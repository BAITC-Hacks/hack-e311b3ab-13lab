import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.integrations.events import AudioChunk, ConnectorStatus, Participant

_END = object()


class MeetingConnector(ABC):
    """Everything the live session needs from a meeting source.

    The rest of the application only talks to this interface, so Teams, Zoom,
    Google Meet and a captured browser tab are interchangeable.
    """

    platform = "unknown"
    kind = "unknown"

    def __init__(self):
        self._audio: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self._events: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._participants: dict[str, Participant] = {}

    @abstractmethod
    async def join(self, meeting_url: str) -> None:
        """Connect to the meeting. Returns once joining has started."""

    @abstractmethod
    async def leave(self) -> None:
        """Disconnect. Must be safe to call more than once."""

    async def get_participants(self) -> list[Participant]:
        return list(self._participants.values())

    async def stream_audio(self) -> AsyncIterator[AudioChunk]:
        while (chunk := await self._audio.get()) is not _END:
            yield chunk

    async def events(self) -> AsyncIterator[object]:
        while (event := await self._events.get()) is not _END:
            yield event

    # Producers (WebSocket handlers, bot callbacks) push through these helpers.

    def push_audio(self, pcm: bytes) -> bool:
        """Queue audio; returns False when the consumer is too far behind."""
        try:
            self._audio.put_nowait(AudioChunk(pcm))
            return True
        except asyncio.QueueFull:
            return False

    def push_event(self, event) -> None:
        if hasattr(event, "participants"):
            self._participants = {item.platform_id: item for item in event.participants}
        try:
            self._events.put_nowait(event)
        except asyncio.QueueFull:
            pass

    def close_streams(self, status: ConnectorStatus | None = None) -> None:
        if status:
            self.push_event(status)
        for queue in (self._audio, self._events):
            try:
                queue.put_nowait(_END)
            except asyncio.QueueFull:
                queue.get_nowait()
                queue.put_nowait(_END)
