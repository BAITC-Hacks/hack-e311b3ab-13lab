"""Live sessions: start and stop, WebSocket tickets, tab audio upload and live events."""

import asyncio
import contextlib
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.access import load_meeting, present_meeting
from app.integrations.factory import build_connector
from app.models import LiveStart
from app.rbac import MeetingPermission as MP, Permission, Role, current_user, meeting_permissions, require
from app.store import new_meeting, now

router = APIRouter()
logger = logging.getLogger("hattama")
MAX_FRAME_BYTES = 64 * 1024
CLOSE_UNAUTHORIZED = 4401
CLOSE_GONE = 4404


class TicketRequest(BaseModel):
    purpose: str


def _state(request_or_socket):
    state = request_or_socket.app.state
    return state.store, state.settings, state.live


@router.post("/api/live", status_code=201)
async def start_live(payload: LiveStart, request: Request, user=Depends(require(Permission.CREATE_MEETINGS))):
    store, settings, live = _state(request)
    if not payload.recording_consent:
        raise HTTPException(400, "Подтвердите, что участники уведомлены о записи и расшифровке ИИ")
    if live.active_count() >= settings.live_max_sessions:
        raise HTTPException(429, "Достигнут лимит одновременных онлайн-сессий")
    meeting = new_meeting(payload.title.strip(), payload.meeting_date.isoformat(), "", created_by=user["id"], chair_id=user["id"] if user["role"] == Role.CHAIR else None)
    url = (payload.meeting_url or "").strip()
    connector, platform = build_connector(payload.source, url, payload.platform, settings, meeting["id"])
    meeting.update(status="live", source={"type": payload.source, "platform": platform})
    meeting["live"] = {"status": "joining", "connector": payload.source, "platform": platform, "started_at": now(), "meeting_url": url, "bot_name": settings.bot_name if payload.source == "bot" else None}
    store.create(meeting)
    store.audit("live_session_started", user, meeting["id"], source=payload.source, platform=platform)
    live.start(meeting["id"], connector, url)
    return present_meeting(store, meeting, meeting_permissions(user, meeting))


@router.post("/api/live/{meeting_id}/stop")
async def stop_live(meeting_id: str, request: Request, user=Depends(current_user)):
    store, _, live = _state(request)
    meeting, permissions = load_meeting(store, meeting_id, user, MP.EDIT)
    if meeting["status"] != "live" or not live.stop(meeting_id):
        raise HTTPException(409, "Онлайн-сессия уже завершена")
    store.audit("live_session_stopped", user, meeting_id)
    return present_meeting(store, store.get(meeting_id), permissions)


@router.post("/api/live/{meeting_id}/ticket")
async def ticket(meeting_id: str, payload: TicketRequest, request: Request, user=Depends(current_user)):
    store, _, live = _state(request)
    if payload.purpose == "audio":
        meeting, _ = load_meeting(store, meeting_id, user, MP.EDIT)
        session = live.session(meeting_id)
        if not session or session.connector.kind != "tab":
            raise HTTPException(409, "Эта сессия не принимает звук из браузера")
    elif payload.purpose == "events":
        load_meeting(store, meeting_id, user, MP.READ)
    else:
        raise HTTPException(422, "purpose: audio или events")
    return {"ticket": live.issue_ticket(meeting_id, user["id"], payload.purpose)}


async def _authorize(websocket: WebSocket, meeting_id: str, purpose: str, needed):
    store, _, live = _state(websocket)
    user_id = live.redeem_ticket(websocket.query_params.get("ticket"), meeting_id, purpose)
    user = store.get_user(user_id) if user_id else None
    meeting = store.get(meeting_id)
    if not user or not user["active"] or not meeting or needed not in meeting_permissions(user, meeting):
        await websocket.close(CLOSE_UNAUTHORIZED)
        return None, None
    return user, meeting


@router.websocket("/api/live/{meeting_id}/audio")
async def audio_socket(websocket: WebSocket, meeting_id: str):
    user, _ = await _authorize(websocket, meeting_id, "audio", MP.EDIT)
    if not user:
        return
    session = websocket.app.state.live.session(meeting_id)
    if not session or session.connector.kind != "tab":
        await websocket.close(CLOSE_GONE)
        return
    await websocket.accept()
    try:
        while not session.stop_requested.is_set():
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data is None:
                continue  # text frames are keep-alives
            if len(data) > MAX_FRAME_BYTES or len(data) % 2:
                await websocket.close(1009)
                return
            if not session.connector.push_audio(data):
                await websocket.send_json({"type": "warning", "message": "Сервер не успевает обрабатывать звук"})
        with contextlib.suppress(RuntimeError):
            await websocket.send_json({"type": "stopped"})
            await websocket.close()
    except WebSocketDisconnect:
        pass  # the browser may reconnect; the idle watchdog ends abandoned sessions


@router.websocket("/api/live/{meeting_id}/events")
async def events_socket(websocket: WebSocket, meeting_id: str):
    user, meeting = await _authorize(websocket, meeting_id, "events", MP.READ)
    if not user:
        return
    store, _, live = _state(websocket)
    queue = live.hub.subscribe(meeting_id)
    await websocket.accept()

    async def watch_disconnect():
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            while (await websocket.receive())["type"] != "websocket.disconnect":
                pass

    closed = asyncio.create_task(watch_disconnect())
    try:
        await websocket.send_json({"type": "snapshot", "meeting": present_meeting(store, meeting, meeting_permissions(user, meeting))})
        if meeting["status"] != "live":
            await websocket.send_json({"type": "finished", "status": meeting["status"]})
            return
        while not closed.done():
            getter = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({getter, closed}, timeout=20, return_when=asyncio.FIRST_COMPLETED)
            if getter not in done:
                getter.cancel()
                if not closed.done():
                    await websocket.send_json({"type": "ping"})
                continue
            event = getter.result()
            await websocket.send_json(event)
            if event.get("type") == "finished":
                return
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Live events socket failed")
    finally:
        live.hub.unsubscribe(meeting_id, queue)
        closed.cancel()
        with contextlib.suppress(RuntimeError):
            await websocket.close()
