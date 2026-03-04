"""
Trinity Voice API
=================
FastAPI backend that exposes Trinity's brain over HTTPS for the mobile app.

Endpoints
---------
  POST /api/auth/token   — exchange PIN for a JWT access token
  POST /api/voice        — upload audio → STT → Trinity → TTS → audio response
  POST /api/ask          — send text   → Trinity → optional TTS → response
  GET  /api/status       — health check (unauthenticated)

Security
--------
  - JWT HS256 tokens, configurable TTL (default 24 h)
  - All API keys (Anthropic, Google) stay server-side only
  - Slowapi rate limiting: 20 req/min for voice, 30/min for text, 5/min for auth
  - CORS locked to configured origins in production

Environment variables required
-------------------------------
  TRINITY_APP_PIN_HASH   SHA-256 hex digest of the PIN (e.g. echo -n "1234" | sha256sum)
  TRINITY_JWT_SECRET     Long random string used to sign JWTs
  GOOGLE_CLOUD_API_KEY   Google Cloud API key with Speech + TTS enabled
                         (falls back to GOOGLE_API_KEY if absent)
  TRINITY_API_PORT       Port to listen on (default 8000)
  TRINITY_API_CORS       Comma-separated allowed origins (default "*")

Run
---
  python core/api.py                      # standalone
  uvicorn core.api:app --host 0.0.0.0     # via uvicorn directly
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Make sure Trinity's root is on the import path regardless of cwd
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

_APP_PIN_HASH   = os.environ.get("TRINITY_APP_PIN_HASH", "")
_JWT_SECRET     = os.environ.get("TRINITY_JWT_SECRET", "change-me-please-use-a-real-secret")
_JWT_ALGORITHM  = "HS256"
_JWT_TTL_HOURS  = int(os.environ.get("TRINITY_JWT_TTL_HOURS", "24"))
_GOOGLE_KEY     = os.environ.get("GOOGLE_CLOUD_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
_CORS_ORIGINS   = [o.strip() for o in os.environ.get("TRINITY_API_CORS", "*").split(",")]

# ── FastAPI app ───────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Trinity Voice API",
    version="1.0.0",
    docs_url=None,   # disable Swagger UI in production
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Auth ──────────────────────────────────────────────────────────────────────

_security = HTTPBearer()


def _verify_pin(pin: str) -> bool:
    if not _APP_PIN_HASH:
        return True  # dev mode: no PIN configured
    return hashlib.sha256(pin.encode()).hexdigest() == _APP_PIN_HASH


def _create_token(sub: str = "david") -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "iat": now, "exp": now + timedelta(hours=_JWT_TTL_HOURS)}
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def _require_auth(creds: HTTPAuthorizationCredentials = Depends(_security)) -> str:
    try:
        payload = jwt.decode(creds.credentials, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        sub: str = payload.get("sub", "")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return sub
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {exc}") from exc


# ── Pydantic models ───────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    pin: str


class AskRequest(BaseModel):
    text: str
    language: Optional[str] = None   # "english" | "tamil" — auto-detected if omitted
    tts: bool = True                  # include audio in response


class VoiceResponse(BaseModel):
    text_input: str
    text_response: str
    language: str
    audio_base64: Optional[str] = None   # MP3 bytes encoded as base64


# ── Speech-to-Text ────────────────────────────────────────────────────────────

def _google_stt(audio_bytes: bytes, encoding: str = "OGG_OPUS", language: str = "en-US") -> str:
    """
    Call Google Cloud Speech-to-Text v1 REST API.

    encoding: OGG_OPUS | LINEAR16 | WEBM_OPUS | MP3
    language: BCP-47 language code — en-US or ta-IN
    """
    import requests  # noqa: PLC0415

    body = {
        "config": {
            "encoding": encoding,
            "sampleRateHertz": 16000,
            "languageCode": language,
            "alternativeLanguageCodes": ["ta-IN"] if language == "en-US" else ["en-US"],
            "model": "latest_long",
            "enableAutomaticPunctuation": True,
            "useEnhanced": True,
        },
        "audio": {"content": base64.b64encode(audio_bytes).decode()},
    }

    url = f"https://speech.googleapis.com/v1/speech:recognize?key={_GOOGLE_KEY}"
    resp = requests.post(url, json=body, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Google STT HTTP {resp.status_code}: {resp.text[:300]}")

    results = resp.json().get("results", [])
    if not results:
        return ""
    return " ".join(r["alternatives"][0]["transcript"] for r in results)


def _detect_audio_encoding(filename: str) -> str:
    """Guess STT encoding from file extension."""
    ext = Path(filename).suffix.lower()
    return {
        ".ogg": "OGG_OPUS",
        ".opus": "OGG_OPUS",
        ".webm": "WEBM_OPUS",
        ".wav": "LINEAR16",
        ".mp3": "MP3",
    }.get(ext, "OGG_OPUS")


# ── Text-to-Speech ────────────────────────────────────────────────────────────

def _google_tts(text: str, language: str = "english") -> bytes:
    """
    Call Google Cloud Text-to-Speech v1 REST API.
    Returns raw MP3 bytes.
    """
    import requests  # noqa: PLC0415

    if language == "tamil":
        lang_code  = "ta-IN"
        voice_name = "ta-IN-Standard-A"
    else:
        lang_code  = "en-US"
        voice_name = "en-US-Neural2-F"   # Neural2 = higher quality, same price tier

    body = {
        "input": {"text": text},
        "voice": {"languageCode": lang_code, "name": voice_name},
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": 1.05,
            "pitch": 0.0,
        },
    }

    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={_GOOGLE_KEY}"
    resp = requests.post(url, json=body, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Google TTS HTTP {resp.status_code}: {resp.text[:300]}")

    audio_b64 = resp.json().get("audioContent", "")
    if not audio_b64:
        raise RuntimeError("Google TTS returned empty audio content")
    return base64.b64decode(audio_b64)


def _gtts_fallback(text: str, language: str = "english") -> bytes:
    """gTTS open-source fallback when Google Cloud TTS is unavailable."""
    from gtts import gTTS  # noqa: PLC0415

    lang_code = "ta" if language == "tamil" else "en"
    buf = io.BytesIO()
    gTTS(text=text, lang=lang_code, slow=False).write_to_fp(buf)
    return buf.getvalue()


def _tts(text: str, language: str) -> Optional[bytes]:
    """TTS with automatic fallback: Google Cloud TTS → gTTS."""
    if _GOOGLE_KEY:
        try:
            return _google_tts(text, language)
        except Exception as exc:
            logger.warning("Google TTS failed, falling back to gTTS: %s", exc)
    try:
        return _gtts_fallback(text, language)
    except Exception as exc:
        logger.error("gTTS fallback also failed: %s", exc)
        return None


# ── Language detection ────────────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    try:
        from voice.language import LanguageDetector  # noqa: PLC0415
        return LanguageDetector().detect(text)
    except Exception:
        return "english"


def _stt_lang_code(language: Optional[str]) -> str:
    return "ta-IN" if language == "tamil" else "en-US"


# ── Trinity brain (singleton) ─────────────────────────────────────────────────

_trinity = None


def _get_trinity():
    global _trinity  # noqa: PLW0603
    if _trinity is None:
        try:
            from core.trinity import Trinity  # noqa: PLC0415
            _trinity = Trinity()
            logger.info("Trinity brain loaded for API mode")
        except Exception as exc:
            raise RuntimeError(f"Trinity brain unavailable: {exc}") from exc
    return _trinity


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/auth/token")
@limiter.limit("5/minute")
async def get_token(request: Request, body: TokenRequest):
    """Exchange a PIN for a JWT access token."""
    if not _verify_pin(body.pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    token = _create_token()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": _JWT_TTL_HOURS * 3600,
    }


@app.post("/api/voice", response_model=VoiceResponse)
@limiter.limit("20/minute")
async def voice_endpoint(
    request:  Request,
    audio:    UploadFile = File(..., description="Recorded audio file (OGG/Opus preferred)"),
    language: Optional[str] = Form(None, description="'english' or 'tamil' — auto-detected if omitted"),
    tts:      bool = Form(True, description="Include TTS audio in response"),
    _user:    str  = Depends(_require_auth),
):
    """
    Full voice pipeline:
      Upload audio → Google STT → Trinity brain → Google TTS → response

    Audio formats supported: OGG/Opus (.ogg), WebM/Opus (.webm),
                             WAV/PCM (.wav), MP3 (.mp3)
    Preferred: OGG/Opus 16 kHz mono (smallest + highest quality)
    """
    # 1. Read and validate audio
    audio_bytes = await audio.read()
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Audio too large (10 MB max)")
    if len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Audio too small — recording may be empty")

    # 2. Speech → Text
    encoding = _detect_audio_encoding(audio.filename or ".ogg")
    lang_code = _stt_lang_code(language)
    try:
        transcript = _google_stt(audio_bytes, encoding=encoding, language=lang_code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Speech recognition error: {exc}") from exc

    if not transcript.strip():
        raise HTTPException(status_code=422, detail="No speech detected — please try again")

    # 3. Detect language if caller did not specify
    detected_lang = language or _detect_language(transcript)

    # 4. Ask Trinity
    try:
        response_text = _get_trinity().ask_trinity(transcript)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Trinity brain error: {exc}") from exc

    # 5. Text → Speech
    audio_b64: Optional[str] = None
    if tts:
        mp3_bytes = _tts(response_text, detected_lang)
        if mp3_bytes:
            audio_b64 = base64.b64encode(mp3_bytes).decode()

    return VoiceResponse(
        text_input=transcript,
        text_response=response_text,
        language=detected_lang,
        audio_base64=audio_b64,
    )


@app.post("/api/ask", response_model=VoiceResponse)
@limiter.limit("30/minute")
async def ask_endpoint(
    request: Request,
    body:    AskRequest,
    _user:   str = Depends(_require_auth),
):
    """
    Text-only pipeline — useful for testing, typing, or when STT is done on-device.

    Send text → Trinity brain → optional TTS audio response.
    """
    detected_lang = body.language or _detect_language(body.text)

    try:
        response_text = _get_trinity().ask_trinity(body.text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Trinity brain error: {exc}") from exc

    audio_b64: Optional[str] = None
    if body.tts:
        mp3_bytes = _tts(response_text, detected_lang)
        if mp3_bytes:
            audio_b64 = base64.b64encode(mp3_bytes).decode()

    return VoiceResponse(
        text_input=body.text,
        text_response=response_text,
        language=detected_lang,
        audio_base64=audio_b64,
    )


@app.get("/api/status")
async def status():
    """Unauthenticated health check — safe to call from load balancers."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "time": datetime.now(timezone.utc).isoformat(),
        "google_stt_available": bool(_GOOGLE_KEY),
        "google_tts_available": bool(_GOOGLE_KEY),
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("TRINITY_API_PORT", "8000"))
    logger.info("Starting Trinity Voice API on port %d", port)
    uvicorn.run(
        "core.api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        access_log=True,
    )
