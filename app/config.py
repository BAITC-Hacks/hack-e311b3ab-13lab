import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    base_url: str
    api_key: str
    asr_model: str
    text_model: str
    max_upload_bytes: int
    timeout: float
    app_token: str
    diarization_model_path: str

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
            app_token=os.getenv("APP_TOKEN", ""),
            diarization_model_path=os.getenv("DIARIZATION_MODEL_PATH", ""),
        )
