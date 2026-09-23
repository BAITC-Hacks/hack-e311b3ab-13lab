import array
import math
import time
import unittest
import wave

from app.integrations.registry import detect_platform
from app.live.manager import INTERRUPTED
from app.live.vad import EnergyVad
from app.live.windows import Windower
from app.models import Segment, Word
from tests.helpers import AppTestCase, FakeProvider

RATE = 16_000


def tone(seconds, amplitude=8000):
    samples = array.array("h", (int(amplitude * math.sin(2 * math.pi * 300 * index / RATE)) for index in range(int(seconds * RATE))))
    return samples.tobytes()


def silence(seconds):
    return bytes(int(seconds * RATE) * 2)


class LiveProvider(FakeProvider):
    """Returns one segment per window with word timestamps relative to the window."""

    def __init__(self):
        self.calls = 0

    async def transcribe(self, path):
        self.calls += 1
        with wave.open(str(path)) as audio:
            seconds = audio.getnframes() / audio.getframerate()
        text = "Айжан подготовит отчёт к пятнице."
        words = [Word(word=word, start=index * 0.5, end=index * 0.5 + 0.4) for index, word in enumerate(text.split())]
        return text, [Segment(id="s1", text=text, start=0, end=min(seconds, words[-1].end), words=words)]


class RegistryTests(unittest.TestCase):
    def test_allowed_meeting_links(self):
        self.assertEqual(detect_platform("https://meet.google.com/abc-defg-hij"), "google_meet")
        self.assertEqual(detect_platform("https://teams.microsoft.com/l/meetup-join/19%3ameeting_x/0"), "teams")
        self.assertEqual(detect_platform("https://teams.live.com/meet/9876543210"), "teams")
        self.assertEqual(detect_platform("https://us05web.zoom.us/j/123456789?pwd=abc"), "zoom")
        self.assertEqual(detect_platform("https://app.zoom.us/wc/join/123456789"), "zoom")

    def test_everything_else_is_rejected(self):
        for url in (
            "http://meet.google.com/abc-defg-hij",
            "https://meet.google.com.evil.example/abc",
            "https://evil.example/?u=https://meet.google.com/abc",
            "https://user:pass@meet.google.com/abc-defg-hij",
            "https://meet.google.com:8443/abc-defg-hij",
            "https://127.0.0.1/j/1",
            "https://backend:8000/api",
            "https://zoom.us/",
            "https://notzoom.us/j/1",
            "javascript:alert(1)",
            "",
        ):
            self.assertIsNone(detect_platform(url), url)


class WindowerTests(unittest.TestCase):
    def test_windows_cut_at_pauses(self):
        windower = Windower(EnergyVad())
        windows = windower.feed(silence(1) + tone(10) + silence(1) + tone(3) + silence(3))
        windows += windower.flush()
        self.assertEqual(len(windows), 2)
        self.assertAlmostEqual(windows[0].start, 0.7, delta=0.1)
        self.assertGreaterEqual(windows[0].speech_seconds, 9.9)
        self.assertAlmostEqual(windows[1].start, 11.7, delta=0.2)
        self.assertLess(windows[1].seconds, 6)

    def test_long_speech_is_split_and_noise_is_dropped(self):
        windower = Windower(EnergyVad())
        windows = windower.feed(tone(60)) + windower.flush()
        self.assertEqual(len(windows), 3)
        self.assertTrue(all(window.seconds <= 25.1 for window in windows))
        quiet = Windower(EnergyVad())
        self.assertEqual(quiet.feed(silence(5) + tone(0.2) + silence(5)) + quiet.flush(), [])

    def test_frames_can_arrive_in_odd_sizes(self):
        windower = Windower(EnergyVad())
        audio = tone(9) + silence(1)
        windows = []
        for offset in range(0, len(audio), 777 * 2):
            windows += windower.feed(audio[offset:offset + 777 * 2])
        self.assertEqual(len(windows), 1)


class LiveSessionTests(AppTestCase):
    settings_overrides = {"live_idle_seconds": 3}

    def setUp(self):
        super().setUp()
        self.provider = LiveProvider()
        self.app.state.live.provider = self.provider

    def start(self, as_user="secretary", **overrides):
        payload = {"title": "Онлайн-планёрка", "meeting_date": "2026-09-23", "recording_consent": True, "source": "tab"} | overrides
        return self.client.post("/api/live", headers=self.auth(as_user), json=payload)

    def ticket(self, meeting_id, purpose, as_user="secretary"):
        return self.client.post(f"/api/live/{meeting_id}/ticket", headers=self.auth(as_user), json={"purpose": purpose})

    def wait_for(self, meeting_id, statuses, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            meeting = self.get(f"/api/meetings/{meeting_id}", "secretary").json()
            if meeting["status"] in statuses:
                return meeting
            time.sleep(0.05)
        self.fail(f"meeting stayed {meeting['status']}")

    def test_tab_session_becomes_a_protocol_without_second_transcription(self):
        response = self.start(meeting_url="https://meet.google.com/abc-defg-hij")
        self.assertEqual(response.status_code, 201, response.text)
        meeting = response.json()
        self.assertEqual(meeting["status"], "live")
        self.assertEqual(meeting["source"], {"type": "tab", "platform": "google_meet"})
        self.assertNotIn("meeting_url", meeting["live"])
        audio_ticket = self.ticket(meeting["id"], "audio").json()["ticket"]
        events_ticket = self.ticket(meeting["id"], "events").json()["ticket"]
        with self.client.websocket_connect(f"/api/live/{meeting['id']}/events?ticket={events_ticket}") as events:
            self.assertEqual(events.receive_json()["type"], "snapshot")
            with self.client.websocket_connect(f"/api/live/{meeting['id']}/audio?ticket={audio_ticket}") as audio:
                stream = silence(0.5) + tone(9) + silence(1.5)
                for offset in range(0, len(stream), 3200):
                    audio.send_bytes(stream[offset:offset + 3200])
                received = []
                while not any(event["type"] == "segments" for event in received):
                    received.append(events.receive_json())
            segment = next(event for event in received if event["type"] == "segments")["segments"][0]
            self.assertEqual(segment["text"], "Айжан подготовит отчёт к пятнице.")
            self.assertAlmostEqual(segment["start"], 0.2, delta=0.05)  # window start incl. 0.3 s pre-roll
            self.assertIn("live", [event.get("status") for event in received if event["type"] == "status"])
            self.assertEqual(self.client.post(f"/api/live/{meeting['id']}/stop", headers=self.auth("secretary")).status_code, 200)
            while (event := events.receive_json())["type"] != "finished":
                pass
        ready = self.wait_for(meeting["id"], {"ready"})
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(ready["live"]["status"], "ended")
        self.assertAlmostEqual(ready["live"]["duration_seconds"], 11, delta=0.2)
        self.assertEqual(ready["segments"][0]["id"], "s1")
        self.assertEqual(ready["analysis"]["actions"][0]["owner"], "Айжан")
        audio_file = self.get(f"/api/meetings/{meeting['id']}/audio", "secretary")
        self.assertEqual(audio_file.status_code, 200)
        self.assertTrue(audio_file.content.startswith(b"RIFF"))
        self.assertIn("live_session_finished", {entry["action"] for entry in self.get("/api/audit", "admin").json()})

    def test_permissions_and_tickets(self):
        self.assertEqual(self.start(as_user="participant").status_code, 403)
        self.assertEqual(self.start(recording_consent=False).status_code, 400)
        meeting = self.start().json()
        self.assertEqual(self.ticket(meeting["id"], "audio", as_user="auditor").status_code, 403)
        self.assertEqual(self.ticket(meeting["id"], "audio", as_user="outsider").status_code, 404)
        self.assertEqual(self.ticket(meeting["id"], "other").status_code, 422)
        token = self.ticket(meeting["id"], "audio").json()["ticket"]
        from starlette.websockets import WebSocketDisconnect

        with self.assertRaises(WebSocketDisconnect) as closed:
            with self.client.websocket_connect(f"/api/live/{meeting['id']}/audio?ticket=forged"):
                pass
        self.assertEqual(closed.exception.code, 4401)
        with self.client.websocket_connect(f"/api/live/{meeting['id']}/audio?ticket={token}"):
            pass
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(f"/api/live/{meeting['id']}/audio?ticket={token}"):
                pass  # tickets are single use
        self.client.post(f"/api/live/{meeting['id']}/stop", headers=self.auth("secretary"))

    def test_bot_requires_allowed_link_and_configuration(self):
        self.assertEqual(self.start(source="bot", meeting_url="https://evil.example/meet").status_code, 422)
        self.assertEqual(self.start(source="bot", meeting_url="https://meet.google.com/abc-defg-hij").status_code, 503)

    def test_session_without_audio_ends_after_idle_timeout(self):
        meeting = self.start().json()
        failed = self.wait_for(meeting["id"], {"failed"}, timeout=10)
        self.assertIn("Звук не поступал", failed["error"])
        self.assertEqual(self.provider.calls, 0)

    def test_concurrent_session_limit(self):
        first, second = self.start().json(), self.start().json()
        self.assertEqual(self.start().status_code, 429)
        for meeting in (first, second):
            self.client.post(f"/api/live/{meeting['id']}/stop", headers=self.auth("secretary"))


class LiveRecoveryTests(AppTestCase):
    def test_restart_keeps_captured_audio(self):
        from app.store import new_meeting

        meeting = new_meeting("Прерванная", "2026-09-23", "", created_by=self.users["secretary"]["id"], source={"type": "tab", "platform": "browser"})
        meeting.update(status="live", live={"status": "live"}, segments=[Segment(id="s1", text="Текст до сбоя.", start=0, end=2).model_dump()])
        self.store.create(meeting)
        live_dir = self.settings.data_dir / "live"
        live_dir.mkdir(parents=True, exist_ok=True)
        (live_dir / f"{meeting['id']}.pcm").write_bytes(tone(2))
        self.client.__exit__(None, None, None)
        from fastapi.testclient import TestClient

        from app.main import create_app

        self.app = create_app(self.settings, FakeProvider(), store=self.store)
        self.client = TestClient(self.app)
        self.client.__enter__()
        recovered = self.store.get(meeting["id"])
        self.assertEqual(recovered["status"], "failed")
        self.assertEqual(recovered["error"], INTERRUPTED)
        self.assertEqual(recovered["asr_segments"][0]["text"], "Текст до сбоя.")
        self.assertTrue(self.app.state.blobs.exists(f"audio/{meeting['id']}.wav"))


if __name__ == "__main__":
    unittest.main()
