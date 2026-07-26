"""
Tests for the pluggable LLM backends — backend selection and the
OpenAI-compatible streaming parser (with `requests` mocked; no server needed).
"""

import asyncio
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
    """Mimics requests' streaming Response for SSE chat completions. Accepts
    any iterable for `tokens` (including an infinite generator, for the
    early-cancellation tests) since it's only ever consumed via `for`."""
    def __init__(self, tokens):
        self._tokens = tokens
        self.closed = False
    def raise_for_status(self): pass
    def close(self):
        self.closed = True
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

    async def test_history_spliced_between_system_and_current_user(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_ENABLED", True)
        captured = {}

        def fake_post(url, json=None, headers=None, stream=None, timeout=None):
            captured["json"] = json
            return _FakeStreamResponse(["ok"])

        monkeypatch.setattr(llm_module.requests, "post", fake_post)
        backend = llm_module.OpenAICompatibleLLM()
        history = [{"role": "user", "content": "earlier q"}, {"role": "assistant", "content": "earlier a"}]

        [t async for t in backend.generate_stream("system rules", "the question", history)]

        msgs = captured["json"]["messages"]
        assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
        assert msgs[1]["content"] == "earlier q"
        assert msgs[2]["content"] == "earlier a"
        assert msgs[3]["content"] == "the question"

    async def test_disabled_yields_nothing(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_ENABLED", False)
        backend = llm_module.OpenAICompatibleLLM()
        out = [t async for t in backend.generate_stream("s", "u")]
        assert out == []

    async def test_server_error_before_any_token_raises(self, monkeypatch):
        """
        Regression: this used to silently yield nothing, which the pipeline
        read as "model produced an empty response" and fell back to a raw
        ranked-passage dump — no indication a real outage had happened
        (task.md's mobile-launch audit, §1i). It must now raise so the
        pipeline can surface an explicit "AI unavailable" error instead.
        """
        monkeypatch.setattr(config, "LLM_ENABLED", True)

        def boom(*a, **k):
            raise ConnectionError("server down")

        monkeypatch.setattr(llm_module.requests, "post", boom)
        backend = llm_module.OpenAICompatibleLLM()
        with pytest.raises(ConnectionError):
            [t async for t in backend.generate_stream("s", "u")]

    async def test_server_error_mid_stream_raises_after_partial_tokens(self, monkeypatch):
        def boom_after_two():
            yield "partial"
            yield " answer"
            raise TimeoutError("read timed out")

        fake_resp = _FakeStreamResponse(boom_after_two())
        monkeypatch.setattr(config, "LLM_ENABLED", True)
        monkeypatch.setattr(llm_module.requests, "post", lambda *a, **k: fake_resp)
        backend = llm_module.OpenAICompatibleLLM()

        received = []
        with pytest.raises(TimeoutError):
            async for tok in backend.generate_stream("s", "u"):
                received.append(tok)
        # Tokens already produced before the failure aren't lost.
        assert "".join(received) == "partial answer"
        assert fake_resp.closed is True  # cleanup still ran

    async def test_disconnect_during_a_failing_stream_does_not_raise(self, monkeypatch):
        # A cancellation (client gone) must never be reported as a
        # generation failure, even if the background thread was mid-error
        # when it happened.
        monkeypatch.setattr(config, "LLM_ENABLED", True)

        def infinite_tokens():
            while True:
                yield "x"

        fake_resp = _FakeStreamResponse(infinite_tokens())
        monkeypatch.setattr(llm_module.requests, "post", lambda *a, **k: fake_resp)
        backend = llm_module.OpenAICompatibleLLM()
        agen = backend.generate_stream("s", "u")
        await asyncio.wait_for(agen.__anext__(), timeout=5)
        await asyncio.wait_for(agen.aclose(), timeout=5)  # must not raise

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

    async def test_normal_completion_closes_the_connection(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_ENABLED", True)
        fake_resp = _FakeStreamResponse(["a", "b"])
        monkeypatch.setattr(llm_module.requests, "post", lambda *a, **k: fake_resp)
        backend = llm_module.OpenAICompatibleLLM()
        [t async for t in backend.generate_stream("s", "u")]
        assert fake_resp.closed is True

    async def test_client_disconnect_stops_generation_and_closes_connection(self, monkeypatch):
        """
        Regression test for the "navigate away mid-answer" bug: main.py's
        query_stream calls agen.aclose() the moment it detects the client
        disconnected. That must propagate all the way down into this
        background-thread HTTP call -- stopping it from pulling further
        tokens and closing the connection to the inference server, instead
        of it running to completion (or, as here, forever) for an answer
        nobody will receive.

        Uses an infinite token source: without the cancel_event fix, this
        test would hang until the asyncio.wait_for timeouts below fire,
        making a regression an unambiguous failure rather than a flake.
        """
        monkeypatch.setattr(config, "LLM_ENABLED", True)

        def infinite_tokens():
            while True:
                yield "x"

        fake_resp = _FakeStreamResponse(infinite_tokens())
        monkeypatch.setattr(llm_module.requests, "post", lambda *a, **k: fake_resp)
        backend = llm_module.OpenAICompatibleLLM()
        agen = backend.generate_stream("s", "u")

        first = await asyncio.wait_for(agen.__anext__(), timeout=5)
        assert first == "x"

        # Simulates the client disconnecting mid-stream.
        await asyncio.wait_for(agen.aclose(), timeout=5)

        # The background thread runs concurrently -- give it a brief window
        # to notice cancel_event and run its own finally block.
        for _ in range(50):
            if fake_resp.closed:
                break
            await asyncio.sleep(0.05)
        assert fake_resp.closed is True


@pytest.mark.anyio
class TestEmbeddedStreaming:
    def _fake_backend(self, monkeypatch, chunk_source):
        monkeypatch.setattr(config, "LLM_ENABLED", True)
        backend = llm_module.EmbeddedLLM()
        backend._loaded = True
        backend._llama = lambda prompt, max_tokens, temperature, stream: chunk_source()
        return backend

    async def test_streams_tokens(self, monkeypatch):
        backend = self._fake_backend(
            monkeypatch, lambda: iter({"choices": [{"text": c}]} for c in ["Hello", " ", "world"]),
        )
        out = [t async for t in backend.generate_stream("sys", "user")]
        assert "".join(out) == "Hello world"

    async def test_generation_error_before_any_token_raises(self, monkeypatch):
        def boom():
            raise RuntimeError("llama.cpp crashed")
            yield  # pragma: no cover — makes this a generator; never reached

        backend = self._fake_backend(monkeypatch, boom)
        with pytest.raises(RuntimeError):
            [t async for t in backend.generate_stream("sys", "user")]

    async def test_generation_error_mid_stream_raises_after_partial_tokens(self, monkeypatch):
        def boom_after_two():
            yield {"choices": [{"text": "partial"}]}
            yield {"choices": [{"text": " answer"}]}
            raise RuntimeError("llama.cpp crashed")

        backend = self._fake_backend(monkeypatch, boom_after_two)
        received = []
        with pytest.raises(RuntimeError):
            async for tok in backend.generate_stream("sys", "user"):
                received.append(tok)
        assert "".join(received) == "partial answer"

    async def test_client_disconnect_stops_pulling_more_chunks(self, monkeypatch):
        """
        Same regression as the OpenAI-compatible backend, for the embedded
        llama.cpp path: an infinite chunk source would hang forever without
        the cancel_event check, since nothing else would ever stop the
        background thread's `for chunk in self._llama(...)` loop.
        """
        def infinite_chunks():
            while True:
                yield {"choices": [{"text": "x"}]}

        backend = self._fake_backend(monkeypatch, infinite_chunks)
        agen = backend.generate_stream("sys", "user")

        first = await asyncio.wait_for(agen.__anext__(), timeout=5)
        assert first == "x"

        # Would hang past the timeout (failing the test) if the background
        # thread never checks cancel_event and keeps consuming the infinite
        # generator forever.
        await asyncio.wait_for(agen.aclose(), timeout=5)


@pytest.fixture
def anyio_backend():
    return "asyncio"
