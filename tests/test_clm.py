"""CLM contract tests with explicit fixtures; no model inference is simulated in the app."""
import io
import json
from pathlib import Path
import sys
import time
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison import Case, CLMInput, clm_body, clm_url, clm_classify, clm_health, clm_http


def sample(**settings):
    return CLMInput(case=Case(question="Quale reparto?", context="Password dimenticata",
        classes=[{"label": "Accesso", "description": "Login e password"}, {"label": "Pagamenti"}],
        files=[{"name": "nota.txt", "text": "Abbonamento attivo"}]), **settings)


def response():
    return {"model": "clm-latest", "answers": {"classification": {"type": "choice", "choice": "c0",
        "probabilities": {"c0": 0.9, "c1": 0.08, "__insufficient__": 0.02}}},
        "usage": {"input_tokens": 1000, "output_tokens": 0, "billing_units": 1}}


def ready(*args):
    return {"status": "ready", "check_ms": 250}


class CLMTests(unittest.TestCase):
    def test_shared_content_and_no_generation_or_model_substitution(self):
        case = sample().case
        body = clm_body(case)
        self.assertEqual(body["state"], case.state())
        self.assertEqual(body["questions"]["classification"]["instructions"], case.question)
        self.assertEqual(body["model"], "clm-latest")
        criteria = body["questions"]["classification"]["criteria"]
        self.assertEqual(criteria["c0"], case.options()[0]["description"])
        self.assertIn("__insufficient__", criteria)
        case.allow_abstain = False
        self.assertNotIn("__insufficient__", clm_body(case)["questions"]["classification"]["criteria"])

    def test_urls_and_pricing_validation(self):
        self.assertEqual(clm_url("http://localhost:8700/v1/systemone/"), "http://localhost:8700")
        self.assertEqual(clm_url("https://example.com/clm/"), "https://example.com/clm")
        for url in ("file:///tmp/key", "http://remote.example", "https://user:key@example.com", "https://example.com?key=secret", "https://example.com/#secret", "https://example.com\\other", "https://example.com:bad"):
            with self.assertRaises(ValueError):
                sample(base_url=url)
        for settings in ({"billing_mode": "per_token"}, {"input_per_million_usd": -1}, {"input_per_million_usd": float("nan")}):
            with self.assertRaises(ValueError):
                sample(**settings)

    def test_health_checks_encoder_model_and_rejects_mock(self):
        good = {"ok": True, "embedder": True, "models": ["clm-latest"]}
        self.assertEqual(clm_health("http://localhost:8700", transport=lambda *args, **kwargs: good)["status"], "ready")
        local = {**good, "runtime": "Qwen3-8B INT8 CPU · Transformers", "max_tokens": 8192, "truncation": False}
        checked = clm_health("http://localhost:8700", transport=lambda *args, **kwargs: local)
        self.assertEqual(checked["runtime"], local["runtime"])
        self.assertEqual(checked["max_tokens"], 8192)
        self.assertIs(checked["truncation"], False)
        for health in ({**good, "embedder": False}, {**good, "mock": True}, {**good, "models": ["qwen-raw"]}, {}):
            self.assertEqual(clm_health("http://localhost:8700", transport=lambda *args, **kwargs: health)["status"], "unavailable")

    def test_unavailable_never_classifies_or_shows_zero_cost(self):
        def never(*args, **kwargs):
            self.fail("Classification must not run")
        result = clm_classify(sample(), transport=never, checker=lambda *args: {"status": "unavailable", "error": "Encoder spento"})
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["classification"])
        self.assertIsNone(result["latency_ms"])
        self.assertIsNone(result["cost"]["usd"])

    def test_classification_latency_and_user_declared_pricing(self):
        def delayed(*args, **kwargs):
            time.sleep(0.02)
            return response()
        for mode, rate, expected in (("self_hosted", None, 0), ("unknown", None, None), ("per_token", 0.05, 0.00005)):
            result = clm_classify(sample(billing_mode=mode, input_per_million_usd=rate), transport=delayed, checker=ready)
            self.assertEqual(result["classification"], "Accesso")
            self.assertEqual(result["cost"]["usd"], expected)
            self.assertGreaterEqual(result["latency_ms"], 20)
            self.assertLess(result["latency_ms"], result["health_check_ms"])
        raw = response()
        raw["usage"] = {}
        self.assertIsNone(clm_classify(sample(billing_mode="per_token", input_per_million_usd=0.05),
            transport=lambda *args, **kwargs: raw, checker=ready)["cost"]["usd"])

    def test_rejects_other_models_and_invalid_distributions(self):
        variants = []
        wrong = response()
        wrong["model"] = "qwen-raw"
        variants.append(wrong)
        wrong = response()
        wrong["answers"]["classification"]["choice"] = "c1"
        variants.append(wrong)
        for dist in ({"c0": 1}, {"c0": float("nan"), "c1": 0, "__insufficient__": 0}, {"c0": 0.1, "c1": 0.1, "__insufficient__": 0.1}):
            wrong = response()
            wrong["answers"]["classification"]["probabilities"] = dist
            variants.append(wrong)
        for raw in variants:
            self.assertEqual(clm_classify(sample(), transport=lambda *args, **kwargs: raw, checker=ready)["status"], "error")

    def test_cpu_timeout_and_runtime_are_reported(self):
        def cpu(*args):
            return {"status": "ready", "runtime": "Qwen3-8B INT8 CPU · Transformers", "check_ms": 1}
        def transport(*args, **kwargs):
            self.assertEqual(kwargs["timeout"], 600)
            return response()
        result = clm_classify(sample(), checker=cpu, transport=transport)
        self.assertEqual(result["status"], "ok")
        self.assertIn("INT8 CPU", result["runtime"])

    def test_local_token_limit_is_reported_without_echoing_arbitrary_errors(self):
        limit = "CLM: testo oltre 8192 token; riduci il contesto o i file."
        for detail in (limit, "test-secret-key"):
            failure = HTTPError("http://localhost:8700/v1/systemone", 422, "invalid", {},
                                io.BytesIO(json.dumps({"detail": detail}).encode()))
            with patch("urllib.request.build_opener") as opener:
                opener.return_value.open.side_effect = failure
                with self.assertRaises(ValueError) as raised:
                    clm_http(failure.url, "test-secret-key", clm_body(sample().case))
            self.assertNotIn("test-secret-key", str(raised.exception))
            if detail == limit:
                self.assertEqual(str(raised.exception), limit)

    def test_transport_headers_and_error_redaction(self):
        class FakeOpener:
            def open(_, request, timeout):
                self.assertEqual(request.full_url, "https://example.com/clm/v1/systemone")
                self.assertEqual(request.get_header("Authorization"), "Bearer test-secret-key")
                self.assertNotIn(b"test-secret-key", request.data)
                return io.BytesIO(json.dumps(response()).encode())
        with patch("urllib.request.build_opener", return_value=FakeOpener()):
            self.assertEqual(clm_http("https://example.com/clm/v1/systemone", "test-secret-key", clm_body(sample().case))["model"], "clm-latest")
        def fail(*args, **kwargs):
            raise ValueError("Errore test-secret-key")
        result = clm_classify(sample(), "test-secret-key", transport=fail, checker=ready)
        self.assertNotIn("test-secret-key", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
