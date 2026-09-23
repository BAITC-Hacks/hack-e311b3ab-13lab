import json
import time
from unittest import mock

import httpx
from starlette.websockets import WebSocketDisconnect

from app.integrations import bot as bot_module
from app.routes.bot import to_event
from tests.helpers import AppTestCase
from tests.test_live import LiveProvider, silence, tone

TOKEN = "bot-token-for-tests-0123456789"


class FakeBotService:
    def __init__(self, status=202):
        self.requests = []
        self.status = status

    def handler(self, request):
        self.requests.append((request.method, request.url.path, request.headers.get("authorization"), request.content))
        return httpx.Response(self.status, json={"status": "starting"})


class BotSessionTests(AppTestCase):
    settings_overrides = {"bot_service_url": "http://meeting-bot:8100", "bot_token": TOKEN, "live_idle_seconds": 60}

    def setUp(self):
        super().setUp()
        self.provider = LiveProvider()
        self.app.state.live.provider = self.provider
        self.service = FakeBotService()
        transport = httpx.MockTransport(self.service.handler)
        real_client = httpx.AsyncClient
        self.patcher = mock.patch.object(bot_module.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        super().tearDown()

    def start_bot(self, url="https://meet.google.com/abc-defg-hij"):
        return self.client.post("/api/live", headers=self.auth("secretary"), json={"title": "Встреча с ботом", "meeting_date": "2026-09-23", "recording_consent": True, "source": "bot", "meeting_url": url})

    def wait_for(self, meeting_id, statuses, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            meeting = self.get(f"/api/meetings/{meeting_id}", "secretary").json()
            if meeting["status"] in statuses:
                return meeting
            time.sleep(0.05)
        self.fail(f"meeting stayed {meeting['status']}")

    def test_bot_session_end_to_end(self):
        response = self.start_bot()
        self.assertEqual(response.status_code, 201, response.text)
        meeting = response.json()
        self.assertEqual(meeting["source"], {"type": "bot", "platform": "google_meet"})
        method, path, authorization, body = self.service.requests[0]
        self.assertEqual((method, path, authorization), ("POST", "/sessions", f"Bearer {TOKEN}"))
        sent = json.loads(body)
        self.assertEqual(sent["callback_url"], f"ws://backend:8000/internal/bot/{meeting['id']}")
        self.assertEqual(sent["bot_name"], "HATTAMA.AI Секретарь")
        with self.client.websocket_connect(f"/internal/bot/{meeting['id']}", headers={"Authorization": f"Bearer {TOKEN}"}) as bot:
            bot.send_json({"type": "status", "status": "lobby", "detail": "Впустите бота"})
            bot.send_json({"type": "status", "status": "joined"})
            bot.send_json({"type": "participants", "participants": [{"id": "Дархан", "name": "Дархан"}, {"id": "Айбек", "name": "Айбек"}]})
            bot.send_json({"type": "speaker", "id": "Айбек", "name": "Айбек", "at": 0.4})
            audio = silence(0.3) + tone(9) + silence(1.5)
            for offset in range(0, len(audio), 3200):
                bot.send_bytes(audio[offset:offset + 3200])
            deadline = time.monotonic() + 10
            while not self.get(f"/api/meetings/{meeting['id']}", "secretary").json().get("segments") and time.monotonic() < deadline:
                time.sleep(0.05)
            live = self.get(f"/api/meetings/{meeting['id']}", "secretary").json()
            self.assertEqual(live["live"]["status"], "live")
            self.assertEqual([item["name"] for item in live["participants_seen"]], ["Дархан", "Айбек"])
            bot.send_json({"type": "status", "status": "ended", "detail": "Совещание завершено"})
        ready = self.wait_for(meeting["id"], {"ready"})
        self.assertEqual(ready["live"]["stop_reason"], "Совещание завершено")
        self.assertEqual(self.provider.calls, 1)
        stored = self.store.get(meeting["id"])
        self.assertEqual(stored["speaker_events"], [{"at": 0.4, "platform_id": "Айбек", "name": "Айбек"}])
        self.assertTrue(any(request[0] == "DELETE" for request in self.service.requests))

    def test_internal_socket_requires_bot_token_and_session(self):
        meeting = self.start_bot().json()
        for headers, code in (({"Authorization": "Bearer wrong"}, 4401), ({}, 4401)):
            with self.assertRaises(WebSocketDisconnect) as closed:
                with self.client.websocket_connect(f"/internal/bot/{meeting['id']}", headers=headers):
                    pass
            self.assertEqual(closed.exception.code, code)
        with self.assertRaises(WebSocketDisconnect) as closed:
            with self.client.websocket_connect("/internal/bot/" + "0" * 32, headers={"Authorization": f"Bearer {TOKEN}"}):
                pass
        self.assertEqual(closed.exception.code, 4404)
        self.client.post(f"/api/live/{meeting['id']}/stop", headers=self.auth("secretary"))

    def test_unavailable_bot_service_fails_the_session(self):
        self.service.status = 503
        meeting = self.start_bot("https://teams.live.com/meet/9876543210").json()
        failed = self.wait_for(meeting["id"], {"failed"})
        self.assertIn("Сервис бота ответил HTTP 503", failed["error"])
        self.assertEqual(failed["source"]["platform"], "teams")

    def test_bot_disconnect_ends_the_session(self):
        meeting = self.start_bot("https://us05web.zoom.us/j/123456789?pwd=abc").json()
        with self.client.websocket_connect(f"/internal/bot/{meeting['id']}", headers={"Authorization": f"Bearer {TOKEN}"}) as bot:
            bot.send_json({"type": "status", "status": "joined"})
        failed = self.wait_for(meeting["id"], {"failed"})
        self.assertIn("Бот вышел из совещания", failed["error"])


class EventParsingTests(AppTestCase):
    def test_bot_messages_are_validated(self):
        self.assertIsNone(to_event({"type": "status", "status": "hacked"}))
        self.assertIsNone(to_event({"type": "speaker", "name": "X", "at": -1}))
        self.assertIsNone(to_event({"type": "unknown"}))
        people = to_event({"type": "participants", "participants": [{"name": "А" * 500}, {"id": "x"}, "junk"]})
        self.assertEqual(len(people.participants), 1)
        self.assertEqual(len(people.participants[0].name), 120)
