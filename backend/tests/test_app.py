import unittest
from io import BytesIO

from docx import Document

from app.deadlines import resolve_deadline
from app.models import Action, Analysis, Segment, Word
from app.pipeline import make_segments, validate_evidence
from tests.helpers import PASSWORD, AppTestCase


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

    def test_model_cannot_set_internal_fields(self):
        action = Action(title="Отчёт", evidence="Подготовить отчёт.", id="forged", assignee_id="someone")
        result = validate_evidence(Analysis(summary="", actions=[action]), [Segment(id="s1", text=action.evidence)])
        self.assertNotEqual(result.actions[0].id, "forged")
        self.assertIsNone(result.actions[0].assignee_id)

    def test_llm_schema_hides_internal_fields(self):
        properties = Analysis.model_json_schema()["$defs"]["Action"]["properties"]
        self.assertNotIn("id", properties)
        self.assertNotIn("assignee_id", properties)


class AuthTests(AppTestCase):
    def test_private_endpoints_require_login(self):
        self.assertEqual(self.client.get("/api/meetings").status_code, 401)
        self.assertEqual(self.client.get("/api/meetings", headers={"Authorization": "Bearer forged"}).status_code, 401)
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_login_logout_and_session_revocation(self):
        me = self.get("/api/auth/me", "secretary").json()
        self.assertEqual(me["role"], "secretary")
        self.assertIn("meetings:create", me["permissions"])
        self.assertEqual(self.client.post("/api/auth/logout", headers=self.auth("secretary")).status_code, 204)
        self.assertEqual(self.get("/api/auth/me", "secretary").status_code, 401)

    def test_failed_logins_are_throttled(self):
        for _attempt in range(5):
            self.assertEqual(self.client.post("/api/auth/login", json={"email": "chair@example.kz", "password": "wrong"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "chair@example.kz", "password": PASSWORD}).status_code, 429)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "nobody@example.kz", "password": PASSWORD}).status_code, 401)

    def test_password_change_invalidates_old_sessions(self):
        response = self.client.post("/api/auth/password", headers=self.auth("chair"), json={"current_password": PASSWORD, "new_password": "another-long-password"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.get("/api/auth/me", "chair").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {response.json()['token']}"}).status_code, 200)

    def test_security_headers(self):
        response = self.client.get("/api/health")
        self.assertIn("default-src 'self'", response.headers["content-security-policy"])
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(self.get("/api/meetings", "secretary").headers["cache-control"], "no-store")


class MeetingTests(AppTestCase):
    def test_recording_consent_required(self):
        self.assertEqual(self.upload(consent="false").status_code, 400)

    def test_upload_limits_and_cleanup(self):
        self.assertEqual(self.upload(content=b"a" * 33).status_code, 413)
        self.assertEqual(list((self.settings.data_dir / "tmp").iterdir()), [])
        self.assertFalse((self.settings.data_dir / "audio").exists())
        self.assertEqual(self.upload(content=b"").status_code, 400)
        self.assertEqual(self.upload(filename="sample.exe").status_code, 415)

    def test_pipeline_review_conflict_and_exports(self):
        meeting = self.ready_meeting()
        self.assertIn("Диаризация не настроена", meeting["analysis"]["warnings"][0])
        meeting["analysis"]["actions"][0]["status"] = "done"
        self.assertEqual(self.review(meeting).status_code, 200)
        self.assertEqual(self.review(meeting).status_code, 409)
        markdown = self.get(f"/api/meetings/{meeting['id']}/export/md", "secretary")
        self.assertIn("Айжан", markdown.text)
        self.assertIn("Выполнено", markdown.text)
        word = self.get(f"/api/meetings/{meeting['id']}/export/docx", "secretary")
        document = Document(BytesIO(word.content))
        self.assertEqual(document.tables[0].rows[1].cells[1].text, "Айжан")
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}/retry", "secretary").status_code, 405)
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}/export/xml", "secretary").status_code, 404)

    def test_missing_meeting(self):
        self.assertEqual(self.get("/api/meetings/unknown", "secretary").status_code, 404)

    def test_audio_is_served_from_storage(self):
        meeting = self.ready_meeting()
        response = self.get(f"/api/meetings/{meeting['id']}/audio", "secretary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"audio")

    def test_delete_removes_recording(self):
        meeting = self.ready_meeting()
        self.assertEqual(self.client.delete(f"/api/meetings/{meeting['id']}", headers=self.auth("secretary")).status_code, 204)
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}", "secretary").status_code, 404)
        self.assertEqual(list((self.settings.data_dir / "audio").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
