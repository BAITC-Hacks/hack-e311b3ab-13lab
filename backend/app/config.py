import os
from dataclasses import dataclass
from pathlib import Path


def _flag(name, default="false"):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    base_url: str
    api_key: str
    asr_model: str
    text_model: str
    max_upload_bytes: int
    timeout: float
    diarization_model_path: str
    diarization_url: str = ""
    diarization_token: str = ""
    database_url: str = ""
    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "hattama"
    minio_secure: bool = False
    session_hours: int = 12
    admin_email: str = ""
    admin_password: str = ""
    admin_name: str = "Администратор"
    pdf_font_path: str = ""
    pdf_font_bold_path: str = ""
    registration_mode: str = "approval"
    diarization_max_seconds: int = 600
    vad_model_path: str = ""
    live_max_sessions: int = 2
    live_max_minutes: int = 180
    live_idle_seconds: int = 120
    bot_service_url: str = ""
    bot_token: str = ""
    bot_name: str = "HATTAMA.AI Секретарь"
    bot_callback_base: str = "ws://backend:8000"
    text_base_url: str = ""
    text_api_key: str = ""
    text_enable_thinking: bool | None = None
    text_max_tokens: int = 12000
    text_chunk_chars: int = 16000

    @classmethod
    def from_env(cls):
        return cls(
            data_dir=Path(os.getenv("DATA_DIR", "data")),
            base_url=os.getenv("TILQAZYNA_BASE_URL", "https://router.tilqazyna.kz/v1").rstrip("/"),
            api_key=os.getenv("TILQAZYNA_API_KEY", ""),
            asr_model=os.getenv("ASR_MODEL", "til-asr"),
            text_model=os.getenv("TEXT_MODEL", "qwen"),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_MB", "100")) * 1024 * 1024,
            timeout=float(os.getenv("API_TIMEOUT_SECONDS", "900")),
            diarization_model_path=os.getenv("DIARIZATION_MODEL_PATH", ""),
            diarization_url=os.getenv("DIARIZATION_URL", "").rstrip("/"),
            diarization_token=os.getenv("DIARIZATION_TOKEN", ""),
            database_url=os.getenv("DATABASE_URL", ""),
            minio_endpoint=os.getenv("MINIO_ENDPOINT", ""),
            minio_access_key=os.getenv("MINIO_ACCESS_KEY", ""),
            minio_secret_key=os.getenv("MINIO_SECRET_KEY", ""),
            minio_bucket=os.getenv("MINIO_BUCKET", "hattama"),
            minio_secure=_flag("MINIO_SECURE"),
            session_hours=int(os.getenv("SESSION_HOURS", "12")),
            admin_email=os.getenv("ADMIN_EMAIL", ""),
            admin_password=os.getenv("ADMIN_PASSWORD", ""),
            admin_name=os.getenv("ADMIN_NAME", "Администратор"),
            pdf_font_path=os.getenv("PDF_FONT_PATH", ""),
            pdf_font_bold_path=os.getenv("PDF_FONT_BOLD_PATH", ""),
            registration_mode=os.getenv("REGISTRATION_MODE", "approval").strip().lower(),
            diarization_max_seconds=int(os.getenv("DIARIZATION_MAX_SECONDS", "600")),
            vad_model_path=os.getenv("VAD_MODEL_PATH", ""),
            live_max_sessions=int(os.getenv("LIVE_MAX_SESSIONS", "2")),
            live_max_minutes=int(os.getenv("LIVE_MAX_MINUTES", "180")),
            live_idle_seconds=int(os.getenv("LIVE_IDLE_SECONDS", "120")),
            bot_service_url=os.getenv("BOT_SERVICE_URL", "").rstrip("/"),
            bot_token=os.getenv("BOT_TOKEN", ""),
            bot_name=os.getenv("BOT_NAME", "HATTAMA.AI Секретарь"),
            bot_callback_base=os.getenv("BOT_CALLBACK_BASE", "ws://backend:8000").rstrip("/"),
            text_base_url=os.getenv("TEXT_BASE_URL", "").rstrip("/"),
            text_api_key=os.getenv("TEXT_API_KEY", ""),
            text_enable_thinking=None if not os.getenv("TEXT_ENABLE_THINKING", "") else _flag("TEXT_ENABLE_THINKING"),
            text_max_tokens=int(os.getenv("TEXT_MAX_TOKENS", "12000")),
            text_chunk_chars=int(os.getenv("TEXT_CHUNK_CHARS", "16000")),
        )
