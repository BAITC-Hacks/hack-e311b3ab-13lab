import json
import unittest
from io import BytesIO

from docx import Document

from app.config import Settings
from app.deadlines import ground_deadlines
from app.exports import docx, markdown
from app.models import Action, Analysis, DeadlineAlternative, Segment
from app.pipeline import Provider, validate_evidence
from app.quality import numeric_fragments


class QualityTests(unittest.TestCase):
    def test_numbers_require_source_context_not_just_digits(self):
        source = Segment(id="s1", text="Загрузка семьдесят один процент. Потери 8%.")
        fragments = numeric_fragments([source], "Готовность 71%. Потери 8%.")
        self.assertEqual([item.included for item in fragments], [False, True])
        self.assertEqual(numeric_fragments([Segment(id="s2", text="Жеті күн. Перенос на полгода.")], "")[1].text, "Перенос на полгода.")

    def test_details_require_exact_evidence(self):
        action = Action(title="Отчёт", evidence="Доложите лично.", deliverable="Личный доклад", deliverable_evidence="Доложите лично.", condition="Расторгнуть договор", condition_evidence="Выдуманная цитата", issued_by="Асхат")
        result = validate_evidence(Analysis(summary="", actions=[action]), [Segment(id="s1", text=action.evidence)])
        self.assertEqual(result.actions[0].deliverable, "Личный доклад")
        self.assertIsNone(result.actions[0].condition)
        self.assertIsNone(result.actions[0].issued_by)

    def test_chair_can_be_owner_with_evidence(self):
        quote = "Асхат, подготовьте отчёт."
        action = Action(title="Отчёт", owner="Асхат", evidence=quote, owner_evidence=quote, issued_by="Тимур", issued_by_evidence="Тимур поручил отчёт.")
        result = validate_evidence(Analysis(summary="", actions=[action]), [Segment(id="s1", text=quote + " Тимур поручил отчёт.")])
        self.assertEqual(result.actions[0].owner, "Асхат")
        self.assertEqual(result.actions[0].issued_by, "Тимур")

    def test_event_deadline_keeps_text_without_date(self):
        action = Action(title="Справка", evidence="Подготовьте справку после совещания с подрядчиками.", deadline_text="после совещания с подрядчиками", due_date="2026-09-25")
        result = ground_deadlines(Analysis(summary="", actions=[action]), "2026-09-23")
        self.assertEqual(result.actions[0].deadline_resolution, "event")
        self.assertIsNone(result.actions[0].due_date)
        self.assertEqual(result.actions[0].deadline_text, "после совещания с подрядчиками")

    def test_conflicts_do_not_silently_pick_date(self):
        source = Segment(id="s1", text="Срок две недели или максимум десять дней, уточним.")
        action = Action(title="Отчёт", evidence=source.text, deadline_text="максимум десять дней", deadline_alternatives=[DeadlineAlternative(text="две недели", segment_id="s1"), DeadlineAlternative(text="максимум десять дней", segment_id="s1"), DeadlineAlternative(text="завтра", segment_id="invented")])
        result = ground_deadlines(validate_evidence(Analysis(summary="", actions=[action]), [source]), "2026-09-23")
        self.assertEqual(result.actions[0].deadline_resolution, "conflict")
        self.assertIsNone(result.actions[0].due_date)
        self.assertEqual(len(result.actions[0].deadline_alternatives), 2)

    def test_explicit_final_deadline_resolves(self):
        action = Action(title="Отчёт", evidence="Согласовали максимум десять дней.", deadline_text="максимум десять дней")
        result = ground_deadlines(Analysis(summary="", actions=[action]), "2026-09-23")
        self.assertEqual(str(result.actions[0].due_date), "2026-10-03")
        self.assertEqual(result.actions[0].deadline_resolution, "resolved")

    def test_exports_keep_details_and_conflict_sources(self):
        action = Action(title="Отчёт", evidence="Доложите лично.", deliverable="Личный доклад", condition="При нарушениях", deadline_resolution="conflict", deadline_alternatives=[DeadlineAlternative(text="две недели", segment_id="s1")])
        meeting = {"title":"Тест", "meeting_date":"2026-09-23", "analysis":Analysis(summary="Тест", actions=[action]).model_dump(mode="json"), "transcript":"Доложите лично.", "segments":[]}
        document = Document(BytesIO(docx(meeting)))
        self.assertIn("Личный доклад", document.tables[0].rows[1].cells[0].text)
        self.assertIn("две недели [s1]", document.tables[0].rows[1].cells[2].text)
        self.assertIn("При нарушениях", markdown(meeting))


class SummaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_corrective_pass_preserves_numeric_context(self):
        provider = Provider(Settings.from_env())
        calls = []

        async def request(endpoint, **kwargs):
            calls.append(json.loads(json.dumps(kwargs)))
            summary = "Обсудили загрузку." if len(calls) == 1 else "Загрузка 71%."
            return {"choices":[{"finish_reason":"stop", "message":{"content":json.dumps({"summary":summary})}}]}

        provider.request = request
        result = await provider.summarize([Segment(id="s1", text="Загрузка 71%.")])
        self.assertEqual(result, "Загрузка 71%.")
        self.assertEqual(len(calls), 2)
        self.assertIn("Загрузка 71%.", calls[1]["json"]["messages"][-1]["content"])

    async def test_correction_is_bounded_when_model_omits_numbers(self):
        provider = Provider(Settings.from_env())
        calls = []

        async def request(endpoint, **kwargs):
            calls.append(endpoint)
            return {"choices":[{"finish_reason":"stop", "message":{"content":'{"summary":"Обсудили загрузку."}'}}]}

        provider.request = request
        result = await provider.summarize([Segment(id="s1", text="Загрузка 71%.")])
        self.assertEqual(len(calls), 2)
        self.assertFalse(numeric_fragments([Segment(id="s1", text="Загрузка 71%.")], result)[0].included)
