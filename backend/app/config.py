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
    database_url: str = ""
    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "qorytyn"
    minio_secure: bool = False
    session_hours: int = 12
    admin_email: str = ""
    admin_password: str = ""
    admin_name: str = "Администратор"
    pdf_font_path: str = ""
    pdf_font_bold_path: str = ""

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
            database_url=os.getenv("DATABASE_URL", ""),
            minio_endpoint=os.getenv("MINIO_ENDPOINT", ""),
            minio_access_key=os.getenv("MINIO_ACCESS_KEY", ""),
            minio_secret_key=os.getenv("MINIO_SECRET_KEY", ""),
            minio_bucket=os.getenv("MINIO_BUCKET", "qorytyn"),
            minio_secure=_flag("MINIO_SECURE"),
            session_hours=int(os.getenv("SESSION_HOURS", "12")),
            admin_email=os.getenv("ADMIN_EMAIL", ""),
            admin_password=os.getenv("ADMIN_PASSWORD", ""),
            admin_name=os.getenv("ADMIN_NAME", "Администратор"),
            pdf_font_path=os.getenv("PDF_FONT_PATH", ""),
            pdf_font_bold_path=os.getenv("PDF_FONT_BOLD_PATH", ""),
        )
