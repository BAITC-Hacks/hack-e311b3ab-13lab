import asyncio
import hmac
import uuid
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app import exports
from app.config import Settings
from app.models import Review
from app.pipeline import Provider, run_pipeline
from app.store import Store, now


def create_app(settings=None, provider=None):
    settings = settings or Settings.from_env()
    store = Store(settings.data_dir)
    provider = provider or Provider(settings)
    audio_dir = settings.data_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    tasks = set()
    semaphore = asyncio.Semaphore(1)

    @asynccontextmanager
    async def lifespan(application):
        for meeting in store.all():
            if meeting["status"] in {"queued", "transcribing", "diarizing", "analyzing"}:
                store.update(meeting["id"], {"status": "failed", "error": "Обработка прервана перезапуском сервера. Нажмите «Повторить»."})
        yield
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="13Lab · Qorytyn", lifespan=lifespan)
    app.state.store = store

    async def authorize(authorization: str = Header(default="")):
        if settings.app_token and not hmac.compare_digest(authorization, "Bearer " + settings.app_token):
            raise HTTPException(401, "Требуется токен доступа")

    def get_meeting(meeting_id):
        meeting = store.get(meeting_id)
        if not meeting:
            raise HTTPException(404, "Совещание не найдено")
        return meeting

    def schedule(meeting_id):
        task = asyncio.create_task(run_pipeline(meeting_id, store, settings, provider, semaphore))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "provider_configured": bool(settings.api_key), "diarization_configured": bool(settings.diarization_model_path), "authentication_required": bool(settings.app_token)}

    @app.get("/api/meetings", dependencies=[Depends(authorize)])
    async def meetings():
        return [{key: meeting[key] for key in ["id", "title", "meeting_date", "status", "created_at"]} for meeting in store.all()]

    @app.post("/api/meetings", status_code=202, dependencies=[Depends(authorize)])
    async def upload(title: str = Form(min_length=1, max_length=200), meeting_date: date = Form(), recording_consent: bool = Form(), audio: UploadFile = File()):
        if not recording_consent:
            raise HTTPException(400, "Подтвердите уведомление участников о записи и обработке")
        suffix = Path(audio.filename or "").suffix.lower()
        if suffix not in {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mp4"}:
            raise HTTPException(415, "Неподдерживаемый формат записи")
        if sum(meeting["status"] in {"queued", "transcribing", "diarizing", "analyzing"} for meeting in store.all()) >= 5:
            raise HTTPException(429, "Очередь заполнена, дождитесь завершения обработки")
        meeting_id = uuid.uuid4().hex
        path = audio_dir / (meeting_id + suffix)
        size = 0
        try:
            with path.open("xb") as target:
                while chunk := await audio.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise HTTPException(413, "Файл превышает лимит загрузки")
                    target.write(chunk)
            if size == 0:
                raise HTTPException(400, "Пустая запись")
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        finally:
            await audio.close()
        meeting = {"id": meeting_id, "title": title.strip(), "meeting_date": meeting_date.isoformat(), "status": "queued", "created_at": now(), "updated_at": now(), "version": 1, "audio_file": path.name, "transcript": "", "segments": [], "analysis": None, "speaker_names": {}, "error": None, "recording_consent": True}
        store.create(meeting)
        schedule(meeting_id)
        return meeting

    @app.get("/api/meetings/{meeting_id}", dependencies=[Depends(authorize)])
    async def detail(meeting_id: str):
        return get_meeting(meeting_id)

    @app.get("/api/meetings/{meeting_id}/audio", dependencies=[Depends(authorize)])
    async def audio_file(meeting_id: str):
        meeting = get_meeting(meeting_id)
        return FileResponse(audio_dir / meeting["audio_file"])

    @app.post("/api/meetings/{meeting_id}/retry", status_code=202, dependencies=[Depends(authorize)])
    async def retry(meeting_id: str):
        meeting = get_meeting(meeting_id)
        if meeting["status"] != "failed":
            raise HTTPException(409, "Повтор доступен только после ошибки")
        result = store.update(meeting_id, {"status": "queued", "error": None})
        schedule(meeting_id)
        return result

    @app.put("/api/meetings/{meeting_id}/review", dependencies=[Depends(authorize)])
    async def review(meeting_id: str, payload: Review):
        meeting = get_meeting(meeting_id)
        if meeting["status"] != "ready":
            raise HTTPException(409, "Дождитесь завершения обработки")
        try:
            return store.update(meeting_id, {"analysis": payload.analysis.model_dump(mode="json"), "speaker_names": payload.speaker_names}, payload.version)
        except ValueError:
            raise HTTPException(409, "Данные изменились. Обновите страницу перед сохранением.")

    @app.get("/api/meetings/{meeting_id}/export/{format}", dependencies=[Depends(authorize)])
    async def export(meeting_id: str, format: str):
        meeting = get_meeting(meeting_id)
        if meeting["status"] != "ready":
            raise HTTPException(409, "Протокол ещё не готов")
        headers = {"Content-Disposition": f'attachment; filename="protocol-{meeting_id}.{format}"'}
        if format == "md":
            return Response(exports.markdown(meeting), media_type="text/markdown; charset=utf-8", headers=headers)
        if format == "docx":
            return Response(exports.docx(meeting), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers=headers)
        if format == "json":
            import json

            return Response(json.dumps(meeting, ensure_ascii=False, indent=2), media_type="application/json", headers=headers)
        raise HTTPException(404, "Формат не поддерживается")

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def index():
        return FileResponse(static_dir / "index.html")

    return app
