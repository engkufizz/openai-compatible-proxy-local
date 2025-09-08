import os
import time
import uuid
import requests
from typing import Dict, Any
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

LMSTUDIO_API_BASE = os.getenv("LMSTUDIO_API_BASE", "http://localhost:1234/v1").rstrip("/")
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "").strip()
MODEL_NAME = os.getenv("LMSTUDIO_PROXY_MODEL_NAME", "lmstudio-proxy")
TIMEOUT = int(os.getenv("PROXY_TIMEOUT", "300"))

app = FastAPI(title="LM Studio OpenAI-Compatible Proxy")

def _session():
    s = requests.Session()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "LMStudio-Proxy/1.0",
    }
    if LMSTUDIO_API_KEY:
        headers["Authorization"] = f"Bearer {LMSTUDIO_API_KEY}"
    s.headers.update(headers)
    return s

@app.get("/health")
def health():
    return {"ok": True, "upstream": LMSTUDIO_API_BASE}

@app.get("/v1/models")
def list_models():
    s = _session()
    try:
        r = s.get(f"{LMSTUDIO_API_BASE}/models", timeout=30)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict) or "data" not in data:
            data = {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "created": int(time.time())}]}
        return JSONResponse(content=data)
    except Exception:
        return JSONResponse(
            content={"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "created": int(time.time())}]}
        )

@app.post("/v1/chat/completions")
def chat_completions(body: Dict[str, Any]):
    want_stream = bool(body.get("stream", False))
    s = _session()
    url = f"{LMSTUDIO_API_BASE}/chat/completions"
    try:
        if want_stream:
            r = s.post(url, json=body, stream=True, timeout=TIMEOUT)
            r.raise_for_status()

            def gen():
                for chunk in r.iter_content(chunk_size=None):
                    if chunk:
                        yield chunk

            media_type = r.headers.get("Content-Type", "text/event-stream")
            return StreamingResponse(gen(), media_type=media_type or "text/event-stream")
        else:
            r = s.post(url, json=body, timeout=TIMEOUT)
            r.raise_for_status()
            j = r.json()
            if isinstance(j, dict):
                j.setdefault("id", f"chatcmpl-{uuid.uuid4().hex[:24]}")
                j.setdefault("model", MODEL_NAME)
            return JSONResponse(content=j)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 502
        try:
            err = e.response.json()
        except Exception:
            err = {"error": {"message": str(e)}}
        return JSONResponse(status_code=status, content=err)
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": {"message": str(e)}})
