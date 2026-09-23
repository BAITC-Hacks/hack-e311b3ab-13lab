"""Voice activity detection on 16 kHz PCM16 frames of FRAME_SAMPLES samples."""

import array
import logging
import math
from pathlib import Path

from app.integrations.events import SAMPLE_RATE

FRAME_SAMPLES = 512  # 32 ms, the Silero window size at 16 kHz
FRAME_SECONDS = FRAME_SAMPLES / SAMPLE_RATE
logger = logging.getLogger("hattama")


class EnergyVad:
    """Adaptive RMS detector. Used when the Silero model is unavailable (and in tests)."""

    kind = "energy"

    def __init__(self, minimum_rms=350.0, ratio=3.0):
        self.minimum_rms = minimum_rms
        self.ratio = ratio
        self.noise = minimum_rms / ratio

    def is_speech(self, frame: array.array) -> bool:
        rms = math.sqrt(sum(sample * sample for sample in frame) / max(len(frame), 1))
        speech = rms > max(self.minimum_rms, self.noise * self.ratio)
        if not speech:
            self.noise = 0.95 * self.noise + 0.05 * rms
        return speech


class SileroVad:
    """Silero VAD through sherpa-onnx: CPU only, about 2 MB, runs far faster than real time."""

    kind = "silero"

    def __init__(self, model_path: str):
        import sherpa_onnx

        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = model_path
        config.silero_vad.min_silence_duration = 0.4
        config.silero_vad.min_speech_duration = 0.25
        config.silero_vad.threshold = 0.5
        config.sample_rate = SAMPLE_RATE
        self._vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=60)

    def is_speech(self, frame: array.array) -> bool:
        self._vad.accept_waveform([sample / 32768 for sample in frame])
        while not self._vad.empty():  # we only use the live flag; drop buffered segments
            self._vad.pop()
        return self._vad.is_speech_detected()


def make_vad(model_path: str):
    if model_path and Path(model_path).is_file():
        try:
            return SileroVad(model_path)
        except Exception as error:  # pragma: no cover - depends on the native wheel
            logger.warning("Silero VAD недоступен (%s), используется энергетический детектор", type(error).__name__)
    return EnergyVad()
