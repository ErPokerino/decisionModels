"""Confronto Rizzo Flow / Gemini 3.5 Flash-Lite / Liquid AI d1 / CLM."""

import argparse
import os
from pathlib import Path

import uvicorn
from fastapi import Header, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from rizzo_flow.api import create_app
from rizzo_flow.engine import Engine
from rizzo_flow.loader import load_backend

from comparison import Case, GeminiInput, LiquidInput, PrepareInput, PRICING, GEMINI_MODEL, LIQUID_MODEL, LIQUID_PRICING
from comparison import gemini_classify, liquid_classify, local_classify, prepare
from comparison import CLMInput, CLMConnection, CLM_MODEL, CLM_CHECKPOINT, CLM_BASE_URL, clm_classify, clm_health

ROOT = Path(__file__).resolve().parent


def build_app(engine):
    app = create_app(engine)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def protect_api(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Origine della richiesta non consentita."}, status_code=403)
            if int(request.headers.get("content-length", "0")) > 15 * 1024 * 1024:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Richiesta troppo grande (massimo 15 MB)."}, status_code=413)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response
    # Sostituisce solo il redirect iniziale; playground e API restano disponibili.
    app.router.routes = [route for route in app.router.routes if route.path != "/"]
    app.mount("/assets", StaticFiles(directory=ROOT / "web"), name="assets")

    @app.get("/", include_in_schema=False)
    def demo():
        return FileResponse(ROOT / "web" / "index.html")

    @app.get("/api/config")
    def config():
        return {"gemini_model": GEMINI_MODEL, "pricing": PRICING, "context_tokens": engine.ctx,
                "liquid_model": LIQUID_MODEL, "liquid_pricing": LIQUID_PRICING,
                "clm_model": CLM_MODEL, "clm_checkpoint": CLM_CHECKPOINT, "clm_base_url": CLM_BASE_URL}

    @app.post("/api/prepare")
    def prepare_case(data: PrepareInput):
        try:
            return prepare(data)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/classify/rizzo")
    def classify_rizzo(case: Case):
        return local_classify(engine, case)

    @app.post("/api/classify/gemini")
    def classify_gemini(data: GeminiInput, x_gemini_api_key: str = Header(default="")):
        return gemini_classify(data.case, x_gemini_api_key.strip(), data.billing_tier)

    @app.post("/api/classify/liquid")
    def classify_liquid(data: LiquidInput, x_liquid_api_key: str = Header(default="")):
        return liquid_classify(data.case, x_liquid_api_key.strip(), data.model)

    @app.post("/api/clm/health")
    def check_clm(data: CLMConnection, x_clm_api_key: str = Header(default="")):
        return clm_health(data.base_url, x_clm_api_key.strip())

    @app.post("/api/classify/clm")
    def classify_clm(data: CLMInput, x_clm_api_key: str = Header(default="")):
        return clm_classify(data, x_clm_api_key.strip())

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8017)
    parser.add_argument("--size", choices=["4b", "1.7b"], default="4b")
    parser.add_argument("--quant", choices=["q4_k_m", "q8_0"], default="q4_k_m")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "vulkan"], default="auto")
    parser.add_argument("--ctx", type=int, default=8192)
    args = parser.parse_args()
    os.chdir(ROOT / ".runtime" / "rizzo-flow")
    backend = load_backend(size=args.size, quant=args.quant, device=args.device, ctx=args.ctx, batch_size=1)
    engine = Engine(backend, ctx=args.ctx)
    try:
        print(f"\nDemo: http://127.0.0.1:{args.port}\n", flush=True)
        uvicorn.run(build_app(engine), host="127.0.0.1", port=args.port)
    finally:
        engine._worker.shutdown(wait=True)
        backend.close()


if __name__ == "__main__":
    main()
