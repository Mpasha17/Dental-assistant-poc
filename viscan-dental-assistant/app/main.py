"""FastAPI routes for the Viscan dental assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, get_settings, reset_settings
from app.logging_utils import configure_logging, get_logger
from app.orchestrator import handle_dictation, handle_text
from app.schemas import ChatRequest, DictationRequest, DraftUpdateRequest
from app.tools.dictation import approve_draft, get_draft, update_draft
from app.tools.patients import public_patient
from app.tools.reports import get_report_by_id
from app.tools.store import patients, reset_stores

logger = get_logger()

ALLOWED_AUDIO = {
    "audio/webm",
    "video/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/ogg",
    "video/ogg",
    "application/ogg",
}
ALLOWED_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".ogg"}
ROLES = {"dentist", "radiologist", "assistant"}


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    reset_stores()
    app = FastAPI(title="Viscan Dental Assistant", version="0.1.0")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(HTTPException)
    async def http_error(_request: Any, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Any, exc: RequestValidationError) -> JSONResponse:
        parts = []
        for error in exc.errors():
            loc = ".".join(str(item) for item in error.get("loc", []) if item != "body")
            parts.append(f"{loc}: {error.get('msg')}".strip(": "))
        return JSONResponse(
            status_code=422,
            content={"error": "Invalid request", "detail": "; ".join(parts)[:500]},
        )

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Any, exc: Exception) -> JSONResponse:
        logger.error("unhandled error_type=%s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"error": "Internal error"})

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/health")
    def health() -> dict[str, Any]:
        current = get_settings()
        return {
            "status": "ok",
            "llm_provider": current.llm_provider,
            "stt_provider": current.stt_provider,
            "gemini_model": current.gemini_model,
            "mistral_model": current.mistral_model,
            "groq_model": current.groq_model,
            "groq_whisper_model": current.groq_whisper_model,
            "local_whisper_model": current.local_whisper_model,
            "llm_timeout_s": current.llm_timeout_s,
            "demo_date": current.demo_date.isoformat(),
            "keys": {
                "gemini": current.key_present("gemini"),
                "mistral": current.key_present("mistral"),
                "groq": current.key_present("groq"),
            },
        }

    @app.get("/patients")
    def get_patients() -> dict[str, Any]:
        return {"patients": [public_patient(patient) for patient in patients()]}

    @app.get("/reports/{report_id}")
    def get_report(report_id: str) -> dict[str, Any]:
        report = get_report_by_id(report_id)
        if report is None:
            draft = get_draft(report_id)
            if draft is None:
                raise HTTPException(status_code=404, detail="Report not found")
            return {"report": draft, "draft": True}
        return {"report": report, "draft": False}

    @app.post("/chat")
    def chat(body: ChatRequest, role: str = Depends(require_role)) -> dict[str, Any]:
        return handle_text(body.session_id, body.text, role)

    @app.post("/dictation")
    def dictation(body: DictationRequest, role: str = Depends(require_role)) -> dict[str, Any]:
        return handle_dictation(body.session_id, body.transcript, body.patient_id, role)

    @app.post("/voice")
    async def voice(
        audio: UploadFile = File(...),
        session_id: str | None = Form(default=None),
        transcript: str | None = Form(default=None),
        role: str = Depends(require_role),
    ) -> dict[str, Any]:
        settings_now = get_settings()
        payload = await audio.read()
        mime = (audio.content_type or "").split(";")[0].strip().lower()
        logger.info("voice_upload bytes=%s mime=%s", len(payload), mime or "-")
        if len(payload) > settings_now.max_audio_bytes:
            raise HTTPException(status_code=413, detail="Audio exceeds the 10 MB limit")
        if len(payload) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        if not _audio_allowed(audio.content_type, audio.filename):
            raise HTTPException(
                status_code=415,
                detail="Unsupported audio type. Use webm, wav, mp3, m4a, or ogg.",
            )
        from app.stt.router import get_stt

        try:
            spoken = get_stt().transcribe(
                payload,
                audio.content_type or "",
                filename=audio.filename,
                transcript_hint=transcript,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("stt_failed error_type=%s detail=%s", type(exc).__name__, _stt_detail(exc, settings_now))
            raise HTTPException(status_code=503, detail="Speech-to-text failed") from exc
        logger.info("stt_ok provider=%s chars=%s", spoken.provider, len(spoken.text.strip()))
        if not spoken.text.strip():
            raise HTTPException(status_code=422, detail="No speech was recognized")
        return handle_text(
            session_id,
            spoken.text,
            role,
            stt_provider=spoken.provider,
            transcript=spoken.text,
        )

    @app.post("/dictation/audio")
    async def dictation_audio(
        audio: UploadFile = File(...),
        session_id: str | None = Form(default=None),
        patient_id: str | None = Form(default=None),
        transcript: str | None = Form(default=None),
        role: str = Depends(require_role),
    ) -> dict[str, Any]:
        settings_now = get_settings()
        payload = await audio.read()
        mime = (audio.content_type or "").split(";")[0].strip().lower()
        logger.info("dictation_upload bytes=%s mime=%s", len(payload), mime or "-")
        if len(payload) > settings_now.max_audio_bytes:
            raise HTTPException(status_code=413, detail="Audio exceeds the 10 MB limit")
        if len(payload) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        if not _audio_allowed(audio.content_type, audio.filename):
            raise HTTPException(
                status_code=415,
                detail="Unsupported audio type. Use webm, wav, mp3, m4a, or ogg.",
            )
        from app.stt.router import get_stt

        try:
            spoken = get_stt().transcribe(
                payload,
                audio.content_type or "",
                filename=audio.filename,
                transcript_hint=transcript,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("stt_failed error_type=%s detail=%s", type(exc).__name__, _stt_detail(exc, settings_now))
            raise HTTPException(status_code=503, detail="Speech-to-text failed") from exc
        logger.info("stt_ok provider=%s chars=%s", spoken.provider, len(spoken.text.strip()))
        return handle_dictation(session_id, spoken.text, patient_id, role, stt_provider=spoken.provider)

    @app.put("/draft/{draft_id}")
    def edit_draft(draft_id: str, body: DraftUpdateRequest, role: str = Depends(require_role)) -> dict[str, Any]:
        del role
        updated = update_draft(draft_id, body.findings)
        if updated is None:
            raise HTTPException(status_code=404, detail="Draft not found or already approved")
        return {"data": updated, "requires_clinician_review": True}

    @app.post("/draft/{draft_id}/approve")
    def approve(draft_id: str, role: str = Depends(require_role)) -> dict[str, Any]:
        if role == "assistant":
            raise HTTPException(status_code=403, detail="Assistants cannot approve a draft")
        if get_draft(draft_id) is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        approved = approve_draft(draft_id, role)
        return {
            "data": approved,
            "answer": "Draft approved.",
            "requires_clinician_review": False,
        }

    return app


def require_role(x_user_role: Annotated[str | None, Header()] = None) -> str:
    """Read the demo role header. Missing means the least-privileged role."""

    if x_user_role is None or not x_user_role.strip():
        return "assistant"
    role = x_user_role.strip().lower()
    if role not in ROLES:
        raise HTTPException(
            status_code=400,
            detail="X-User-Role must be one of: dentist, radiologist, assistant",
        )
    return role


def _stt_detail(exc: Exception, settings_now: Any) -> str:
    """One log line. Strip a key if the SDK echoed it."""

    detail = str(exc).splitlines()[0][:160]
    for secret in (settings_now.groq_api_key, settings_now.gemini_api_key, settings_now.mistral_api_key):
        if secret:
            detail = detail.replace(secret, "[redacted]")
    return detail


def _audio_allowed(content_type: str | None, filename: str | None) -> bool:
    media = (content_type or "").split(";")[0].strip().lower()
    if media in ALLOWED_AUDIO:
        return True
    if media in {"", "application/octet-stream"}:
        return Path(filename or "").suffix.lower() in ALLOWED_EXTENSIONS
    return False


app = create_app()


def reload_runtime() -> None:
    """Reset cached settings and fixtures. Tests call this after env changes."""

    reset_settings()
    reset_stores()
    configure_logging(get_settings().log_level)
