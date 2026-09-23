import json
import unittest
from dataclasses import replace
from unittest.mock import patch

import httpx

from app.config import Settings
from app.pipeline import Provider


class TextEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_qwen_endpoint_has_no_asr_credential(self):
        settings = replace(Settings.from_env(), api_key="asr-secret", text_base_url="http://localhost:8769/v1", text_api_key="", text_enable_thinking=False)

        def respond(request):
            self.assertEqual(str(request.url), "http://localhost:8769/v1/chat/completions")
            self.assertNotIn("authorization", request.headers)
            self.assertFalse(json.loads(request.content)["chat_template_kwargs"]["enable_thinking"])
            return httpx.Response(200, json={"ok": True})

        with patch("app.pipeline.httpx.AsyncClient", return_value=httpx.AsyncClient(transport=httpx.MockTransport(respond))):
            self.assertTrue((await Provider(settings).request("/chat/completions", json={"messages": []}))["ok"])

    async def test_asr_keeps_original_endpoint_and_key(self):
        settings = replace(Settings.from_env(), api_key="asr-secret", base_url="http://asr/v1", text_base_url="http://llm/v1", text_enable_thinking=False)

        def respond(request):
            self.assertEqual(str(request.url), "http://asr/v1/audio/transcriptions")
            self.assertEqual(request.headers["authorization"], "Bearer asr-secret")
            return httpx.Response(200, json={"text": "test"})

        with patch("app.pipeline.httpx.AsyncClient", return_value=httpx.AsyncClient(transport=httpx.MockTransport(respond))):
            self.assertEqual((await Provider(settings).request("/audio/transcriptions", data={"model": "til-asr"}))["text"], "test")
