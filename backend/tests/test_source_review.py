import unittest
from io import BytesIO

from docx import Document

from app.source_review import suggestions
from tests.helpers import AppTestCase


class SuggestionTests(unittest.TestCase):
    def test_dictionary_is_only_a_suggestion_and_handles_kazakh(self):
        segments = [{"id": "s1", "text": "Ботагус, Атырауская. Әсемгүл."}]
        result = suggestions(segments, ["Ботагоз", "Павлодарская", "Әсемгул"])
        self.assertEqual([item["original"] for item in result], ["Ботагус", "Әсемгүл"])
        self.assertEqual(result[0]["candidates"], ["Ботагоз"])
        self.assertEqual(segments[0]["text"], "Ботагус, Атырауская. Әсемгүл.")
        self.assertEqual(suggestions(segments, []), [])

    def test_multiple_candidates_are_not_silently_resolved(self):
        result = suggestions([{"id": "s1", "text": "Ботагус"}], ["Ботагоз", "Ботагул"])
        self.assertEqual(len(result[0]["candidates"]), 2)


class SourceReviewTests(AppTestCase):
    def test_numeric_counter_is_recomputed_after_manual_edit(self):
        meeting = self.ready_meeting()
        self.store.update(meeting["id"], {"segments": [{"id": "s1", "text": "Потери 8%.", "start": 0, "end": 3}]})
        meeting = self.get(f"/api/meetings/{meeting['id']}", "secretary").json()
        meeting["analysis"]["summary"] = "Обсуждали потери"
        meeting["analysis"]["numeric_fragments"] = [{"segment_id": "s1", "text": "Выдумка", "included": True}]
        result = self.review(meeting)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["analysis"]["numeric_fragments"], [{"segment_id": "s1", "text": "Потери 8%.", "included": False}])

    def note(self, **changes):
        return {"kind": "correction", "segment_id": "s1", "original": "Айжан", "text": "Айдан", "audio_checked": True, **changes}

    def test_review_preserves_raw_source_and_exports_notes(self):
        meeting = self.ready_meeting()
        result = self.review(meeting, source_review={"notes": [self.note()]} )
        self.assertEqual(result.status_code, 200, result.text)
        saved = result.json()
        for field in ("transcript", "segments", "analysis"):
            self.assertEqual(saved[field], meeting[field])
        self.assertEqual(self.review(meeting, source_review={"notes": []}).status_code, 409)
        self.assertEqual(self.review(saved).json()["source_review"], saved["source_review"])
        markdown = self.get(f"/api/meetings/{meeting['id']}/export/md", "secretary").text
        self.assertIn("«Айжан» → Айдан", markdown)
        content = self.get(f"/api/meetings/{meeting['id']}/export/docx", "secretary").content
        self.assertIn("Айдан", "\n".join(paragraph.text for paragraph in Document(BytesIO(content)).paragraphs))

    def test_invalid_sources_and_unconfirmed_claims_rejected(self):
        meeting = self.ready_meeting()
        for note in [self.note(segment_id="missing"), self.note(original="Не было"), self.note(audio_checked=False), self.note(text=" "), self.note(kind="supplement", audio_checked=False), self.note(kind="owner", action_id="missing")]:
            self.assertEqual(self.review(meeting, source_review={"notes": [note]}).status_code, 422, note)

    def test_speaker_is_per_segment_and_unknown_remains_possible(self):
        meeting = self.ready_meeting()
        note = self.note(kind="speaker", original="", text="Айжан")
        result = self.review(meeting, source_review={"notes": [note]})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["speaker_names"], meeting["speaker_names"])
        self.assertEqual(self.review(result.json(), source_review={"notes": [note, note]}).status_code, 422)
        note = self.note(kind="uncertain", original="", text="Дату не разобрать", audio_checked=False)
        self.assertEqual(self.review(result.json(), source_review={"notes": [note]}).status_code, 200)

    def test_owner_confirmation_cannot_become_stale(self):
        meeting = self.ready_meeting()
        action = meeting["analysis"]["actions"][0]
        note = self.note(kind="owner", original="", text=action["owner"], action_id=action["id"])
        result = self.review(meeting, source_review={"notes": [note]})
        self.assertEqual(result.status_code, 200, result.text)
        changed = result.json()
        changed["analysis"]["actions"][0]["owner"] = "Другое имя"
        self.assertEqual(self.review(changed).status_code, 422)

    def test_permissions_and_approval_lock(self):
        meeting = self.ready_meeting()
        endpoint = f"/api/meetings/{meeting['id']}/source-suggestions"
        for role in ("auditor", "participant"):
            self.assertIn(self.client.post(endpoint, headers=self.auth(role), json={"terms": ["Айдан"]}).status_code, (403, 404))
            self.assertNotIn("source_review", self.get(f"/api/meetings/{meeting['id']}", role).json())
        self.assertEqual(self.client.post(endpoint, headers=self.auth("admin"), json={"terms": ["Айдан"]}).status_code, 200)  # admins have full access
        self.assertEqual(self.client.post(endpoint, headers=self.auth("secretary"), json={"terms": ["Айдан"]}).status_code, 200)
        self.assertEqual(self.client.post(endpoint, headers=self.auth("secretary"), json={"terms": ["x" * 201]}).status_code, 422)
        approved = self.approve(meeting)
        self.assertEqual(self.review(approved, source_review={"notes": [self.note()]}).status_code, 409)
