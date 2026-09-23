import asyncio
import json
import unittest

import httpx

from app.models import Segment
from app.pipeline import Provider
from tests.helpers import make_settings

EVIDENCE = "Айжан подготовит отчёт к пятнице."
DRAFT = {"summary": "Черновик", "decisions": [], "actions": [{"title": "Подготовить отчёт", "owner": "Айжан", "deadline_text": "к пятнице", "due_date": None, "evidence": EVIDENCE, "segment_ids": ["s1"]}], "warnings": []}
REVIEWED = DRAFT | {"summary": "Проверено"}


def reply(content):
    return {"choices": [{"message": {"content": content}}]}


def server_error(status=500):
    request = httpx.Request("POST", "https://models.example/v1/chat/completions")
    return httpx.HTTPStatusError("error", request=request, response=httpx.Response(status, request=request))


class ScriptedProvider(Provider):
    def __init__(self, *answers):
        super().__init__(make_settings(".", api_key="test"))
        self.answers = list(answers)
        self.budgets = []

    async def request(self, endpoint, **kwargs):
        self.budgets.append(kwargs["json"]["max_tokens"])
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return reply(answer)


def analyze(provider):
    return asyncio.run(provider.analyze([Segment(id="s1", text=EVIDENCE, start=0, end=3)], "2026-09-23", "Тест"))


class ReviewPassTests(unittest.TestCase):
    def test_reviewed_result_is_used(self):
        result = analyze(ScriptedProvider(json.dumps(DRAFT), "```json\n" + json.dumps(REVIEWED) + "\n```"))
        self.assertEqual(result.summary, "Проверено")
        self.assertFalse(any("Второй проход" in warning for warning in result.warnings))

    def test_review_server_errors_fall_back_to_the_checked_draft(self):
        provider = ScriptedProvider(json.dumps(DRAFT), server_error(), server_error())
        result = analyze(provider)
        self.assertEqual(provider.budgets, [6500, 6500, 2500])
        self.assertEqual(result.summary, "Черновик")
        self.assertEqual(len(result.actions), 1)
        self.assertTrue(any("Второй проход" in warning for warning in result.warnings))

    def test_retry_with_smaller_budget_can_succeed(self):
        result = analyze(ScriptedProvider(json.dumps(DRAFT), server_error(), json.dumps(REVIEWED)))
        self.assertEqual(result.summary, "Проверено")

    def test_invalid_review_json_falls_back_to_draft(self):
        result = analyze(ScriptedProvider(json.dumps(DRAFT), "не JSON"))
        self.assertEqual(result.summary, "Черновик")
        self.assertTrue(any("Второй проход" in warning for warning in result.warnings))

    def test_client_errors_and_bad_first_pass_are_not_masked(self):
        with self.assertRaises(httpx.HTTPStatusError):
            analyze(ScriptedProvider(json.dumps(DRAFT), server_error(401)))
        with self.assertRaises(httpx.HTTPStatusError):
            analyze(ScriptedProvider(server_error()))
        with self.assertRaises(ValueError):
            analyze(ScriptedProvider("не JSON", "тоже не JSON"))


if __name__ == "__main__":
    unittest.main()
