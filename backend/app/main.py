import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import exports
from app.blobs import make_blob_store, media_type
from app.config import Settings
from app.models import ACTIVE_STATUSES, REVIEWABLE_STATUSES, ActionUpdate, Approval, LoginRequest, PasswordChange, People, Review, UserCreate, UserUpdate
from app.pipeline import Provider, run_pipeline
from app.rbac import ROLE_LABELS, MeetingPermission as MP, Permission, Role, assignee_ids, current_user, meeting_permissions, require, role_permissions
from app.security import DUMMY_HASH, verify_password
from app.store import Store, audio_key, new_meeting, now

logger = logging.getLogger("qorytyn")

AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mp4"}
INTERRUPTED = "Обработка прервана перезапуском сервера. Нажмите «Повторить»."
SUMMARY_FIELDS = ("id", "title", "meeting_date", "status", "created_at", "updated_at", "version", "error", "created_by", "chair_id", "participant_ids", "approved_at", "approved_by")
CONTENT_FIELDS = ("transcript", "segments", "analysis", "speaker_names")
CSP = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"


class LoginThrottle:
    """Blocks a login key (email + client address) after repeated failures."""

    def __init__(self, limit=5, window_seconds=900):
        self.limit = limit
        self.window = window_seconds
        self.failures = defaultdict(deque)

    def _recent(self, key):
        attempts = self.failures[key]
        while attempts and attempts[0] < time.monotonic() - self.window:
            attempts.popleft()
        if not attempts:
            self.failures.pop(key, None)
        return attempts

    def blocked(self, key):
        return len(self._recent(key)) >= self.limit

    def fail(self, key):
        self._recent(key)
        self.failures[key].append(time.monotonic())

    def reset(self, key):
        self.failures.pop(key, None)


def describe_user(user):
    return {**user, "role_label": ROLE_LABELS.get(user["role"], user["role"]), "permissions": sorted(role_permissions(user))}


def create_app(settings=None, provider=None, store=None, blobs=None):
    settings = settings or Settings.from_env()
    store = store or Store(settings)
    blobs = blobs or make_blob_store(settings)
    provider = provider or Provider(settings)
    fonts = exports.find_fonts(settings)
    tmp_dir = settings.data_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tasks = set()
    semaphore = asyncio.Semaphore(1)
    throttle = LoginThrottle()

    def bootstrap_admin():
        if store.count_users(Role.ADMIN):
            return
        if settings.admin_email and settings.admin_password:
            user = store.create_user(settings.admin_email, settings.admin_name, Role.ADMIN, settings.admin_password)
            store.audit("user_created", meeting_id=None, email=user["email"], role=user["role"], source="bootstrap")
            logger.warning("Создан администратор %s из ADMIN_EMAIL/ADMIN_PASSWORD", user["email"])
        else:
            logger.warning("Нет активного администратора. Задайте ADMIN_EMAIL и ADMIN_PASSWORD или выполните python -m scripts.create_user")

    @asynccontextmanager
    async def lifespan(application):
        await asyncio.to_thread(blobs.prepare)
        store.mark_interrupted(INTERRUPTED)
        bootstrap_admin()
        yield
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="13Lab · Qorytyn", lifespan=lifespan)
    app.state.store = store
    app.state.blobs = blobs
    app.state.settings = settings

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        path = request.url.path
        if path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        if not path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers.setdefault("Content-Security-Policy", CSP)
            response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    def load(meeting_id, user, needed=MP.VIEW):
        meeting = store.get(meeting_id)
        permissions = meeting_permissions(user, meeting) if meeting else frozenset()
        if MP.VIEW not in permissions:
            raise HTTPException(404, "Совещание не найдено")
        if needed not in permissions:
            raise HTTPException(403, "Недостаточно прав для этого действия")
        return meeting, permissions

    def people_for(meeting, names):
        ids = {meeting.get("created_by"), meeting.get("chair_id"), meeting.get("approved_by"), *meeting.get("participant_ids", []), *assignee_ids(meeting)}
        ids |= {approval.get("approved_by") for approval in meeting.get("approvals", [])}
        return {user_id: names[user_id] for user_id in ids if user_id in names}

    def present(meeting, permissions):
        result = {field: meeting.get(field) for field in SUMMARY_FIELDS}
        result["participant_ids"] = result["participant_ids"] or []
        result["permissions"] = sorted(permissions)
        result["people"] = people_for(meeting, store.user_names())
        result["approvals"] = [{key: value for key, value in approval.items() if key != "files"} | {"formats": sorted(approval.get("files", {}))} for approval in meeting.get("approvals", [])]
        if MP.READ in permissions:
            result.update({field: meeting.get(field) for field in CONTENT_FIELDS})
        return result

    def schedule(meeting_id):
        task = asyncio.create_task(run_pipeline(meeting_id, store, settings, provider, semaphore, blobs))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    def active_user(user_id, message):
        user = store.get_user(user_id)
        if not user or not user["active"]:
            raise HTTPException(422, message)
        return user

    # Health and authentication

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "provider_configured": bool(settings.api_key), "diarization_configured": bool(settings.diarization_model_path), "pdf_configured": bool(fonts)}

    @app.post("/api/auth/login")
    async def login(payload: LoginRequest, request: Request):
        email = payload.email.strip().lower()
        key = (email, request.client.host if request.client else "")
        if throttle.blocked(key):
            raise HTTPException(429, "Слишком много неудачных попыток. Повторите через 15 минут.")
        found = store.user_credentials(email)
        valid = await asyncio.to_thread(verify_password, payload.password, found[1] if found else DUMMY_HASH)
        if not (found and valid and found[0]["active"]):
            throttle.fail(key)
            store.audit("login_failed", email=email)
            raise HTTPException(401, "Неверный email или пароль")
        throttle.reset(key)
        user = found[0]
        token, expires_at = store.create_session(user["id"])
        store.audit("login", user)
        return {"token": token, "expires_at": expires_at, "user": describe_user(user)}

    @app.post("/api/auth/logout", status_code=204)
    async def logout(request: Request, user=Depends(current_user)):
        store.delete_session(request.state.token)
        store.audit("logout", user)
        return Response(status_code=204)

    @app.get("/api/auth/me")
    async def me(user=Depends(current_user)):
        return describe_user(user)

    @app.post("/api/auth/password")
    async def change_password(payload: PasswordChange, user=Depends(current_user)):
        _, password_hash = store.user_credentials(user["email"])
        if not await asyncio.to_thread(verify_password, payload.current_password, password_hash):
            raise HTTPException(400, "Текущий пароль указан неверно")
        store.update_user(user["id"], password=payload.new_password)
        token, expires_at = store.create_session(user["id"])
        store.audit("password_changed", user)
        return {"token": token, "expires_at": expires_at}

    # Users

    @app.get("/api/users")
    async def list_users(user=Depends(require(Permission.MANAGE_USERS))):
        return [describe_user(item) for item in store.list_users()]

    @app.get("/api/users/directory")
    async def directory(user=Depends(require(Permission.READ_DIRECTORY))):
        return [{"id": item["id"], "name": item["name"], "role": item["role"], "role_label": ROLE_LABELS[item["role"]]} for item in store.list_users() if item["active"]]

    @app.post("/api/users", status_code=201)
    async def create_user(payload: UserCreate, user=Depends(require(Permission.MANAGE_USERS))):
        try:
            created = store.create_user(payload.email, payload.name, payload.role, payload.password)
        except ValueError:
            raise HTTPException(409, "Пользователь с таким email уже существует")
        store.audit("user_created", user, email_created=created["email"], role=created["role"])
        return describe_user(created)

    @app.patch("/api/users/{user_id}")
    async def update_user(user_id: str, payload: UserUpdate, user=Depends(require(Permission.MANAGE_USERS))):
        target = store.get_user(user_id)
        if not target:
            raise HTTPException(404, "Пользователь не найден")
        losing_admin = target["role"] == Role.ADMIN and target["active"] and ((payload.role and payload.role != Role.ADMIN) or payload.active is False)
        if losing_admin and store.count_users(Role.ADMIN) <= 1:
            raise HTTPException(409, "Нельзя отключить или понизить последнего администратора")
        updated = store.update_user(user_id, name=payload.name, role=payload.role, active=payload.active, password=payload.password)
        changed = sorted(field for field, value in payload.model_dump(exclude_none=True).items())
        store.audit("user_updated", user, target=updated["email"], fields=changed, role=updated["role"], active=updated["active"])
        return describe_user(updated)

    # Audit log

    @app.get("/api/audit")
    async def audit(meeting_id: str | None = None, limit: int = Query(200, ge=1, le=1000), user=Depends(require(Permission.READ_AUDIT))):
        return store.audit_entries(meeting_id, limit)

    # Meetings

    @app.get("/api/meetings")
    async def meetings(user=Depends(current_user)):
        result = []
        for meeting in store.all():
            permissions = meeting_permissions(user, meeting)
            if MP.VIEW in permissions:
                result.append({key: meeting[key] for key in ("id", "title", "meeting_date", "status", "created_at")} | {"permissions": sorted(permissions)})
        return result

    @app.post("/api/meetings", status_code=202)
    async def upload(
        title: str = Form(min_length=1, max_length=200),
        meeting_date: date = Form(),
        recording_consent: bool = Form(),
        audio: UploadFile = File(),
        user=Depends(require(Permission.CREATE_MEETINGS)),
    ):
        if not recording_consent:
            raise HTTPException(400, "Подтвердите уведомление участников о записи и обработке")
        suffix = Path(audio.filename or "").suffix.lower()
        if suffix not in AUDIO_SUFFIXES:
            raise HTTPException(415, "Неподдерживаемый формат записи")
        if store.count_active() >= 5:
            raise HTTPException(429, "Очередь заполнена, дождитесь завершения обработки")
        upload_path = tmp_dir / (uuid.uuid4().hex + suffix)
        size = 0
        try:
            with upload_path.open("xb") as target:
                while chunk := await audio.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise HTTPException(413, "Файл превышает лимит загрузки")
                    target.write(chunk)
            if size == 0:
                raise HTTPException(400, "Пустая запись")
        except BaseException:
            upload_path.unlink(missing_ok=True)
            raise
        finally:
            await audio.close()
        meeting = new_meeting(title.strip(), meeting_date.isoformat(), "", created_by=user["id"], chair_id=user["id"] if user["role"] == Role.CHAIR else None)
        meeting["audio_key"] = f"audio/{meeting['id']}{suffix}"
        try:
            await asyncio.to_thread(blobs.put_file, meeting["audio_key"], upload_path)
        except Exception:
            upload_path.unlink(missing_ok=True)
            logger.exception("Audio upload to storage failed")
            raise HTTPException(503, "Хранилище записей недоступно")
        store.create(meeting)
        store.audit("meeting_created", user, meeting["id"], title=meeting["title"], size_bytes=size)
        schedule(meeting["id"])
        return present(meeting, meeting_permissions(user, meeting))

    @app.get("/api/meetings/{meeting_id}")
    async def detail(meeting_id: str, user=Depends(current_user)):
        meeting, permissions = load(meeting_id, user)
        return present(meeting, permissions)

    @app.get("/api/meetings/{meeting_id}/audio")
    async def audio_file(meeting_id: str, user=Depends(current_user)):
        meeting, _ = load(meeting_id, user, MP.LISTEN)
        key = audio_key(meeting)
        if not await asyncio.to_thread(blobs.exists, key):
            raise HTTPException(404, "Запись не найдена в хранилище")
        store.audit("audio_opened", user, meeting_id)
        local = blobs.local_path(key)
        if local:
            return FileResponse(local, media_type=media_type(key))
        return StreamingResponse(await asyncio.to_thread(blobs.open_stream, key), media_type=media_type(key))

    @app.post("/api/meetings/{meeting_id}/retry", status_code=202)
    async def retry(meeting_id: str, user=Depends(current_user)):
        meeting, permissions = load(meeting_id, user, MP.RETRY)
        if meeting["status"] != "failed":
            raise HTTPException(409, "Повтор доступен только после ошибки")
        result = store.update(meeting_id, {"status": "queued", "error": None})
        store.audit("meeting_retried", user, meeting_id)
        schedule(meeting_id)
        return present(result, permissions)

    @app.put("/api/meetings/{meeting_id}/review")
    async def review(meeting_id: str, payload: Review, user=Depends(current_user)):
        meeting, permissions = load(meeting_id, user, MP.EDIT)
        if meeting["status"] == "approved":
            raise HTTPException(409, "Протокол утверждён. Верните его на доработку, чтобы изменить.")
        if meeting["status"] != "ready":
            raise HTTPException(409, "Дождитесь завершения обработки")
        seen = set()
        for action in payload.analysis.actions:
            if not action.id or action.id in seen:
                action.id = uuid.uuid4().hex[:12]
            seen.add(action.id)
            if action.assignee_id:
                active_user(action.assignee_id, f"Исполнитель для «{action.title[:60]}» не найден или отключён")
        try:
            result = store.update(meeting_id, {"analysis": payload.analysis.model_dump(mode="json"), "speaker_names": payload.speaker_names}, payload.version)
        except ValueError:
            raise HTTPException(409, "Данные изменились. Обновите страницу перед сохранением.")
        store.audit("review_saved", user, meeting_id, version=result["version"])
        return present(result, permissions)

    @app.put("/api/meetings/{meeting_id}/people")
    async def people(meeting_id: str, payload: People, user=Depends(current_user)):
        meeting, _ = load(meeting_id, user, MP.PEOPLE)
        if payload.chair_id:
            chair = active_user(payload.chair_id, "Председатель не найден или отключён")
            if chair["role"] != Role.CHAIR:
                raise HTTPException(422, "Председателем может быть только пользователь с ролью «Председатель»")
        participants = list(dict.fromkeys(payload.participant_ids))
        for participant_id in participants:
            active_user(participant_id, "Участник не найден или отключён")
        result = store.update(meeting_id, {"chair_id": payload.chair_id, "participant_ids": participants})
        store.audit("people_updated", user, meeting_id, chair_id=payload.chair_id, participants=len(participants))
        return present(result, meeting_permissions(user, result))

    @app.patch("/api/meetings/{meeting_id}/actions/{action_id}")
    async def update_action(meeting_id: str, action_id: str, payload: ActionUpdate, user=Depends(current_user)):
        meeting, permissions = load(meeting_id, user)
        if meeting["status"] not in REVIEWABLE_STATUSES:
            raise HTTPException(409, "Поручения ещё не готовы")
        actions = (meeting.get("analysis") or {}).get("actions", [])
        action = next((item for item in actions if item.get("id") == action_id), None)
        own = action is not None and meeting["status"] == "approved" and action.get("assignee_id") == user["id"]
        if MP.TRACK not in permissions and not own:
            raise HTTPException(403 if action else 404, "Недостаточно прав для этого поручения" if action else "Поручение не найдено")
        if action is None:
            raise HTTPException(404, "Поручение не найдено")

        def change(document):
            target = next((item for item in document["analysis"]["actions"] if item.get("id") == action_id), None)
            if target is None:
                raise LookupError(action_id)
            target["status"] = payload.status

        try:
            result = store.update(meeting_id, change)
        except LookupError:
            raise HTTPException(404, "Поручение не найдено")
        store.audit("action_status_changed", user, meeting_id, action_id=action_id, status=payload.status)
        return present(result, meeting_permissions(user, result))

    @app.post("/api/meetings/{meeting_id}/approve")
    async def approve(meeting_id: str, payload: Approval, user=Depends(current_user)):
        meeting, _ = load(meeting_id, user, MP.APPROVE)
        if meeting["status"] != "ready":
            raise HTTPException(409, "Утвердить можно только проверенный черновик")
        if meeting["version"] != payload.version:
            raise HTTPException(409, "Данные изменились. Обновите страницу перед утверждением.")
        approved_at = now()
        next_version = payload.version + 1
        snapshot = meeting | {"status": "approved", "approved_at": approved_at, "approved_by": user["id"]}
        names = store.user_names()
        rendered = {"docx": exports.docx(snapshot, names)}
        warnings = []
        if fonts:
            rendered["pdf"] = exports.pdf(snapshot, fonts, names)
        else:
            warnings.append("PDF не сохранён: не найден шрифт с кириллицей. Укажите PDF_FONT_PATH.")
        files = {fmt: f"protocols/{meeting_id}/v{next_version}.{fmt}" for fmt in rendered}
        try:
            for fmt, data in rendered.items():
                await asyncio.to_thread(blobs.put_bytes, files[fmt], data)
        except Exception:
            logger.exception("Protocol archive upload failed")
            raise HTTPException(503, "Хранилище протоколов недоступно")

        def change(document):
            document.update({"status": "approved", "approved_at": approved_at, "approved_by": user["id"]})
            document.setdefault("approvals", []).append({"version": next_version, "approved_at": approved_at, "approved_by": user["id"], "files": files})

        try:
            result = store.update(meeting_id, change, payload.version)
        except ValueError:
            for key in files.values():
                await asyncio.to_thread(blobs.delete, key)
            raise HTTPException(409, "Данные изменились. Обновите страницу перед утверждением.")
        store.audit("meeting_approved", user, meeting_id, version=result["version"], files=sorted(files))
        return present(result, meeting_permissions(user, result)) | {"warnings": warnings}

    @app.get("/api/meetings/{meeting_id}/approved/{format}")
    async def approved_file(meeting_id: str, format: str, user=Depends(current_user)):
        meeting, _ = load(meeting_id, user, MP.EXPORT)
        approvals = meeting.get("approvals", [])
        key = approvals[-1].get("files", {}).get(format) if approvals else None
        if not key:
            raise HTTPException(404, "Утверждённая копия в этом формате не найдена")
        if not await asyncio.to_thread(blobs.exists, key):
            raise HTTPException(404, "Утверждённая копия не найдена в хранилище")
        data = await asyncio.to_thread(blobs.get_bytes, key)
        store.audit("approved_copy_downloaded", user, meeting_id, format=format, version=approvals[-1]["version"])
        headers = {"Content-Disposition": f'attachment; filename="protocol-{meeting_id}-v{approvals[-1]["version"]}.{format}"'}
        return Response(data, media_type=media_type(key), headers=headers)

    @app.post("/api/meetings/{meeting_id}/reopen")
    async def reopen(meeting_id: str, user=Depends(current_user)):
        meeting, permissions = load(meeting_id, user, MP.REOPEN)
        if meeting["status"] != "approved":
            raise HTTPException(409, "Протокол не утверждён")
        result = store.update(meeting_id, {"status": "ready", "approved_at": None, "approved_by": None})
        store.audit("meeting_reopened", user, meeting_id)
        return present(result, permissions)

    @app.get("/api/meetings/{meeting_id}/export/{format}")
    async def export(meeting_id: str, format: str, user=Depends(current_user)):
        meeting, permissions = load(meeting_id, user, MP.EXPORT)
        if meeting["status"] not in REVIEWABLE_STATUSES:
            raise HTTPException(409, "Протокол ещё не готов")
        if format == "json" and MP.EXPORT_RAW not in permissions:
            raise HTTPException(403, "Полная выгрузка JSON доступна только редакторам протокола")
        names = store.user_names()
        headers = {"Content-Disposition": f'attachment; filename="protocol-{meeting_id}.{format}"'}
        if format == "md":
            response = Response(exports.markdown(meeting, names), media_type="text/markdown; charset=utf-8", headers=headers)
        elif format == "docx":
            response = Response(exports.docx(meeting, names), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers=headers)
        elif format == "pdf":
            if not fonts:
                raise HTTPException(503, "PDF недоступен: не найден шрифт с кириллицей. Укажите PDF_FONT_PATH.")
            response = Response(exports.pdf(meeting, fonts, names), media_type="application/pdf", headers=headers)
        elif format == "json":
            response = Response(json.dumps(meeting, ensure_ascii=False, indent=2), media_type="application/json", headers=headers)
        else:
            raise HTTPException(404, "Формат не поддерживается")
        store.audit("meeting_exported", user, meeting_id, format=format)
        return response

    @app.delete("/api/meetings/{meeting_id}", status_code=204)
    async def delete_meeting(meeting_id: str, user=Depends(current_user)):
        meeting, _ = load(meeting_id, user, MP.DELETE)
        if meeting["status"] in ACTIVE_STATUSES:
            raise HTTPException(409, "Дождитесь завершения обработки перед удалением")
        await asyncio.to_thread(blobs.delete, audio_key(meeting))
        await asyncio.to_thread(blobs.delete_prefix, f"protocols/{meeting_id}")
        store.delete(meeting_id)
        store.audit("meeting_deleted", user, meeting_id, title=meeting["title"])
        return Response(status_code=204)

    @app.get("/api/me/actions")
    async def my_actions(user=Depends(current_user)):
        result = []
        for meeting in store.all():
            if meeting["status"] != "approved":
                continue
            for action in (meeting.get("analysis") or {}).get("actions", []):
                if action.get("assignee_id") == user["id"]:
                    result.append({"meeting_id": meeting["id"], "meeting_title": meeting["title"], "meeting_date": meeting["meeting_date"], "action": action})
        return result

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def index():
        return FileResponse(static_dir / "index.html")

    return app
