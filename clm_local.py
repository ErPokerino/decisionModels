"""Official CLM engine with a Windows CPU Qwen3-8B last-token encoder."""
import argparse
from collections import OrderedDict
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime" / "clm-local"
sys.path.insert(0, str(ROOT / ".runtime" / "clm-reference" / "src"))


def quantize_encoder(model):
    """Convert one linear layer at a time, avoiding a second copy of the 8B model."""
    import torch
    class Int8Linear(torch.nn.Module):
        def __init__(self, linear):
            super().__init__()
            linear = linear.float()
            linear.qconfig = torch.ao.quantization.default_dynamic_qconfig
            self.linear = torch.ao.nn.quantized.dynamic.Linear.from_float(linear)

        def forward(self, x):
            return self.linear(x.float()).to(x.dtype)

    total = sum(isinstance(module, torch.nn.Linear) for module in model.modules())
    converted = 0
    def convert(module):
        nonlocal converted
        for name, child in list(module.named_children()):
            if isinstance(child, torch.nn.Linear):
                setattr(module, name, Int8Linear(child))
                converted += 1
                if converted % 32 == 0 or converted == total:
                    print(f"Layer encoder INT8: {converted}/{total}", flush=True)
            else:
                convert(child)
    convert(model)
    return model


class LocalEncoder:
    """Same raw-text, normalized last-token embeddings as the upstream embedder.

    No chat template or generation. Reject oversized text instead of truncating.
    Serialize inference to keep CPU memory bounded and cache up to 2048 vectors.
    """
    def __init__(self, model_dir, threads=6, max_tokens=8192):
        import torch
        from transformers import AutoModel, AutoTokenizer
        torch.set_num_threads(threads)
        self.torch = torch
        self.max_tokens = max_tokens
        self.lock = threading.RLock()
        self.cache = OrderedDict()
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        # Load in FP16 then quantize only the encoder's linear layers to INT8.
        # AutoModel omits the unused LM head; the official CLM heads stay FP32.
        self.model = AutoModel.from_pretrained(
            model_dir, local_files_only=True, dtype=torch.float16,
            attn_implementation="sdpa", low_cpu_mem_usage=True).eval()
        print("Quantizzazione CPU INT8 dell'encoder Qwen3-8B", flush=True)
        self.model = quantize_encoder(self.model)

    def healthy(self):
        return True

    def embed(self, texts):
        import numpy as np
        torch = self.torch
        with self.lock:
            # Validate all inputs even on cache hits; never silently truncate context.
            encoded = [self.tokenizer(text, return_tensors="pt") for text in texts]
            if any(item["input_ids"].shape[1] > self.max_tokens for item in encoded):
                raise ValueError(f"CLM: testo oltre {self.max_tokens} token; riduci il contesto o i file.")
            tokens = 0
            vectors = []
            for text, inputs in zip(texts, encoded):
                if text not in self.cache:
                    with torch.inference_mode():
                        hidden = self.model(**inputs, use_cache=False).last_hidden_state
                        vector = torch.nn.functional.normalize(hidden[:, -1, :].float(), dim=-1)
                        self.cache[text] = vector[0].cpu().numpy().copy()
                        tokens += inputs["input_ids"].shape[1]
                    del hidden, vector
                    if len(self.cache) > 2048:
                        self.cache.popitem(last=False)
                self.cache.move_to_end(text)
                vectors.append(self.cache[text])
            return np.stack(vectors), tokens


def main():
    import uvicorn
    from clm import Engine
    from clm.server import create_app
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8700)
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=8192)
    args = parser.parse_args()
    # A second demo startup must not load another 8B encoder into RAM.
    service_lock = (RUNTIME / "server.lock").open("a+b")
    if sys.platform == "win32":
        import msvcrt
        if service_lock.tell() == 0:
            service_lock.write(b"0")
            service_lock.flush()
        service_lock.seek(0)
        try:
            msvcrt.locking(service_lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise SystemExit("CLM locale è già avviato o in caricamento.") from None
    print("Caricamento Qwen3-8B su CPU; attendi CLM pronto prima del confronto.", flush=True)
    encoder = LocalEncoder(RUNTIME / "encoder", args.threads, args.max_tokens)
    engine = Engine(embedder=encoder, checkpoint=str(RUNTIME / "heads" / "CLM_v0.1-8B.pt"),
                    device="cpu", action_cache="16MiB")
    app = create_app(engine, ui=False)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    @app.middleware("http")
    async def runtime_metadata(request, call_next):
        # Expose the actual encoder backend without altering the official API contract.
        from fastapi.responses import JSONResponse
        if request.url.path == "/health":
            from setup_clm import QWEN_REVISION, CLM_REVISION
            return JSONResponse({"ok": True, "embedder": True, "models": [m["name"] for m in engine.models()],
                                 "runtime": "Qwen3-8B INT8 CPU · Transformers",
                                 "encoder_revision": QWEN_REVISION, "checkpoint_revision": CLM_REVISION,
                                 "max_tokens": args.max_tokens, "truncation": False})
        return await call_next(request)
    print(f"CLM pronto: http://127.0.0.1:{args.port} (Qwen3-8B INT8 CPU + heads ufficiali)", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
