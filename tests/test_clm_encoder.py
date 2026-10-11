"""Numerical compatibility checks for the CPU encoder using a tiny real Qwen3."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
HAS_TORCH = importlib.util.find_spec("torch") is not None and importlib.util.find_spec("transformers") is not None


@unittest.skipUnless(HAS_TORCH, "Esegui nell'ambiente CLM per verificare l'encoder CPU")
class EncoderTests(unittest.TestCase):
    def test_int8_qwen3_preserves_normalized_last_token_embeddings(self):
        import torch
        from transformers import Qwen3Config, Qwen3Model
        from clm_local import quantize_encoder
        torch.manual_seed(42)
        torch.set_num_threads(2)
        config = Qwen3Config(vocab_size=64, hidden_size=32, intermediate_size=64,
                             num_hidden_layers=2, num_attention_heads=2,
                             num_key_value_heads=1, head_dim=16)
        model = Qwen3Model(config).eval().half()
        inputs = torch.tensor([[1, 4, 8, 12, 16]])
        with torch.inference_mode():
            baseline = torch.nn.functional.normalize(model(inputs, use_cache=False).last_hidden_state[:, -1].float(), dim=-1)
        model = quantize_encoder(model)
        with torch.inference_mode():
            actual = torch.nn.functional.normalize(model(inputs, use_cache=False).last_hidden_state[:, -1].float(), dim=-1)
        self.assertTrue(torch.isfinite(actual).all())
        self.assertAlmostEqual(actual.norm().item(), 1.0, places=5)
        self.assertGreater(torch.nn.functional.cosine_similarity(actual, baseline).item(), 0.99)
        self.assertTrue(any(isinstance(module, torch.ao.nn.quantized.dynamic.Linear) for module in model.modules()))


if __name__ == "__main__":
    unittest.main()
