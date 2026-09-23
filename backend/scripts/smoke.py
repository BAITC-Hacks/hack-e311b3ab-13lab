import argparse
import asyncio
import json
import os
import re
import shutil
import time
from datetime import date
from pathlib import Path

from app.blobs import make_blob_store
from app.config import Settings
from app.pipeline import Provider, run_pipeline
from app.store import Store, new_meeting


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
    store = Store(settings)
    blobs = make_blob_store(settings)
    blobs.prepare()
    meeting = new_meeting(args.audio.stem, args.meeting_date.isoformat(), "")
    meeting["audio_key"] = f"audio/{meeting['id']}{args.audio.suffix.lower()}"
    staged = settings.data_dir / "tmp" / Path(meeting["audio_key"]).name
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.audio, staged)
    blobs.put_file(meeting["audio_key"], staged)
    store.create(meeting)
    started = time.monotonic()
    await run_pipeline(meeting["id"], store, settings, Provider(settings), asyncio.Semaphore(1), blobs)
    meeting = store.get(meeting["id"])
    output = settings.data_dir / f"smoke-{meeting['id']}.json"
    output.write_text(json.dumps(meeting, ensure_ascii=False, indent=2))
    print(json.dumps({"id": meeting["id"], "status": meeting["status"], "elapsed_seconds": round(time.monotonic() - started, 1), "segments": len(meeting["segments"]), "actions": len(meeting["analysis"]["actions"]) if meeting["analysis"] else None, "error": meeting["error"], "output": str(output)}, ensure_ascii=False))
    if meeting["status"] != "ready":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
