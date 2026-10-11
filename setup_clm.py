"""Download the pinned, official CLM heads and Qwen3 encoder (resumable)."""
from pathlib import Path
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import re
import socket
import threading
import time

from huggingface_hub import HfApi, hf_hub_download, snapshot_download
import requests

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime" / "clm-local"
QWEN_REVISION = "b968826d9c46dd6066d109eabc6255188de91218"
CLM_REVISION = "e939398d4556fcd9400c76fa8c5a513202f42b0a"


def resilient_dns():
    """Fallback to addresses resolved in this process during temporary DNS failures.

    URLs, Host headers, TLS server names and certificate verification stay intact.
    The cache is process-local and never changes the system's DNS settings.
    """
    original = socket.getaddrinfo
    cache = {}
    lock = threading.Lock()
    def resolve(host, port, *args, **kwargs):
        key = (host, port, args, tuple(sorted(kwargs.items())))
        try:
            addresses = original(host, port, *args, **kwargs)
            with lock:
                cache[key] = addresses
            return addresses
        except socket.gaierror:
            with lock:
                addresses = cache.get(key)
            if addresses:
                return addresses
            raise
    socket.getaddrinfo = resolve


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for data in iter(lambda: source.read(8 << 20), b""):
            digest.update(data)
    return digest.hexdigest()


def download_weights(workers, batch_blocks=0):
    """Bounded parallel ranges for connections on which single large GETs stall."""
    info = HfApi().model_info("Qwen/Qwen3-8B", revision=QWEN_REVISION, files_metadata=True, token=False)
    files = [f for f in info.siblings if f.rfilename.endswith(".safetensors")]
    encoder = RUNTIME / "encoder"
    parts = encoder / ".parts"
    parts.mkdir(parents=True, exist_ok=True)
    chunks = []
    pending = []
    for file in files:
        target = encoder / file.rfilename
        if target.is_file() and target.stat().st_size == file.size and sha256(target) == file.lfs.sha256:
            print(f"Verificato: {file.rfilename}", flush=True)
            continue
        pending.append(file)
        for start in range(0, file.size, 8 << 20):
            chunks.append((file, start, min(file.size - 1, start + (8 << 20) - 1)))

    connections = threading.local()
    def fetch(chunk):
        if not hasattr(connections, "session"):
            connections.session = requests.Session()
        file, start, end = chunk
        part = parts / f"{file.rfilename}.{start}"
        partial = part.with_suffix(part.suffix + ".partial")
        size = end - start + 1
        if part.is_file() and part.stat().st_size == size:
            return size
        url = f"https://huggingface.co/Qwen/Qwen3-8B/resolve/{QWEN_REVISION}/{file.rfilename}"
        for attempt in range(5):
            offset = partial.stat().st_size if partial.exists() else 0
            if offset > size:
                partial.unlink()
                offset = 0
            if offset == size:
                partial.replace(part)
                return size
            try:
                with connections.session.get(url, headers={"Range": f"bytes={start + offset}-{end}"},
                                  stream=True, timeout=(30, 60)) as response:
                    response.raise_for_status()
                    expected = f"bytes {start + offset}-{end}/{file.size}"
                    if response.status_code != 206 or response.headers.get("Content-Range") != expected:
                        raise ValueError(f"HTTP Range non valido: {response.status_code}, {response.headers.get('Content-Range')}; atteso {expected}")
                    with partial.open("ab") as output:
                        for data in response.iter_content(1 << 20):
                            output.write(data)
                if partial.stat().st_size != size:
                    raise ValueError("Blocco incompleto")
                partial.replace(part)
                return size
            except (requests.RequestException, ValueError) as error:
                if attempt == 4:
                    reason = re.sub(r"https?://[^\s)']+", "[download URL]", str(error))[:250]
                    raise RuntimeError(f"{file.rfilename}, blocco {start}: {reason}. Riesegui per riprendere.") from None
                time.sleep(attempt + 1)

    total = sum(end - start + 1 for _, start, end in chunks)
    saved = 0
    missing = []
    for chunk in chunks:
        file, start, end = chunk
        part = parts / f"{file.rfilename}.{start}"
        if part.is_file() and part.stat().st_size == end - start + 1:
            saved += end - start + 1
        else:
            missing.append(chunk)
    selected = missing[:batch_blocks] if batch_blocks else missing
    print(f"Blocchi completi riutilizzati: {saved / 1e9:.2f} GB; da scaricare in questo lotto: {len(selected)}", flush=True)
    completed = 0
    last_report = 0
    started = time.perf_counter()
    errors = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for task in as_completed([pool.submit(fetch, chunk) for chunk in selected]):
            try:
                completed += task.result()
            except RuntimeError as error:
                errors.append(str(error))
                print(f"Blocco da riprendere: {error}", flush=True)
            now = time.perf_counter()
            if now - last_report >= 10 or completed == total:
                done = saved + completed
                print(f"Encoder: {done / 1e9:.2f}/{total / 1e9:.2f} GB ({100 * done / max(total, 1):.1f}%)", flush=True)
                last_report = now
    if errors:
        raise RuntimeError(f"{len(errors)} blocchi da riprendere. Riesegui setup_clm.py --range-download; gli altri blocchi restano salvati.")
    if len(selected) < len(missing):
        print("Lotto completato. Riesegui per completare i blocchi rimanenti.", flush=True)
        return False
    for file in pending:
        target = encoder / file.rfilename
        temporary = target.with_suffix(".assembling")
        with temporary.open("wb") as output:
            for start in range(0, file.size, 8 << 20):
                with (parts / f"{file.rfilename}.{start}").open("rb") as source:
                    for data in iter(lambda: source.read(1 << 20), b""):
                        output.write(data)
        if sha256(temporary) != file.lfs.sha256:
            raise RuntimeError(f"SHA-256 non corrispondente: {file.rfilename}. Pesi non utilizzati.")
        temporary.replace(target)
        for start in range(0, file.size, 8 << 20):
            (parts / f"{file.rfilename}.{start}").unlink()
        print(f"SHA-256 verificato: {file.rfilename}", flush=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range-download", action="store_true")
    parser.add_argument("--workers", type=int, default=32, choices=range(1, 65))
    parser.add_argument("--batch-blocks", type=int, default=0, choices=range(0, 2049))
    args = parser.parse_args()
    print("Download heads ufficiali CLM-v0.1-8B", flush=True)
    hf_hub_download("Contrastive-LM/CLM-v0.1-8B", "CLM_v0.1-8B.pt",
                    revision=CLM_REVISION, local_dir=RUNTIME / "heads")
    print("Download encoder ufficiale Qwen3-8B (~16 GB); download riprendibile", flush=True)
    snapshot_download("Qwen/Qwen3-8B", revision=QWEN_REVISION,
                      local_dir=RUNTIME / "encoder", max_workers=3,
                      allow_patterns=(["*.json", "*.txt", "LICENSE"] if args.range_download else
                                      ["*.safetensors", "*.json", "*.txt", "LICENSE"]))
    if args.range_download:
        if not download_weights(args.workers, args.batch_blocks):
            return
    (RUNTIME / "installed").write_text(f"{QWEN_REVISION}\n{CLM_REVISION}\n", encoding="utf-8")
    print("CLM pronto per start-clm.ps1", flush=True)


if __name__ == "__main__":
    resilient_dns()
    main()
