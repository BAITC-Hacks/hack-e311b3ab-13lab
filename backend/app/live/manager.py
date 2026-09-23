"""Live meeting sessions.

A session consumes any MeetingConnector: audio is appended to DATA_DIR/live/<id>.pcm,
cut into speech windows and transcribed window by window with the regular ASR
provider. When the session ends the audio becomes a normal recording and the
transcript is stored as `asr_segments`, so `run_pipeline` reuses it instead of
transcribing again and continues with diarization, extraction and review.
"""

import asyncio
import logging
import secrets
import time
import uuid
import wave
from collections import defaultdict
from pathlib import Path

import httpx

from app.integrations.events import BYTES_PER_SAMPLE, SAMPLE_RATE, ActiveSpeaker, ConnectorStatus, ParticipantsChanged
from app.live.vad import make_vad
from app.live.windows import Windower
from app.models import Segment
from app.store import now

logger = logging.getLogger("hattama")
TICKET_SECONDS = 30
INTERRUPTED = "Онлайн-сессия прервана перезапуском сервера. Записанная часть сохранена: нажмите «Повторить», чтобы подготовить протокол."


class LiveHub:
    """In-process fan-out of live events to WebSocket viewers."""

    def __init__(self):
        self._subscribers = defaultdict(set)

    def subscribe(self, meeting_id):
        queue = asyncio.Queue(maxsize=500)
        self._subscribers[meeting_id].add(queue)
        return queue

    def unsubscribe(self, meeting_id, queue):
        self._subscribers[meeting_id].discard(queue)
        if not self._subscribers[meeting_id]:
            self._subscribers.pop(meeting_id, None)

    def publish(self, meeting_id, event):
        for queue in list(self._subscribers.get(meeting_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:  # a stalled viewer reloads the snapshot instead
                pass


def pcm_to_wav(pcm_path: Path, wav_path: Path) -> float:
    """Wrap raw PCM16 mono 16 kHz in a WAV container; returns the duration in seconds."""
    with pcm_path.open("rb") as source, wave.open(str(wav_path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(BYTES_PER_SAMPLE)
        target.setframerate(SAMPLE_RATE)
        while chunk := source.read(1 << 20):
            target.writeframes(chunk)
    return pcm_path.stat().st_size / (SAMPLE_RATE * BYTES_PER_SAMPLE)


class LiveSession:
    def __init__(self, manager, meeting_id, connector, meeting_url=""):
        self.manager = manager
        self.meeting_id = meeting_id
        self.connector = connector
        self.meeting_url = meeting_url
        settings = manager.settings
        self.pcm_path = settings.data_dir / "live" / f"{meeting_id}.pcm"
        self.pcm_path.parent.mkdir(parents=True, exist_ok=True)
        self.windower = Windower(make_vad(settings.vad_model_path))
        self.windows: asyncio.Queue = asyncio.Queue()
        self.stop_requested = asyncio.Event()
        self.stop_reason = ""
        self.started = time.monotonic()
        self.last_audio = time.monotonic()
        self.audio_seconds = 0.0
        self.failed_windows = 0
        self.speaker_events = []
        self.participants = {}
        self.status = "joining"
        self.task = None

    def request_stop(self, reason=""):
        if not self.stop_requested.is_set():
            self.stop_reason = reason
            self.stop_requested.set()

    def publish(self, event):
        self.manager.hub.publish(self.meeting_id, event)

    def set_status(self, status, detail=""):
        self.status = status
        self.manager.update_live(self.meeting_id, status=status, detail=detail)
        self.publish({"type": "status", "status": status, "detail": detail})

    async def run(self):
        consumers, asr, interrupted = [], None, False
        try:
            await self.connector.join(self.meeting_url)
            if self.connector.kind == "tab":
                self.set_status("waiting_audio")
            consumers = [
                asyncio.create_task(self._consume_audio()),
                asyncio.create_task(self._consume_events()),
                asyncio.create_task(self._watchdog()),
            ]
            asr = asyncio.create_task(self._transcribe_windows())
            await self.stop_requested.wait()
        except asyncio.CancelledError:
            interrupted = True  # the server is shutting down: keep what was captured
        except Exception as error:
            logger.exception("Live session failed")
            self.stop_reason = self.stop_reason or f"Ошибка подключения ({type(error).__name__})"
        finally:
            await self._shutdown(consumers, asr, interrupted)

    async def _shutdown(self, consumers, asr, interrupted):
        try:
            await self.connector.leave()
        except Exception:
            logger.exception("Connector leave failed")
        for task in consumers:
            task.cancel()
        await asyncio.gather(*consumers, return_exceptions=True)
        for window in self.windower.flush():
            self.windows.put_nowait(window)
        self.windows.put_nowait(None)
        if asr is not None:
            if interrupted:
                asr.cancel()
            try:
                await asyncio.wait_for(asr, timeout=None if not interrupted else 1)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        await asyncio.shield(self.manager.finalize(self, interrupted))

    async def _consume_audio(self):
        limit = self.manager.settings.live_max_minutes * 60
        with self.pcm_path.open("ab") as target:
            async for chunk in self.connector.stream_audio():
                target.write(chunk.pcm)
                self.audio_seconds += chunk.seconds
                self.last_audio = time.monotonic()
                if self.status in ("joining", "waiting_audio", "lobby"):
                    self.set_status("live")
                for window in self.windower.feed(chunk.pcm):
                    self.windows.put_nowait(window)
                if self.audio_seconds >= limit:
                    self.request_stop("Достигнута максимальная длительность онлайн-сессии")
                    break
        self.request_stop(self.stop_reason or "Источник звука завершил передачу")

    async def _consume_events(self):
        async for event in self.connector.events():
            if isinstance(event, ConnectorStatus):
                self.set_status(event.status, event.detail)
                if event.status in ("ended", "error"):
                    self.request_stop(event.detail or ("Совещание завершено" if event.status == "ended" else "Ошибка подключения"))
            elif isinstance(event, ParticipantsChanged):
                for participant in event.participants:
                    self.participants[participant.platform_id] = participant.name
                seen = [{"platform_id": key, "name": value} for key, value in self.participants.items()]
                self.manager.store.update(self.meeting_id, {"participants_seen": seen})
                self.publish({"type": "participants", "participants": seen, "present": [item.platform_id for item in event.participants]})
            elif isinstance(event, ActiveSpeaker):
                self.participants.setdefault(event.participant.platform_id, event.participant.name)
                self.speaker_events.append({"at": round(event.at, 2), "platform_id": event.participant.platform_id, "name": event.participant.name})
                self.publish({"type": "speaker", "name": event.participant.name, "platform_id": event.participant.platform_id, "at": event.at})

    async def _watchdog(self):
        idle = self.manager.settings.live_idle_seconds
        while True:
            await asyncio.sleep(2)
            silent_for = time.monotonic() - self.last_audio
            if self.connector.kind == "tab" and silent_for > idle:
                self.request_stop("Звук из вкладки не поступает")
                return

    async def _transcribe_windows(self):
        provider = self.manager.provider
        tmp_dir = self.manager.settings.data_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        while (window := await self.windows.get()) is not None:
            path = tmp_dir / f"live-{self.meeting_id}-{uuid.uuid4().hex[:8]}.wav"
            try:
                with wave.open(str(path), "wb") as target:
                    target.setnchannels(1)
                    target.setsampwidth(BYTES_PER_SAMPLE)
                    target.setframerate(SAMPLE_RATE)
                    target.writeframes(window.pcm)
                _, segments = await provider.transcribe(path)
            except RuntimeError:
                continue  # the ASR found no words in this window
            except (httpx.HTTPError, ValueError) as error:
                self.failed_windows += 1
                self.publish({"type": "warning", "message": f"Фрагмент {window.start:.0f}–{window.start + window.seconds:.0f} с не распознан ({type(error).__name__})"})
                continue
            finally:
                path.unlink(missing_ok=True)
            shifted = [shift_segment(segment, window.start) for segment in segments]
            self.manager.append_segments(self.meeting_id, shifted)
            self.publish({"type": "segments", "segments": [segment.model_dump(exclude={"words"}) for segment in shifted], "lag_seconds": round(max(0.0, self.audio_seconds - (window.start + window.seconds)), 1)})


def shift_segment(segment: Segment, offset: float) -> Segment:
    shifted = segment.model_copy(deep=True)
    if shifted.start is not None:
        shifted.start = round(shifted.start + offset, 3)
    if shifted.end is not None:
        shifted.end = round(shifted.end + offset, 3)
    for word in shifted.words:
        word.start = round(word.start + offset, 3)
        word.end = round(word.end + offset, 3)
    return shifted


class LiveManager:
    def __init__(self, store, settings, provider, blobs, schedule):
        self.store = store
        self.settings = settings
        self.provider = provider
        self.blobs = blobs
        self.schedule = schedule
        self.hub = LiveHub()
        self.sessions: dict[str, LiveSession] = {}
        self._tickets: dict[str, tuple] = {}

    def active_count(self):
        return len(self.sessions)

    def session(self, meeting_id):
        return self.sessions.get(meeting_id)

    def start(self, meeting_id, connector, meeting_url=""):
        session = LiveSession(self, meeting_id, connector, meeting_url)
        self.sessions[meeting_id] = session
        session.task = asyncio.create_task(session.run())
        session.task.add_done_callback(lambda _task: self.sessions.pop(meeting_id, None))
        return session

    def stop(self, meeting_id, reason="Остановлено пользователем"):
        session = self.sessions.get(meeting_id)
        if session:
            session.request_stop(reason)
        return session

    async def shutdown(self):
        sessions = list(self.sessions.values())
        for session in sessions:
            session.task.cancel()
        await asyncio.gather(*(session.task for session in sessions), return_exceptions=True)

    # Tickets let a browser authenticate a WebSocket without an Authorization header.

    def issue_ticket(self, meeting_id, user_id, purpose):
        self._purge_tickets()
        token = secrets.token_urlsafe(24)
        self._tickets[token] = (meeting_id, user_id, purpose, time.monotonic() + TICKET_SECONDS)
        return token

    def redeem_ticket(self, token, meeting_id, purpose):
        self._purge_tickets()
        entry = self._tickets.pop(token or "", None)
        if not entry or entry[0] != meeting_id or entry[2] != purpose:
            return None
        return entry[1]

    def _purge_tickets(self):
        moment = time.monotonic()
        for token in [token for token, entry in self._tickets.items() if entry[3] < moment]:
            self._tickets.pop(token, None)

    # Persistence helpers

    def update_live(self, meeting_id, **fields):
        def change(document):
            document["live"] = {**(document.get("live") or {}), **fields}

        try:
            self.store.update(meeting_id, change)
        except KeyError:
            pass

    def append_segments(self, meeting_id, segments):
        def change(document):
            existing = document.get("segments") or []
            for segment in segments:
                segment.id = f"s{len(existing) + 1}"
                existing.append(segment.model_dump())
            document["segments"] = existing

        try:
            self.store.update(meeting_id, change)
        except KeyError:
            pass

    async def finalize(self, session: LiveSession, interrupted=False):
        meeting_id = session.meeting_id
        meeting = self.store.get(meeting_id)
        if meeting is None:
            session.pcm_path.unlink(missing_ok=True)
            return
        live = {**(meeting.get("live") or {}), "ended_at": now(), "duration_seconds": round(session.audio_seconds, 1), "failed_windows": session.failed_windows, "stop_reason": session.stop_reason}
        extra = {"speaker_events": session.speaker_events, "participants_seen": [{"platform_id": key, "name": value} for key, value in session.participants.items()]}
        await self.persist(meeting, live, extra, interrupted)
        self.hub.publish(meeting_id, {"type": "finished", "status": self.store.get(meeting_id)["status"]})

    async def persist(self, meeting, live, extra, interrupted):
        """Turn the captured PCM and live transcript into a regular recorded meeting."""
        meeting_id = meeting["id"]
        pcm_path = self.settings.data_dir / "live" / f"{meeting_id}.pcm"
        if not pcm_path.exists() or pcm_path.stat().st_size == 0:
            pcm_path.unlink(missing_ok=True)
            self.store.update(meeting_id, extra | {"status": "failed", "live": live | {"status": "ended"}, "error": "Звук не поступал: протокол не сформирован. " + (live.get("stop_reason") or "")})
            return
        wav_path = self.settings.data_dir / "tmp" / f"live-{meeting_id}.wav"
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        duration = await asyncio.to_thread(pcm_to_wav, pcm_path, wav_path)
        key = f"audio/{meeting_id}.wav"
        await asyncio.to_thread(self.blobs.put_file, key, wav_path)
        pcm_path.unlink(missing_ok=True)
        segments = self.store.get(meeting_id).get("segments") or []
        live = live | {"status": "ended", "duration_seconds": round(duration, 1)}
        changes = extra | {"audio_key": key, "live": live, "asr_segments": segments, "transcript": " ".join(segment["text"] for segment in segments)}
        if not segments:
            self.store.update(meeting_id, changes | {"status": "failed", "error": "Речь в онлайн-сессии не распознана. Запись сохранена: проверьте звук и нажмите «Повторить»."})
            return
        if interrupted:
            self.store.update(meeting_id, changes | {"status": "failed", "error": INTERRUPTED})
            return
        self.store.update(meeting_id, changes | {"status": "queued", "error": None})
        self.store.audit("live_session_finished", None, meeting_id, duration_seconds=round(duration, 1), segments=len(segments))
        self.schedule(meeting_id)

    async def recover(self):
        """At startup, save audio of sessions that were live when the process stopped."""
        for meeting in self.store.all():
            if meeting.get("status") == "live":
                live = {**(meeting.get("live") or {}), "ended_at": now(), "stop_reason": "Перезапуск сервера"}
                await self.persist(meeting, live, {}, interrupted=True)
