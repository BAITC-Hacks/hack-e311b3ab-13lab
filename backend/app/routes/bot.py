"""Internal socket for the meeting bot. nginx does not proxy /internal, and the backend
port is not published, so only services inside the compose network can reach it."""

import hmac
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.integrations.events import ActiveSpeaker, ConnectorStatus, Participant, ParticipantsChanged

router = APIRouter()
logger = logging.getLogger("hattama")
MAX_FRAME_BYTES = 64 * 1024
STATUSES = {"joining", "lobby", "joined", "ended", "error"}


def to_event(message: dict):
    kind = message.get("type")
    if kind == "status" and message.get("status") in STATUSES:
        return ConnectorStatus(message["status"], str(message.get("detail", ""))[:300])
    if kind == "participants" and isinstance(message.get("participants"), list):
        people = tuple(Participant(str(item.get("id", item.get("name", "")))[:120], str(item.get("name", ""))[:120]) for item in message["participants"][:300] if isinstance(item, dict) and item.get("name"))
        return ParticipantsChanged(people)
    if kind == "speaker" and message.get("name"):
        at = message.get("at")
        if isinstance(at, (int, float)) and at >= 0:
            return ActiveSpeaker(Participant(str(message.get("id", message["name"]))[:120], str(message["name"])[:120]), float(at))
    return None


@router.websocket("/internal/bot/{meeting_id}")
async def bot_socket(websocket: WebSocket, meeting_id: str):
    settings, live = websocket.app.state.settings, websocket.app.state.live
    token = websocket.headers.get("authorization", "")
    session = live.session(meeting_id)
    if not settings.bot_token or not hmac.compare_digest(token, f"Bearer {settings.bot_token}"):
        await websocket.close(4401)
        return
    if not session or session.connector.kind != "bot":
        await websocket.close(4404)
        return
    connector = session.connector
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if (data := message.get("bytes")) is not None:
                if len(data) <= MAX_FRAME_BYTES and len(data) % 2 == 0:
                    connector.push_audio(data)
                continue
            try:
                event = to_event(json.loads(message.get("text") or "{}"))
            except ValueError:
                event = None
            if event:
                connector.push_event(event)
    except WebSocketDisconnect:
        pass
    finally:
        connector.bot_disconnected()
