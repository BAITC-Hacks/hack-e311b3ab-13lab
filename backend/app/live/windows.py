"""Cut continuous audio into speech windows that are sent to ASR one by one."""

import array
from collections import deque
from dataclasses import dataclass

from app.integrations.events import BYTES_PER_SAMPLE, SAMPLE_RATE
from app.live.vad import FRAME_SAMPLES, FRAME_SECONDS

FRAME_BYTES = FRAME_SAMPLES * BYTES_PER_SAMPLE


@dataclass(frozen=True)
class Window:
    start: float  # seconds since the session started
    pcm: bytes
    speech_seconds: float

    @property
    def seconds(self) -> float:
        return len(self.pcm) / (SAMPLE_RATE * BYTES_PER_SAMPLE)


class Windower:
    """Groups frames into windows of min..max seconds, cutting at pauses.

    A window closes after `silence_cut` seconds of silence once it is at least
    `min_seconds` long, after `long_pause` seconds of silence at any length, or at
    `max_seconds`. Windows with less than `min_speech` seconds of speech are dropped.
    """

    def __init__(self, vad, min_seconds=8.0, max_seconds=25.0, silence_cut=0.6, long_pause=2.0, min_speech=0.5, pre_roll=0.3):
        self.vad = vad
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds
        self.silence_cut = silence_cut
        self.long_pause = long_pause
        self.min_speech = min_speech
        self._pending = b""
        self._frames_seen = 0
        self._pre_roll = deque(maxlen=max(1, round(pre_roll / FRAME_SECONDS)))
        self._window: list[bytes] | None = None
        self._window_start = 0
        self._speech = 0.0
        self._silence = 0.0

    @property
    def seconds_seen(self) -> float:
        return self._frames_seen * FRAME_SECONDS

    def feed(self, pcm: bytes) -> list[Window]:
        data = self._pending + pcm
        usable = len(data) - len(data) % FRAME_BYTES
        self._pending = data[usable:]
        windows = []
        for offset in range(0, usable, FRAME_BYTES):
            window = self._frame(data[offset:offset + FRAME_BYTES])
            if window:
                windows.append(window)
        return windows

    def flush(self) -> list[Window]:
        window = self._close()
        return [window] if window else []

    def _frame(self, frame: bytes):
        samples = array.array("h")
        samples.frombytes(frame)
        speech = self.vad.is_speech(samples)
        self._frames_seen += 1
        if self._window is None:
            if not speech:
                self._pre_roll.append(frame)
                return None
            self._window = list(self._pre_roll)
            self._window_start = self._frames_seen - 1 - len(self._pre_roll)
            self._pre_roll.clear()
            self._speech = self._silence = 0.0
        self._window.append(frame)
        if speech:
            self._speech += FRAME_SECONDS
            self._silence = 0.0
        else:
            self._silence += FRAME_SECONDS
        length = len(self._window) * FRAME_SECONDS
        if (length >= self.min_seconds and self._silence >= self.silence_cut) or self._silence >= self.long_pause or length >= self.max_seconds:
            return self._close()
        return None

    def _close(self):
        if self._window is None:
            return None
        window = Window(start=self._window_start * FRAME_SECONDS, pcm=b"".join(self._window), speech_seconds=self._speech)
        self._window = None
        return window if window.speech_seconds >= self.min_speech else None
