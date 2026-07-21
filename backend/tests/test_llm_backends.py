"""
Tests for the pluggable LLM backends — backend selection and the
OpenAI-compatible streaming parser (with `requests` mocked; no server needed).
"""

import json

import pytest

from generation import llm as llm_module
from utils.config import config


class TestBackendSelection:
    def test_default_is_embedded(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_BACKEND", "embedded")
        assert isinstance(llm_module.get_llm(), llm_module.EmbeddedLLM)

    def test_openai_backend_selected(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_BACKEND", "openai")
        assert isinstance(llm_module.get_llm(), llm_module.OpenAICompatibleLLM)

    def test_openai_case_insensitive(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_BACKEND", "OpenAI")
        assert isinstance(llm_module.get_llm(), llm_module.OpenAICompatibleLLM)


class _FakeStreamResponse:
    """Mimics requests' streaming Response for SSE chat completions."""
    def __init__(self, tokens):
        self._tokens = tokens
    def raise_for_status(self): pass
    def iter_lines(self, decode_unicode=True):
        for t in self._tokens:
            yield "data: " + json.dumps({"choices": [{"delta": {"content": t}}]})
        yield "data: [DONE]"


@pytest.mark.anyio
class TestOpenAIStreaming:
    async def test_streams_delta_content(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_ENABLED", True)
        captured = {}

        def fake_post(url, json=None, headers=None, stream=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _FakeStreamResponse(["Hello", " ", "world"])

        monkeypatch.setattr(llm_module.requests, "post", fake_post)
        backend = llm_module.OpenAICompatibleLLM()

        out = []
        async for tok in backend.generate_stream("system rules", "the question"):
            out.append(tok)

        assert "".join(out) == "Hello world"
        # It POSTs chat/completions with system+user messages and streaming on.
        assert captured["url"].endswith("/chat/completions")
        roles = [m["role"] for m in captured["json"]["messages"]]
        assert roles == ["system", "user"]
        assert captured["json"]["stream"] is True

    async def test_disabled_yields_nothing(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_ENABLED", False)
        backend = llm_module.OpenAICompatibleLLM()
        out = [t async for t in backend.generate_stream("s", "u")]
        assert out == []

    async def test_server_error_degrades_to_empty(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_ENABLED", True)

        def boom(*a, **k):
            raise ConnectionError("server down")

        monkeypatch.setattr(llm_module.requests, "post", boom)
        backend = llm_module.OpenAICompatibleLLM()
        out = [t async for t in backend.generate_stream("s", "u")]
        assert out == []  # never raises — pipeline falls back to passages

    async def test_bearer_key_sent_when_configured(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_ENABLED", True)
        monkeypatch.setattr(config, "LLM_API_KEY", "secret-key")
        captured = {}
        monkeypatch.setattr(
            llm_module.requests, "post",
            lambda url, json=None, headers=None, stream=None, timeout=None: (captured.update(headers=headers), _FakeStreamResponse(["x"]))[1],
        )
        backend = llm_module.OpenAICompatibleLLM()
        [t async for t in backend.generate_stream("s", "u")]
        assert captured["headers"]["Authorization"] == "Bearer secret-key"


@pytest.fixture
def anyio_backend():
    return "asyncio"
