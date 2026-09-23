import tempfile
import time
import unittest
from dataclasses import replace
from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

from app.config import Settings
from app.deadlines import resolve_deadline
from app.main import create_app
from app.models import Action, Analysis, Segment, Word
from app.pipeline import make_segments, validate_evidence


class FakeProvider:
    async def transcribe(self, path):
        return "Айжан подготовит отчёт к пятнице.", [Segment(id="s1", text="Айжан подготовит отчёт к пятнице.", start=0, end=3)]

    async def analyze(self, segments, meeting_date, title):
        return Analysis(summary="Подготовка отчёта", actions=[Action(title="Подготовить отчёт", owner="Айжан", deadline_text="к пятнице", due_date="2026-09-25", evidence=segments[0].text, segment_ids=["s1"])])


class PipelineTests(unittest.TestCase):
    def test_deadline_ambiguity(self):
        self.assertIsNone(resolve_deadline("на следующей неделе", "2026-09-23"))
        self.assertIsNone(resolve_deadline("к среде", "2026-09-23"))
        self.assertEqual(str(resolve_deadline("до пятницы", "2026-09-23")), "2026-09-25")
        self.assertEqual(str(resolve_deadline("за две недели", "2026-09-23")), "2026-10-07")
        self.assertEqual(str(resolve_deadline("до двадцать шестого сентября", "2026-09-23")), "2026-09-26")
        self.assertEqual(str(resolve_deadline("до пятнадцатого октября", "2026-09-23")), "2026-10-15")
        self.assertEqual(str(resolve_deadline("к двадцатому октября", "2026-09-23")), "2026-10-20")

    def test_word_timestamps_and_sentence_grouping(self):
        result = make_segments("", [Word(word="Сәлем!", start=1, end=2), Word(word="Отчёт.", start=3, end=4)])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1].start, 3)

    def test_no_invented_timestamps(self):
        self.assertIsNone(make_segments("Привет. Отчёт готов.", [])[0].start)

    def test_invalid_word_interval(self):
        with self.assertRaises(ValueError):
            Word(word="test", start=2, end=1)

    def test_hallucinated_evidence_is_rejected(self):
        analysis = Analysis(summary="", actions=[Action(title="Удалить файл", evidence="Удалить файл")])
        result = validate_evidence(analysis, [Segment(id="s1", text="Подготовить отчёт")])
        self.assertEqual(result.actions, [])
        self.assertEqual(len(result.warnings), 1)

    def test_missing_deadline_and_source_validation(self):
        action = Action(title="Отчёт", evidence="Айжан подготовит отчёт.", due_date="2026-09-25", segment_ids=["invented"])
        result = validate_evidence(Analysis(summary="", actions=[action]), [Segment(id="s1", text=action.evidence)])
        self.assertIsNone(result.actions[0].due_date)
        self.assertEqual(result.actions[0].segment_ids, ["s1"])
        self.assertTrue(result.actions[0].needs_review)

    def test_duplicate_actions_removed(self):
        action = Action(title="Отчёт", evidence="Подготовить отчёт.")
        result = validate_evidence(Analysis(summary="", actions=[action, action.model_copy()]), [Segment(id="s1", text=action.evidence)])
        self.assertEqual(len(result.actions), 1)


class APITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = replace(Settings.from_env(), data_dir=Path(self.directory.name), api_key="test", app_token="test-access", max_upload_bytes=32, diarization_model_path="")
        self.client = TestClient(create_app(self.settings, FakeProvider()))
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer test-access"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.directory.cleanup()

    def upload(self, content=b"audio", consent="true", filename="sample.mp3"):
        return self.client.post("/api/meetings", headers=self.headers, data={"title": "Тест", "meeting_date": "2026-09-23", "recording_consent": consent}, files={"audio": (filename, content, "audio/mpeg")})

    def ready_meeting(self):
        response = self.upload()
        self.assertEqual(response.status_code, 202)
        meeting_id = response.json()["id"]
        for attempt in range(100):
            result = self.client.get(f"/api/meetings/{meeting_id}", headers=self.headers).json()
            if result["status"] == "ready":
                return result
            time.sleep(.01)
        self.fail("Pipeline did not finish")

    def test_private_endpoints_require_authentication(self):
        self.assertEqual(self.client.get("/api/meetings").status_code, 401)
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_recording_consent_required(self):
        self.assertEqual(self.upload(consent="false").status_code, 400)

    def test_upload_limits_and_cleanup(self):
        self.assertEqual(self.upload(content=b"a" * 33).status_code, 413)
        self.assertEqual(list((self.settings.data_dir / "audio").iterdir()), [])
        self.assertEqual(self.upload(content=b"").status_code, 400)
        self.assertEqual(self.upload(filename="sample.exe").status_code, 415)

    def test_pipeline_review_conflict_and_exports(self):
        meeting = self.ready_meeting()
        self.assertIn("Диаризация не настроена", meeting["analysis"]["warnings"][0])
        payload = {"version": meeting["version"], "analysis": meeting["analysis"], "speaker_names": {}}
        payload["analysis"]["actions"][0]["status"] = "done"
        self.assertEqual(self.client.put(f"/api/meetings/{meeting['id']}/review", headers=self.headers, json=payload).status_code, 200)
        self.assertEqual(self.client.put(f"/api/meetings/{meeting['id']}/review", headers=self.headers, json=payload).status_code, 409)
        markdown = self.client.get(f"/api/meetings/{meeting['id']}/export/md", headers=self.headers)
        self.assertIn("Айжан", markdown.text)
        word = self.client.get(f"/api/meetings/{meeting['id']}/export/docx", headers=self.headers)
        document = Document(BytesIO(word.content))
        self.assertEqual(document.tables[0].rows[1].cells[1].text, "Айжан")
        self.assertEqual(self.client.get(f"/api/meetings/{meeting['id']}/retry", headers=self.headers).status_code, 405)

    def test_missing_meeting(self):
        self.assertEqual(self.client.get("/api/meetings/unknown", headers=self.headers).status_code, 404)


if __name__ == "__main__":
    unittest.main()
