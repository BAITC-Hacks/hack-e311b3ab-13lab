import argparse
import asyncio
import json
import os
import re
import shutil
import time
import uuid
from datetime import date
from pathlib import Path

from app.config import Settings
from app.pipeline import Provider, run_pipeline
from app.store import Store, now


async def main():
    parser = argparse.ArgumentParser(description="Run the real provider pipeline on a local meeting recording")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--meeting-date", type=date.fromisoformat, required=True)
    parser.add_argument("--credentials-file", type=Path)
    args = parser.parse_args()
    if args.credentials_file:
        match = re.search(r"sk-tq-[A-Za-z0-9]+", args.credentials_file.read_text())
        if not match:
            raise SystemExit("No provider key found")
        os.environ["TILQAZYNA_API_KEY"] = match.group()
    settings = Settings.from_env()
    store = Store(settings.data_dir)
    meeting_id = uuid.uuid4().hex
    audio_dir = settings.data_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    path = audio_dir / (meeting_id + args.audio.suffix.lower())
    shutil.copyfile(args.audio, path)
    store.create({"id": meeting_id, "title": args.audio.stem, "meeting_date": args.meeting_date.isoformat(), "status": "queued", "created_at": now(), "updated_at": now(), "version": 1, "audio_file": path.name, "transcript": "", "segments": [], "analysis": None, "speaker_names": {}, "error": None, "recording_consent": True})
    started = time.monotonic()
    await run_pipeline(meeting_id, store, settings, Provider(settings), asyncio.Semaphore(1))
    meeting = store.get(meeting_id)
    output = settings.data_dir / f"smoke-{meeting_id}.json"
    output.write_text(json.dumps(meeting, ensure_ascii=False, indent=2))
    print(json.dumps({"id": meeting_id, "status": meeting["status"], "elapsed_seconds": round(time.monotonic() - started, 1), "segments": len(meeting["segments"]), "actions": len(meeting["analysis"]["actions"]) if meeting["analysis"] else None, "error": meeting["error"], "output": str(output)}, ensure_ascii=False))
    if meeting["status"] != "ready":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
