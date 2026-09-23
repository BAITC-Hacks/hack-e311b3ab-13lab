"""Normalized meeting events shared by every connector."""

from dataclasses import dataclass, field

SAMPLE_RATE = 16_000
BYTES_PER_SAMPLE = 2  # PCM16 little-endian, mono


@dataclass(frozen=True)
class AudioChunk:
    """Raw PCM16 mono audio at 16 kHz."""

    pcm: bytes

    @property
    def seconds(self) -> float:
        return len(self.pcm) / (SAMPLE_RATE * BYTES_PER_SAMPLE)


@dataclass(frozen=True)
class Participant:
    platform_id: str
    name: str


@dataclass(frozen=True)
class ParticipantsChanged:
    participants: tuple[Participant, ...]


@dataclass(frozen=True)
class ActiveSpeaker:
    """A participant is speaking from `at` seconds since the session started."""

    participant: Participant
    at: float


@dataclass(frozen=True)
class ConnectorStatus:
    """joining, lobby, joined, ended or error."""

    status: str
    detail: str = ""


@dataclass
class SessionInfo:
    platform: str
    connector: str
    meeting_url: str = ""
    extra: dict = field(default_factory=dict)
