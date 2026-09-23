"""Internal API used by the backend. Never exposed outside the compose network."""

import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field

from bot.adapters import ADAPTERS
from bot.browser import storage_state
from bot.session import BotSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
TOKEN = os.getenv("BOT_TOKEN", "")
MAX_SESSIONS = int(os.getenv("BOT_MAX_SESSIONS", "2"))
sessions: dict[str, BotSession] = {}
state = {}


@asynccontextmanager
async def lifespan(app):
    if len(TOKEN) < 16:
        raise RuntimeError("Set BOT_TOKEN (at least 16 characters)")
    state["playwright"] = await async_playwright().start()
    yield
    for session in list(sessions.values()):
        session.stop_requested.set()
    await asyncio.gather(*(session.task for session in sessions.values() if session.task), return_exceptions=True)
    await state["playwright"].stop()


app = FastAPI(title="HATTAMA.AI meeting bot", lifespan=lifespan)


def authorize(authorization: str):
    if not hmac.compare_digest(authorization, f"Bearer {TOKEN}"):
        raise HTTPException(401, "Unauthorized")


class SessionRequest(BaseModel):
    session_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    platform: str
    meeting_url: str = Field(max_length=2000)
    bot_name: str = Field(min_length=1, max_length=80)
    callback_url: str = Field(pattern=r"^wss?://")


@app.get("/health")
def health(authorization: str = Header(default="")):
    authorize(authorization)
    return {"ok": True, "sessions": {key: session.status for key, session in sessions.items()}, "accounts": {platform: bool(storage_state(platform)) for platform in ADAPTERS}}


@app.post("/sessions", status_code=202)
async def start(request: SessionRequest, authorization: str = Header(default="")):
    authorize(authorization)
    if request.platform not in ADAPTERS:
        raise HTTPException(422, "Unsupported platform")
    if request.platform == "google_meet" and not storage_state("google_meet"):
        raise HTTPException(409, "Google account for the bot is not signed in: run python -m bot.login google_meet")
    if request.session_id in sessions:
        raise HTTPException(409, "Session already running")
    if len(sessions) >= MAX_SESSIONS:
        raise HTTPException(429, "Bot is busy")
    session = BotSession(request.session_id, request.platform, request.meeting_url, request.bot_name, request.callback_url, TOKEN, state["playwright"])
    sessions[request.session_id] = session
    session.task = asyncio.create_task(session.run())
    session.task.add_done_callback(lambda _task: sessions.pop(request.session_id, None))
    return {"status": "starting"}


@app.delete("/sessions/{session_id}", status_code=202)
async def stop(session_id: str, authorization: str = Header(default="")):
    authorize(authorization)
    session = sessions.get(session_id)
    if session:
        session.stop_requested.set()
    return {"status": "stopping" if session else "not_running"}
