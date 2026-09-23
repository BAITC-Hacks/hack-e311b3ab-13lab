"""One bot in one meeting: join, stream audio and events to the backend, leave."""

import asyncio
import contextlib
import json
import logging
import os
import time
from pathlib import Path

import websockets

from bot.adapters import ADAPTERS
from bot.audio import MeetingSink
from bot.browser import launch, new_context

logger = logging.getLogger("bot")
ANNOUNCEMENT = "Ведётся запись и расшифровка совещания ИИ-секретарём HATTAMA.AI. Протокол проверит секретарь."
DEBUG_DIR = Path("/debug")


class BotSession:
    def __init__(self, session_id, platform, meeting_url, bot_name, callback_url, token, playwright):
        self.session_id = session_id
        self.adapter = ADAPTERS[platform]()
        self.meeting_url = meeting_url
        self.bot_name = bot_name
        self.callback_url = callback_url
        self.token = token
        self.playwright = playwright
        self.stop_requested = asyncio.Event()
        self.audio_seconds = 0.0
        self.joined = False
        self.task = None
        self.status = "starting"
        self.debug = os.getenv("BOT_DEBUG") == "1"
        self.lobby_timeout = int(os.getenv("BOT_LOBBY_TIMEOUT_SECONDS", "600"))

    async def run(self):
        sink = MeetingSink(self.session_id)
        browser = backend = None
        try:
            backend = await websockets.connect(self.callback_url, additional_headers={"Authorization": f"Bearer {self.token}"}, max_size=2**20, ping_interval=20)
            await self.send_status(backend, "joining")
            await sink.create()
            browser = await launch(self.playwright, sink.name)
            context = await new_context(browser, self.adapter.platform)
            page = await context.new_page()
            await self.adapter.join(page, self.meeting_url, self.bot_name)
            await self.snapshot(page, "requested")
            await self.watch(page, backend, sink)
        except Exception as error:
            logger.exception("Bot session failed")
            if backend:
                with contextlib.suppress(Exception):
                    await self.send_status(backend, "error", str(error) if isinstance(error, RuntimeError) else f"Ошибка бота ({type(error).__name__})")
        finally:
            if browser:
                with contextlib.suppress(Exception):
                    page = browser.contexts[0].pages[0] if browser.contexts and browser.contexts[0].pages else None
                    if page:
                        await self.adapter.leave(page)
                with contextlib.suppress(Exception):
                    await browser.close()
            await sink.close()
            if backend:
                with contextlib.suppress(Exception):
                    await backend.close()

    async def watch(self, page, backend, sink):
        requested = time.monotonic()
        last_status = None
        participants_sent = None
        speaking_now = set()
        next_roster = 0.0
        pump = None
        try:
            final_seen = 0
            while not self.stop_requested.is_set():
                state = await self.adapter.state(page)
                # Pages flash transitional messages; only a state that persists for ~5 s ends the session.
                if state in ("denied", "ended"):
                    final_seen += 1
                    if final_seen == 1:
                        logger.info("Bot %s sees %s: %s", self.session_id[:8], state, self.adapter.last_match[:240])
                    if final_seen < 4:
                        await asyncio.sleep(1.5)
                        continue
                else:
                    final_seen = 0
                if state != last_status:
                    last_status = state
                    await self.snapshot(page, state)
                    if state == "lobby":
                        await self.send_status(backend, "lobby", "Впустите бота из зала ожидания")
                    elif state == "joined" and not self.joined:
                        self.joined = True
                        await self.adapter.after_join(page)
                        await self.send_status(backend, "joined")
                        pump = asyncio.create_task(self.pump_audio(sink, backend))
                        if await self.adapter.announce(page, ANNOUNCEMENT):
                            logger.info("Recording notice posted in chat")
                    elif state == "denied":
                        await self.send_status(backend, "error", "Организатор не впустил бота во встречу")
                        return
                    elif state == "ended" or (state != "joined" and self.joined):
                        await self.send_status(backend, "ended", "Совещание завершено")
                        return
                if not self.joined and time.monotonic() - requested > self.lobby_timeout:
                    await self.send_status(backend, "error", "Бота не впустили во встречу за отведённое время")
                    return
                if self.joined:
                    if time.monotonic() >= next_roster:
                        next_roster = time.monotonic() + 5
                        roster = await self.adapter.participants(page)
                        if roster and roster != participants_sent:
                            participants_sent = roster
                            await backend.send(json.dumps({"type": "participants", "participants": roster}, ensure_ascii=False))
                    now_speaking = set(await self.adapter.speaking(page)) - {self.bot_name}
                    for name in now_speaking - speaking_now:
                        await backend.send(json.dumps({"type": "speaker", "id": name, "name": name, "at": round(self.audio_seconds, 2)}, ensure_ascii=False))
                    speaking_now = now_speaking
                if pump and pump.done():
                    return  # the backend connection or the recorder stopped
                await asyncio.sleep(0.5 if self.joined else 1.5)
        finally:
            if pump:
                pump.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await pump

    async def pump_audio(self, sink, backend):
        async for chunk in sink.chunks():
            await backend.send(chunk)
            self.audio_seconds += len(chunk) / 32000

    async def send_status(self, backend, status, detail=""):
        self.status = status
        await backend.send(json.dumps({"type": "status", "status": status, "detail": detail}, ensure_ascii=False))

    async def snapshot(self, page, label):
        if not self.debug:
            return
        folder = DEBUG_DIR / self.session_id
        folder.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(Exception):
            await page.screenshot(path=str(folder / f"{int(time.time())}-{label}.png"))
