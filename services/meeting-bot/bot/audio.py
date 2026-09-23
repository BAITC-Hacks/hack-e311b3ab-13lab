"""One PulseAudio null sink per meeting; parec records its monitor as 16 kHz PCM16 mono."""

import asyncio
import contextlib

CHUNK_BYTES = 3200  # 100 ms


async def _pactl(*args) -> str:
    process = await asyncio.create_subprocess_exec("pactl", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await process.communicate()
    if process.returncode:
        raise RuntimeError(f"pactl {' '.join(args)} failed: {err.decode().strip()}")
    return out.decode().strip()


class MeetingSink:
    def __init__(self, session_id: str):
        self.name = f"meeting_{session_id[:16]}"
        self.module_id = None
        self.recorder = None

    async def create(self):
        self.module_id = await _pactl("load-module", "module-null-sink", f"sink_name={self.name}", f"sink_properties=device.description={self.name}")
        return self.name

    async def chunks(self):
        """Yield raw PCM chunks from the sink monitor until stopped."""
        self.recorder = await asyncio.create_subprocess_exec(
            "parec", f"--device={self.name}.monitor", "--rate=16000", "--channels=1", "--format=s16le", "--latency-msec=100",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        while chunk := await self.recorder.stdout.read(CHUNK_BYTES):
            yield chunk

    async def close(self):
        if self.recorder and self.recorder.returncode is None:
            self.recorder.terminate()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.recorder.wait(), 5)
        if self.module_id:
            with contextlib.suppress(Exception):
                await _pactl("unload-module", self.module_id)
