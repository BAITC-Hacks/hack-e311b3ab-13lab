"""Private pyannote worker. Bind to loopback and reach through Teleport."""
import hmac
import os
import subprocess
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

os.environ.setdefault("PYANNOTE_METRICS_ENABLED", "0")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile

pipeline = None
startup_error = None
lock = threading.Lock()
MODEL = "pyannote/speaker-diarization-community-1"


@asynccontextmanager
async def lifespan(app):
    global pipeline, startup_error
    import torch
    from huggingface_hub import get_token
    from pyannote.audio import Pipeline
    if not os.environ.get("DIARIZATION_TOKEN"):
        raise RuntimeError("Set DIARIZATION_TOKEN before starting the service")
    try:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable")
        torch.cuda.set_per_process_memory_fraction(.10)
        pipeline = Pipeline.from_pretrained(MODEL, token=get_token())
        pipeline.to(torch.device("cuda"))
    except Exception as error:
        startup_error = type(error).__name__
        print("Model unavailable:", startup_error, flush=True)
    yield


app = FastAPI(title="Qorytyn GPU diarization", lifespan=lifespan)


@app.get("/health")
def health():
    import torch
    return {"ready": pipeline is not None, "model": MODEL,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "error": startup_error}


@app.post("/diarize")
def diarize(file: UploadFile = File(), num_speakers: int | None = Form(default=None),
            authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization, "Bearer " + os.environ.get("DIARIZATION_TOKEN", "")):
        raise HTTPException(401, "Unauthorized")
    if pipeline is None:
        raise HTTPException(503, "Model not ready; check Hugging Face model access")
    if num_speakers is not None and not 1 <= num_speakers <= 30:
        raise HTTPException(400, "Invalid speaker count")
    if not lock.acquire(blocking=False):
        raise HTTPException(429, "GPU worker is busy")
    try:
        with tempfile.TemporaryDirectory(prefix="qorytyn-") as directory:
            original = Path(directory) / "input.audio"
            wav = Path(directory) / "audio.wav"
            size = 0
            with original.open("wb") as target:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > 100 * 1024 * 1024:
                        raise HTTPException(413, "Maximum size is 100 MB")
                    target.write(chunk)
            try:
                # Decode one extra second to detect inputs above the demo limit.
                subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(original),
                    "-t", "601", "-ac", "1", "-ar", "16000", str(wav)],
                    capture_output=True, check=True, timeout=60)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                raise HTTPException(400, "Cannot decode audio")
            import soundfile as sf
            import torch
            samples, rate = sf.read(wav, dtype="float32")
            duration = len(samples) / rate
            if not 0 < duration <= 600:
                raise HTTPException(400, "Recording must be between 0 and 600 seconds")
            started = time.monotonic()
            kwargs = {"num_speakers": num_speakers} if num_speakers else {}
            with torch.inference_mode():
                result = pipeline({"waveform": torch.from_numpy(samples).unsqueeze(0), "sample_rate": rate}, **kwargs)
            annotation = result.exclusive_speaker_diarization
            turns = [{"start": max(0, turn.start), "end": min(duration, turn.end), "speaker_id": speaker}
                for turn, _, speaker in annotation.itertracks(yield_label=True)
                if min(duration, turn.end) > max(0, turn.start)]
            return {"turns": turns, "duration_seconds": duration, "model": MODEL,
                "gpu": torch.cuda.get_device_name(0), "elapsed_seconds": round(time.monotonic() - started, 2)}
    finally:
        file.file.close()
        lock.release()
