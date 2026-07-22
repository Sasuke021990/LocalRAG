"""
Tests for generation.pipeline — the shared answer pipeline — with a mocked
LLM and lightweight fakes for retrieval/rerank/cache. No Redis, no real model.
"""

import pytest

from generation import grounding, pipeline
from utils.config import config


# ─── Fakes ───────────────────────────────────────────────────────────────────

class _Result:
    def __init__(self, content, score, pool="General", file_name="doc.txt"):
        self.content = content
        self.score = score
        self.metadata = {"file_name": file_name, "pool": pool, "chunk_index": 0}


class FakeSearch:
    def __init__(self, results): self._results = results
    def search(self, user_id, query, top_k, pool=None): return self._results


class FakeReranker:
    def rerank(self, query, results, top_k): return results[:top_k]


class FakeCache:
    def __init__(self, hit=None): self.hit = hit; self.saved = []
    def get_cached_result(self, user_id, query):
        if self.hit is None:
            return None
        class C: results = self.hit
        return C()
    def set_cached_result(self, user_id, query, results): self.saved.append(results)


class FakeLLM:
    """Streams a canned output; records whether it was called (for gate tests)
    and the last history it was given (for conversational-memory tests)."""
    def __init__(self, output="", ready=True):
        self.output = output
        self._ready = ready
        self.called = False
        self.last_history = None
    @property
    def ready(self): return self._ready
    async def generate_stream(self, system, user, history=None):
        self.called = True
        self.last_history = history
        for tok in self.output:   # yield char by char to exercise streaming
            yield tok


async def _drain(**kw):
    events = []
    async for ev in pipeline.stream_answer(**kw): events.append(ev)
    return events


def _base(**over):
    kw = dict(
        user_id="u1", query="what is X?", top_k=10, rerank_top_k=5,
        hybrid_search=FakeSearch([_Result("X is a thing.", 0.9)]),
        reranker=FakeReranker(), semantic_cache=FakeCache(), llm=FakeLLM("X is a thing. [1]"),
    )
    kw.update(over)
    return kw


@pytest.mark.anyio
class TestGate:
    async def test_no_results_refuses_without_calling_llm(self):
        llm = FakeLLM("should not run")
        kw = _base(hybrid_search=FakeSearch([]), llm=llm)
        events = await _drain(**kw)
        kinds = [e for e, _ in events]
        assert "refusal" in kinds
        assert "token" not in kinds
        assert llm.called is False

    async def test_below_threshold_refuses(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_MIN_RELEVANCE_SCORE", 0.5)
        llm = FakeLLM("nope")
        kw = _base(hybrid_search=FakeSearch([_Result("weak", 0.1)]), llm=llm)
        events = await _drain(**kw)
        assert any(e == "refusal" for e, _ in events)
        assert llm.called is False

    async def test_no_results_uses_not_found_message(self):
        kw = _base(hybrid_search=FakeSearch([]), llm=FakeLLM("x"))
        events = await _drain(**kw)
        refusal = next(data for ev, data in events if ev == "refusal")
        assert refusal == grounding.NO_RESULTS_MESSAGE

    async def test_irrelevant_results_use_out_of_scope_message(self, monkeypatch):
        # Retrieved something, but below threshold → off-topic wording, not "not found".
        monkeypatch.setattr(config, "LLM_MIN_RELEVANCE_SCORE", 0.5)
        kw = _base(hybrid_search=FakeSearch([_Result("weak", 0.1)]), llm=FakeLLM("x"))
        events = await _drain(**kw)
        refusal = next(data for ev, data in events if ev == "refusal")
        assert refusal == grounding.OUT_OF_SCOPE_MESSAGE


@pytest.mark.anyio
class TestGreeting:
    async def test_greeting_answers_without_retrieval_or_llm(self):
        llm = FakeLLM("should not run")
        search = FakeSearch([_Result("X is a thing.", 0.9)])
        events = await _drain(**_base(query="hi", hybrid_search=search, llm=llm))
        kinds = [e for e, _ in events]
        assert "token" in kinds
        assert "refusal" not in kinds
        assert llm.called is False
        done = events[-1][1]
        assert done["refused"] is False
        assert done["sources"] == []
        assert "vaultly" in done["answer"].lower()

    async def test_thanks_is_treated_as_greeting(self):
        events = await _drain(**_base(query="thank you", llm=FakeLLM("x")))
        done = events[-1][1]
        assert "welcome" in done["answer"].lower()

    async def test_greeting_not_cached(self):
        cache = FakeCache()
        await _drain(**_base(query="hello", semantic_cache=cache, llm=FakeLLM("x")))
        assert cache.saved == []


@pytest.mark.anyio
class TestGeneration:
    async def test_streams_tokens_and_done(self):
        events = await _drain(**_base())
        kinds = [e for e, _ in events]
        assert kinds[0] == "sources"
        assert "token" in kinds
        assert kinds[-1] == "done"
        done = events[-1][1]
        assert "X is a thing." in done["answer"]
        assert done["refused"] is False

    async def test_disabled_llm_falls_back_to_passages(self):
        llm = FakeLLM("", ready=False)
        events = await _drain(**_base(llm=llm))
        assert llm.called is False
        answer = events[-1][1]["answer"]
        assert "relevant passage" in answer.lower()

    async def test_thinking_splits_reasoning_from_answer(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_THINKING_ENABLED", True)
        llm = FakeLLM("<think>let me check passage 1</think>The answer is X. [1]")
        events = await _drain(**_base(llm=llm))
        kinds = [e for e, _ in events]
        assert "thinking" in kinds
        done = events[-1][1]
        assert "let me check" in done["reasoning"]
        assert "The answer is X." in done["answer"]
        assert "<think>" not in done["answer"]

    async def test_cache_hit_skips_generation(self):
        llm = FakeLLM("should not run")
        cache = FakeCache(hit=[{"answer": "cached answer", "sources": [], "reasoning": ""}])
        events = await _drain(**_base(semantic_cache=cache, llm=llm))
        assert llm.called is False
        done = events[-1][1]
        assert done["cached"] is True
        assert done["answer"] == "cached answer"


@pytest.mark.anyio
class TestConversationalMemory:
    async def test_history_reaches_the_llm_trimmed(self):
        llm = FakeLLM("answer")
        history = [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
        ]
        await _drain(**_base(llm=llm, history=history))
        assert llm.last_history == [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
        ]

    async def test_no_history_passes_none_through(self):
        llm = FakeLLM("answer")
        await _drain(**_base(llm=llm))  # no history kwarg
        assert llm.last_history == []

    async def test_history_keeps_only_last_three_exchanges(self):
        llm = FakeLLM("answer")
        # 5 exchanges (10 messages) — only the last 3 (6 messages) should reach the LLM.
        history = []
        for i in range(5):
            history.append({"role": "user", "content": f"q{i}"})
            history.append({"role": "assistant", "content": f"a{i}"})
        await _drain(**_base(llm=llm, history=history))
        assert len(llm.last_history) == 6
        assert llm.last_history[0]["content"] == "q2"
        assert llm.last_history[-1]["content"] == "a4"

    async def test_history_messages_truncated_to_char_budget(self):
        llm = FakeLLM("answer")
        long_answer = "x" * 1000
        history = [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": long_answer},
        ]
        await _drain(**_base(llm=llm, history=history))
        assert len(llm.last_history[-1]["content"]) <= 502  # 500 chars + " …"

    async def test_history_not_sent_on_cache_hit(self):
        # No generation happens on a cache hit, so history is irrelevant/unused —
        # just confirm passing it doesn't break the cache-hit short-circuit.
        llm = FakeLLM("should not run")
        cache = FakeCache(hit=[{"answer": "cached", "sources": [], "reasoning": ""}])
        history = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
        events = await _drain(**_base(semantic_cache=cache, llm=llm, history=history))
        assert llm.called is False
        assert events[-1][1]["answer"] == "cached"


@pytest.fixture
def anyio_backend():
    return "asyncio"
