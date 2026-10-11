"""Controllo end-to-end della demo avviata, senza dipendenze aggiuntive."""

import argparse
import json
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8017)
    parser.add_argument("--require-clm", action="store_true", help="Fallisce se CLM non esegue una classificazione reale")
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    with urlopen(base, timeout=10) as response:
        assert b"compare-form" in response.read(), "Pagina demo non trovata"
    with urlopen(base + "/health", timeout=10) as response:
        assert json.load(response)["status"] == "ready"
    with urlopen(base + "/assets/ticket.json", timeout=10) as response:
        payload = json.load(response)
    request = Request(base + "/v1/decisions", data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=300) as response:
        result = json.load(response)
    assert set(result["answers"]) == set(payload["questions"])
    for name, answer in result["answers"].items():
        assert answer["type"] == payload["questions"][name]["type"]
        assert answer["status"] in {"ok", "insufficient_evidence", "uncertain", "out_of_range"}
        assert abs(sum(answer["probabilities"].values()) - 1) < 1e-6
        assert all(0 <= p <= 1 for p in answer["probabilities"].values())
    assert result["timing"]["generated_tokens"] == 0
    case = {"question": "Quale reparto deve gestire il problema principale?",
            "context": payload["state"], "classes": [{"label": "Accesso", "description": "Login e password"},
            {"label": "Pagamenti", "description": "Fatture e addebiti"}], "allow_abstain": True}
    def post(path, body):
        call = Request(base + path, data=json.dumps(body).encode(),
                       headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(call, timeout=300) as response:
            return json.load(response)
    prepared = post("/api/prepare", case)
    local = post("/api/classify/rizzo", prepared["case"])
    assert local["status"] == "ok" and local["classification"] in {"Accesso", "Pagamenti"}
    assert local["latency_ms"] > 0 and local["cost"]["usd"] == 0
    gemini = post("/api/classify/gemini", {"case": prepared["case"]})
    assert gemini["status"] == "skipped" and gemini["cost"]["usd"] is None
    liquid = post("/api/classify/liquid", {"case": prepared["case"], "model": "d1"})
    assert liquid["status"] == "skipped" and liquid["cost"]["usd"] is None
    assert liquid["latency_ms"] is None
    health = post("/api/clm/health", {"base_url": "http://127.0.0.1:8700"})
    if args.require_clm:
        assert health["status"] == "ready", health.get("error", "CLM non pronto")
    clm = post("/api/classify/clm", {"case": prepared["case"], "base_url": "http://127.0.0.1:8700"})
    if health["status"] == "unavailable":
        assert clm["status"] == "unavailable" and clm["latency_ms"] is None and clm["cost"]["usd"] is None
        print("CLM: servizio non attivo, stato esplicito e nessun risultato simulato.")
    else:
        assert clm["status"] in {"ok", "insufficient_evidence"} and clm["latency_ms"] > 0
        assert clm["cost"]["usd"] == 0
        assert abs(sum(item["probability"] for item in clm["probabilities"]) - 1) < 0.01
        print("CLM: classificazione verificata sul servizio configurato.")
        print(json.dumps({"classification": clm["classification"], "status": clm["status"],
                          "latency_ms": clm["latency_ms"], "cost": clm["cost"],
                          "runtime": clm.get("runtime")}, ensure_ascii=False))
    print("Confronto HTTP verificato: Rizzo reale; Gemini e Liquid senza chiavi; collegamento CLM.")
    print(json.dumps({"status": "ok", "model": result["model"],
                      "timing": result["timing"], "answers": {
                          key: {field: value for field, value in answer.items()
                                if field in {"type", "status", "value", "choice", "score"}}
                          for key, answer in result["answers"].items()
                      }}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
