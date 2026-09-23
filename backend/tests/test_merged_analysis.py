import json
import unittest
from dataclasses import replace
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.deadlines import ground_deadlines
from app.models import Action, Analysis, Segment
from app.pipeline import Provider, validate_evidence


class MergedGroundingTests(unittest.TestCase):
    def test_main_deadline_cannot_silently_override_an_alternative(self):
        from app.models import DeadlineAlternative
        source = Segment(id="s1", text="За две недели найдите поставщика. Максимум десять дней.")
        action = Action(title="Поставщик", evidence=source.text, deadline_text="Максимум десять дней", deadline_alternatives=[DeadlineAlternative(text="За две недели найдите поставщика", segment_id="s1")])
        result = ground_deadlines(validate_evidence(Analysis(summary="", actions=[action]), [source]), "2026-09-23")
        self.assertEqual(result.actions[0].deadline_resolution, "conflict")
        self.assertIsNone(result.actions[0].due_date)
        self.assertEqual(len(result.actions[0].deadline_alternatives), 2)

    def test_missing_event_phrase_is_recovered_only_from_action_evidence(self):
        action = Action(title="Справка", evidence="Мне по итогам этого совещания короткую справку.")
        result = ground_deadlines(Analysis(summary="", actions=[action]), "2026-09-23")
        self.assertEqual(result.actions[0].deadline_text, "по итогам этого совещания")
        self.assertEqual(result.actions[0].deadline_resolution, "event")

    def test_recovery_only_from_contiguous_valid_segments(self):
        segments = [Segment(id="s1", text="Айжан,"), Segment(id="s2", text="подготовьте отчёт."), Segment(id="s3", text="Спасибо.")]
        for ids, retained in [(["s1", "s2"], True), (["s1", "s3"], False), (["bad"], False), ([], False), (["s2", "s1"], False)]:
            action = Action(title="Отчёт", evidence="Неточная цитата", segment_ids=ids)
            result = validate_evidence(Analysis(summary="", actions=[action]), segments)
            self.assertEqual(bool(result.actions), retained)
            if retained:
                self.assertEqual(result.actions[0].evidence, "Айжан, подготовьте отчёт.")
                self.assertTrue(result.actions[0].review_questions)

    def test_invented_owner_cleared_and_internal_ids_not_accepted(self):
        action = Action(title="Отчёт", evidence="Подготовьте отчёт.", owner="Асхат", owner_evidence="Асхат, подготовьте отчёт.", id="forged", assignee_id="admin")
        result = validate_evidence(Analysis(summary="", actions=[action]), [Segment(id="s1", text="Подготовьте отчёт.")])
        self.assertIsNone(result.actions[0].owner)
        self.assertIsNone(result.actions[0].assignee_id)
        self.assertNotEqual(result.actions[0].id, "forged")

    def test_event_and_noisy_deadlines_have_no_date(self):
        for phrase, resolution in [("по итогам этого совещания", "event"), ("мне больше недели", "uncertain")]:
            action = Action(title="Отчёт", evidence="Отчёт", deadline_text=phrase)
            result = ground_deadlines(Analysis(summary="", actions=[action]), "2026-09-23")
            self.assertEqual(result.actions[0].deadline_resolution, resolution)
            self.assertIsNone(result.actions[0].due_date)

    def test_model_event_label_does_not_override_calendar_phrase(self):
        action = Action(title="Отчёт", evidence="Отчёт", deadline_text="до тридцатого сентября", deadline_resolution="event")
        result = ground_deadlines(Analysis(summary="", actions=[action]), "2026-09-23")
        self.assertEqual(result.actions[0].deadline_resolution, "resolved")
        self.assertEqual(str(result.actions[0].due_date), "2026-09-30")

    def test_numeric_quotes_allow_punctuation_but_not_missing_context(self):
        from app.quality import numeric_fragments
        segment = Segment(id="s1", text="Загрузка 71%,")
        self.assertTrue(numeric_fragments([segment], "«Загрузка 71%»")[0].included)
        self.assertFalse(numeric_fragments([segment], "Потери 71%.")[0].included)

    def test_summary_cannot_drop_negation_inside_a_quote(self):
        from app.quality import validate_summary_quotes
        segments = [Segment(id="s1", text="Три недели, но не больше.")]
        self.assertEqual(validate_summary_quotes("Срок: «Три недели, но не больше».", segments), "Срок: «Три недели, но не больше».")
        result = validate_summary_quotes("Срок: «Три недели, но больше».", segments)
        self.assertNotIn("но больше", result)
        self.assertIn("требуется проверка", result)


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_receives_uncertainty_in_a_single_system_message(self):
        provider = Provider(Settings.from_env())
        async def request(*args, **kwargs):
            messages = kwargs["json"]["messages"]
            self.assertEqual([message["role"] for message in messages], ["system", "user"])
            constraints = json.loads(messages[1]["content"])["review_constraints"]
            self.assertEqual(constraints[0]["deadline_resolution"], "uncertain")
            self.assertIsNone(constraints[0]["owner"])
            return {"choices": [{"message": {"content": '{"summary":"Срок требует уточнения."}'}}]}
        provider.request = request
        await provider.summarize([Segment(id="s1", text="Срок неясен.")], [Action(title="Шаблон", evidence="Срок неясен.", deadline_resolution="uncertain")])

    async def test_http_retry_is_bounded(self):
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(503, json={"error": "temporary"})
        settings = replace(Settings.from_env(), text_base_url="http://llm/v1")
        with patch("app.pipeline.httpx.AsyncClient", return_value=httpx.AsyncClient(transport=httpx.MockTransport(respond))), patch("app.pipeline.asyncio.sleep"):
            with self.assertRaises(httpx.HTTPStatusError):
                await Provider(settings).request("/chat/completions", json={"messages": []})
        self.assertEqual(len(calls), 2)

    async def test_json_repair_is_bounded(self):
        provider = Provider(Settings.from_env())
        calls = []
        async def request(*args, **kwargs):
            calls.append(kwargs)
            return {"choices": [{"message": {"content": "broken"}}]}
        provider.request = request
        with self.assertRaises(ValidationError):
            await provider.parse_analysis("broken", [])
        self.assertEqual(len(calls), 1)

    async def test_successful_json_repair(self):
        provider = Provider(Settings.from_env())
        async def request(*args, **kwargs):
            return {"choices": [{"message": {"content": json.dumps({"summary": "Отчёт"})}}]}
        provider.request = request
        self.assertEqual((await provider.parse_analysis("broken", [])).summary, "Отчёт")
