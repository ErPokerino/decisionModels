import base64
import io
import json
import time
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison import Case, PrepareInput, extract_text, gemini_body, gemini_classify, gemini_http, prepare, usage_cost
from comparison import LiquidInput, liquid_body, liquid_classify, liquid_http, liquid_usage_cost


def sample_case(**overrides):
    return Case.model_validate({"question": "Quale reparto deve gestire la richiesta?",
        "context": "Non riesco ad accedere dopo il cambio della password.",
        "classes": [{"label": "Accesso"}, {"label": "Pagamenti"}], **overrides})


def gemini_response(class_id="c0", finish="STOP"):
    return {"modelVersion": "gemini-3.5-flash-lite", "candidates": [{"finishReason": finish,
        "content": {"parts": [{"text": "pensiero nascosto", "thought": True},
                              {"text": json.dumps({"class_id": class_id})}]}}],
        "usageMetadata": {"promptTokenCount": 1000, "cachedContentTokenCount": 100,
            "candidatesTokenCount": 20, "thoughtsTokenCount": 30, "totalTokenCount": 1050}}


def liquid_response(choice="c0"):
    return {"model": "d1", "answers": {"classification": {"type": "choice", "choice": choice,
        "probabilities": {"c0": 0.90, "c1": 0.08, "__insufficient__": 0.02}, "confidence": 0.85}},
        "usage": {"input_tokens": 1000, "output_tokens": 0}}


def text_pdf():
    stream = b"BT /F1 12 Tf 30 100 Td (Fattura: totale 50 euro) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    data, offsets = b"%PDF-1.4\n", [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return data + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode()


class ComparisonTests(unittest.TestCase):
    def test_evidence_and_options_are_identical(self):
        case = sample_case(files=[{"name": "extra.txt", "text": "Abbonamento attivo"}])
        native, gemini = case.native(), gemini_body(case)
        prompt = json.loads(gemini["contents"][0]["parts"][0]["text"])
        self.assertEqual(native.state, prompt["evidence"])
        self.assertEqual([option.model_dump() for option in native.questions["classification"].options], prompt["options"][:-1])
        self.assertIn("__insufficient__", gemini["generationConfig"]["responseJsonSchema"]["properties"]["class_id"]["enum"])

    def test_abstention_policy_and_duplicate_classes(self):
        case = sample_case(allow_abstain=False)
        self.assertEqual(len(gemini_body(case)["generationConfig"]["responseJsonSchema"]["properties"]["class_id"]["enum"]), 2)
        with self.assertRaises(ValueError):
            sample_case(classes=[{"label": "Accesso"}, {"label": " accesso "}])

    def test_cost_includes_thinking_and_discounted_cache_once(self):
        usage = gemini_response()["usageMetadata"]
        self.assertAlmostEqual(usage_cost(usage, "paid")["usd"], 0.000398)
        self.assertEqual(usage_cost(usage, "paid")["billable_output_tokens"], 50)
        self.assertEqual(usage_cost(usage, "free")["usd"], 0)
        self.assertAlmostEqual(usage_cost(usage, "free")["paid_equivalent_usd"], 0.000398)
        self.assertIsNone(usage_cost({}, "paid")["usd"])

    def test_valid_response_and_unavailable_class_keep_real_usage(self):
        result = gemini_classify(sample_case(), "test-key", transport=lambda body, key: gemini_response())
        self.assertEqual(result["classification"], "Accesso")
        self.assertGreaterEqual(result["latency_ms"], 0)
        invalid = gemini_classify(sample_case(), "test-key", transport=lambda body, key: gemini_response("inventata"))
        self.assertEqual(invalid["status"], "error")
        self.assertGreater(invalid["cost"]["usd"], 0)
        truncated = gemini_classify(sample_case(), "test-key", transport=lambda body, key: gemini_response(finish="MAX_TOKENS"))
        self.assertEqual(truncated["status"], "error")
        self.assertGreater(truncated["cost"]["usd"], 0)

    def test_missing_key_never_calls_google_and_secrets_are_redacted(self):
        def fail(body, key):
            raise ValueError("Errore con test-secret-key")
        skipped = gemini_classify(sample_case(), "", transport=fail)
        self.assertEqual(skipped["status"], "skipped")
        self.assertIsNone(skipped["latency_ms"])
        failed = gemini_classify(sample_case(), "test-secret-key", transport=fail)
        self.assertNotIn("test-secret-key", json.dumps(failed))

    def test_transport_uses_header_not_url_for_key(self):
        def respond(request, timeout):
            self.assertNotIn("test-secret-key", request.full_url)
            self.assertNotIn(b"test-secret-key", request.data)
            self.assertEqual(request.get_header("X-goog-api-key"), "test-secret-key")
            self.assertIn("gemini-3.5-flash-lite:generateContent", request.full_url)
            self.assertEqual(timeout, 120)
            return io.BytesIO(json.dumps(gemini_response()).encode())
        with patch("urllib.request.urlopen", side_effect=respond):
            self.assertIn("usageMetadata", gemini_http(gemini_body(sample_case()), "test-secret-key"))

    def test_text_pdf_docx_and_no_silent_truncation(self):
        self.assertEqual(extract_text("contesto.txt", "città".encode()), "città")
        self.assertIn("Fattura", extract_text("fattura.pdf", text_pdf()))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Contratto di servizio</w:t></w:r></w:p></w:body></w:document>')
        self.assertEqual(extract_text("contratto.docx", buffer.getvalue()), "Contratto di servizio")
        with self.assertRaises(ValueError):
            extract_text("foto.png", b"image")
        with self.assertRaises(ValueError):
            extract_text("troppo-lungo.txt", b"a" * 32001)

    def test_prepare_combines_text_and_attachments(self):
        data = PrepareInput.model_validate({**sample_case().model_dump(exclude={"files"}),
            "attachments": [{"name": "nota.txt", "content_base64": base64.b64encode(b"Password cambiata").decode()}]})
        result = prepare(data)
        self.assertEqual(result["case"]["files"][0]["text"], "Password cambiata")
        self.assertEqual(result["files"][0]["characters"], 17)
        with self.assertRaises(ValueError):
            sample_case(context="a" * 31999, files=[{"name": "nota.txt", "text": "troppo"}])

    def test_liquid_shared_evidence_classes_and_abstention(self):
        case = sample_case(files=[{"name": "nota.txt", "text": "Abbonamento attivo"}])
        body = liquid_body(case)
        self.assertEqual(body["state"], case.native().state)
        self.assertEqual(body["questions"]["classification"]["instructions"], case.question)
        criteria = body["questions"]["classification"]["criteria"]
        self.assertEqual(criteria["c0"], case.options()[0]["description"])
        self.assertIn("__insufficient__", criteria)
        self.assertNotIn("__insufficient__", liquid_body(sample_case(allow_abstain=False))["questions"]["classification"]["criteria"])
        with self.assertRaises(ValueError):
            LiquidInput.model_validate({"case": case.model_dump(), "model": "inventato"})

    def test_liquid_cost_real_usage_and_unknown_cost(self):
        self.assertAlmostEqual(liquid_usage_cost({"input_tokens": 1000}, "d1")["usd"], 0.00004)
        self.assertEqual(liquid_usage_cost({"input_tokens": 1000}, "d1:free")["usd"], 0)
        self.assertIsNone(liquid_usage_cost({}, "d1")["usd"])
        self.assertIsNone(liquid_usage_cost({}, "d1:free")["usd"])
        for invalid in (-1, True, "1000"):
            with self.assertRaises(ValueError):
                liquid_usage_cost({"input_tokens": invalid}, "d1")

    def test_liquid_valid_result_and_latency_include_transport(self):
        def respond(body, key):
            time.sleep(0.02)
            return liquid_response()
        result = liquid_classify(sample_case(), "test-key", transport=respond)
        self.assertEqual(result["classification"], "Accesso")
        self.assertEqual(result["confidence"], 0.85)
        self.assertGreaterEqual(result["latency_ms"], 20)
        self.assertEqual(len(result["probabilities"]), 3)
        raw = liquid_response("__insufficient__")
        raw["answers"]["classification"]["probabilities"] = {"c0": 0.02, "c1": 0.08, "__insufficient__": 0.9}
        result = liquid_classify(sample_case(), "test-key", transport=lambda *args: raw)
        self.assertEqual(result["status"], "insufficient_evidence")

    def test_liquid_invalid_decisions_keep_actual_cost(self):
        variants = [liquid_response("inventata"), liquid_response("c1")]
        for distribution in ({"c0": 1}, {"c0": float("nan"), "c1": 0, "__insufficient__": 0},
                             {"c0": 0.1, "c1": 0.1, "__insufficient__": 0.1}):
            raw = liquid_response()
            raw["answers"]["classification"]["probabilities"] = distribution
            variants.append(raw)
        for raw in variants:
            result = liquid_classify(sample_case(), "test-key", transport=lambda *args: raw)
            self.assertEqual(result["status"], "error")
            self.assertGreater(result["cost"]["usd"], 0)

    def test_liquid_missing_key_and_error_redaction(self):
        def fail(body, key):
            raise ValueError("Errore con test-secret-key")
        skipped = liquid_classify(sample_case(), "", transport=fail)
        self.assertEqual(skipped["status"], "skipped")
        self.assertIsNone(skipped["latency_ms"])
        self.assertNotIn("test-secret-key", json.dumps(liquid_classify(sample_case(), "test-secret-key", transport=fail)))
        result = liquid_classify(sample_case(), "bad\nkey", transport=fail)
        self.assertIsNone(result["latency_ms"])

    def test_liquid_key_only_in_authorization_header(self):
        def respond(request, timeout):
            self.assertEqual(request.full_url, "https://api.liquid.ai/decisions/v1/systemone")
            self.assertNotIn(b"test-secret-key", request.data)
            self.assertEqual(request.get_header("Authorization"), "Bearer test-secret-key")
            self.assertEqual(timeout, 120)
            return io.BytesIO(json.dumps(liquid_response()).encode())
        with patch("urllib.request.urlopen", side_effect=respond):
            self.assertIn("usage", liquid_http(liquid_body(sample_case()), "test-secret-key"))


if __name__ == "__main__":
    unittest.main()
