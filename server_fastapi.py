# ─────────────────────────────────────────────
#  Polarbear Converter — Python / FastAPI 后端
#  用途：代理前端 TTS 请求，API Key 存在服务器
# ─────────────────────────────────────────────
#  安装依赖：pip install fastapi uvicorn httpx python-dotenv
#  启动方式：uvicorn server:app --reload --port 3000
#  或生产环境：uvicorn server:app --host 0.0.0.0 --port 3000

import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, constr, confloat
from typing import Literal, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Polarbear Converter API")

# ── CORS（按需限制来源） ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 生产环境改为 ["https://yourdomain.com"]
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

# ── 静态文件：前端 HTML 与本文件同目录即可 ──
from fastapi.responses import FileResponse

@app.get("/")
async def serve_frontend():
    return FileResponse("polarbear-converter.html")


# ── 请求体 Schema ──
class TTSRequest(BaseModel):
    input: constr(min_length=1, max_length=5000)
    model: Literal["tts-1", "tts-1-hd"] = "tts-1"
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "alloy"
    speed: confloat(ge=0.5, le=2.0) = 1.0
    response_format: Literal["mp3", "wav", "opus", "aac"] = "mp3"


MIME_MAP = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "opus": "audio/ogg",
    "aac": "audio/aac",
}


# ── TTS 代理接口 ──
@app.post("/v1/audio/speech")
async def tts_proxy(body: TTSRequest):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured on server.")

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")

    async with httpx.AsyncClient(timeout=60) as client:
        upstream = await client.post(
            f"{base_url}/v1/audio/speech",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model":           body.model,
                "input":           body.input.strip(),
                "voice":           body.voice,
                "speed":           body.speed,
                "response_format": body.response_format,
            },
        )

    if upstream.status_code != 200:
        try:
            detail = upstream.json()
        except Exception:
            detail = {"message": "OpenAI API error"}
        raise HTTPException(status_code=upstream.status_code, detail=detail)

    return StreamingResponse(
        iter([upstream.content]),
        media_type=MIME_MAP.get(body.response_format, "audio/mpeg"),
    )
