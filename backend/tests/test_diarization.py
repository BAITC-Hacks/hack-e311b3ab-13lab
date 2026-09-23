import asyncio
import tempfile
import httpx
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.config import Settings
from app.diarization import Turn, align_speakers, remote_diarize
from app.models import Analysis, Word
from app.pipeline import make_segments, run_pipeline
from app.store import Store, new_meeting
from app.blobs import LocalBlobStore
from tests.helpers import make_settings


class AlignmentTests(unittest.TestCase):
    def test_splits_sentence_at_voice_change_without_losing_words(self):
        words = [Word(word="Айжан,", start=0, end=.5), Word(word="сделайте", start=.6, end=1),
            Word(word="хорошо.", start=1.1, end=2)]
        segments = make_segments("", words)
        result = align_speakers(segments, [Turn(start=0, end=1, speaker_id="A"), Turn(start=1, end=2, speaker_id="B")])
        self.assertEqual([s.speaker for s in result], ["A", "B"])
        self.assertEqual([w for s in result for w in s.words], words)
        self.assertEqual([s.id for s in result], ["s1", "s2"])

    def test_overlap_and_uncovered_audio_are_not_guessed(self):
        words = [Word(word="Да", start=0, end=1), Word(word="потом", start=5, end=6)]
        result = align_speakers(make_segments("", words), [Turn(start=0, end=1, speaker_id="A"), Turn(start=0, end=1, speaker_id="B")])
        self.assertTrue(all(s.speaker is None and s.speaker_uncertain for s in result))

    def test_invalid_turns_rejected(self):
        for start, end in [(2, 1), (0, float("inf")), (-1, 1)]:
            with self.assertRaises(ValueError):
                Turn(start=start, end=end, speaker_id="A")

    def test_retry_after_gpu_failure_reuses_asr(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as directory:
                settings = make_settings(directory, diarization_url="http://127.0.0.1:8765")
                store = Store(settings)
                blobs = LocalBlobStore(settings.data_dir)
                blobs.put_bytes("audio/test.wav", b"audio")
                meeting = new_meeting("Test", "2026-09-23", "audio/test.wav")
                meeting["id"] = "test"
                store.create(meeting)
                provider = AsyncMock()
                segments = make_segments("", [Word(word="Сделаю.", start=0, end=1)])
                provider.transcribe.return_value = ("Сделаю.", segments)
                provider.analyze.return_value = Analysis(summary="Test")
                with patch("app.pipeline.remote_diarize", side_effect=RuntimeError("GPU offline")):
                    await run_pipeline("test", store, settings, provider, asyncio.Semaphore(1), blobs)
                self.assertEqual(store.get("test")["status"], "failed")
                self.assertTrue(store.get("test")["asr_segments"])
                with patch("app.pipeline.remote_diarize", return_value=(segments,{"turns":[],"model":"test"})):
                    await run_pipeline("test", store, settings, provider, asyncio.Semaphore(1), blobs)
                self.assertEqual(store.get("test")["status"], "ready")
                self.assertEqual(provider.transcribe.await_count, 1)
                store.engine.dispose()
        asyncio.run(scenario())


class RemoteClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_authentication_and_safe_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.wav"
            path.write_bytes(b"audio")
            settings = make_settings(directory, diarization_url="http://worker", diarization_token="test-secret")
            seen = []
            def handle(request):
                seen.append(request)
                return httpx.Response(200, json={"duration_seconds": 2, "model": "pyannote", "private": "not-stored",
                    "turns": [{"start": 0, "end": 2, "speaker_id": "A"}]})
            factory = httpx.AsyncClient
            with patch("app.diarization.httpx.AsyncClient", side_effect=lambda **kw: factory(transport=httpx.MockTransport(handle), **kw)):
                result, metadata = await remote_diarize(path, make_segments("", [Word(word="Да.", start=0, end=1)]), settings)
            self.assertEqual(seen[0].headers["Authorization"], "Bearer test-secret")
            self.assertEqual(result[0].speaker, "A")
            self.assertNotIn("private", metadata)

    async def test_worker_error_is_actionable_without_response_body(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.wav"
            path.write_bytes(b"audio")
            settings = make_settings(directory, diarization_url="http://worker")
            factory = httpx.AsyncClient
            def handle(request):
                return httpx.Response(401, text="sensitive worker diagnostics")
            with patch("app.diarization.httpx.AsyncClient", side_effect=lambda **kw: factory(transport=httpx.MockTransport(handle), **kw)):
                with self.assertRaisesRegex(RuntimeError, "DIARIZATION_TOKEN") as error:
                    await remote_diarize(path, [], settings)
            self.assertNotIn("sensitive", str(error.exception))
