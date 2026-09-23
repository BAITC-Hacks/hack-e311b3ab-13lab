import logging
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app import security
from app.config import Settings
from app.main import create_app
from app.models import Action, Analysis, Segment

# Cheaper scrypt cost keeps the suite fast; verification reads the cost from each hash.
security.SCRYPT_N = 2**10
logging.getLogger("hattama").setLevel(logging.ERROR)

PASSWORD = "correct-horse-battery"
ROLES = {"admin": "admin", "secretary": "secretary", "chair": "chair", "participant": "participant", "auditor": "auditor", "outsider": "participant"}


class FakeProvider:
    async def transcribe(self, path):
        return "Айжан подготовит отчёт к пятнице.", [Segment(id="s1", text="Айжан подготовит отчёт к пятнице.", start=0, end=3)]

    async def analyze(self, segments, meeting_date, title):
        return Analysis(summary="Подготовка отчёта", actions=[Action(id="a1", title="Подготовить отчёт", owner="Айжан", deadline_text="к пятнице", due_date="2026-09-25", evidence=segments[0].text, segment_ids=["s1"])])


def make_settings(directory, **overrides):
    base = replace(
        Settings.from_env(),
        data_dir=Path(directory),
        api_key="test",
        max_upload_bytes=32,
        diarization_model_path="",
        database_url="",
        minio_endpoint="",
        admin_email="",
        admin_password="",
    )
    return replace(base, **overrides)


class AppTestCase(unittest.TestCase):
    settings_overrides = {}

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = make_settings(self.directory.name, **self.settings_overrides)
        self.app = create_app(self.settings, FakeProvider())
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.store = self.app.state.store
        self.users, self.tokens = {}, {}
        for name, role in ROLES.items():
            self.users[name] = self.store.create_user(f"{name}@example.kz", name.title(), role, PASSWORD)
            response = self.client.post("/api/auth/login", json={"email": f"{name}@example.kz", "password": PASSWORD})
            self.tokens[name] = response.json()["token"]

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.store.engine.dispose()
        self.directory.cleanup()

    def auth(self, name):
        return {"Authorization": f"Bearer {self.tokens[name]}"}

    def upload(self, as_user="secretary", content=b"audio", consent="true", filename="sample.mp3"):
        return self.client.post("/api/meetings", headers=self.auth(as_user), data={"title": "Тест", "meeting_date": "2026-09-23", "recording_consent": consent}, files={"audio": (filename, content, "audio/mpeg")})

    def get(self, path, as_user):
        return self.client.get(path, headers=self.auth(as_user))

    def ready_meeting(self, as_user="secretary"):
        response = self.upload(as_user)
        self.assertEqual(response.status_code, 202, response.text)
        meeting_id = response.json()["id"]
        for _attempt in range(200):
            result = self.get(f"/api/meetings/{meeting_id}", as_user).json()
            if result["status"] == "ready":
                return result
            time.sleep(0.01)
        self.fail("Pipeline did not finish")

    def approve(self, meeting, as_user="secretary"):
        response = self.client.post(f"/api/meetings/{meeting['id']}/approve", headers=self.auth(as_user), json={"version": meeting["version"]})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def review(self, meeting, as_user="secretary", **changes):
        payload = {"version": meeting["version"], "analysis": meeting["analysis"], "speaker_names": meeting["speaker_names"], **changes}
        return self.client.put(f"/api/meetings/{meeting['id']}/review", headers=self.auth(as_user), json=payload)
