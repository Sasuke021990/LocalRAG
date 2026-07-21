"""
Answer pipeline — shared by ``POST /query`` (non-streaming) and
``POST /query/stream`` (SSE).

``stream_answer`` is an async generator of ``(event, data)`` tuples:

    ("sources",  [ {file_name, pool, chunk_index, score, content}, ... ])
    ("thinking", "<reasoning text chunk>")     # only when LLM_THINKING_ENABLED
    ("token",    "<answer text chunk>")
    ("refusal",  "<fixed refusal message>")    # instead of tokens, when gated out
    ("done",     {answer, reasoning, sources, refused, cached})

``answer_query`` drains that into a plain dict for the non-streaming route.

The refusal gate runs **before** the model is ever called, and generation is
skipped entirely on a cache hit or when the LLM is disabled (fallback to a
ranked-passage summary) — so this is a strict upgrade over the old behavior,
never a regression.
"""

import logging
from typing import Any, AsyncIterator, Dict, List, Tuple

from generation import grounding
from utils.config import config

logger = logging.getLogger(__name__)


def _sources_from(reranked: List[Any]) -> List[Dict[str, Any]]:
    return [
        {
            "file_name": r.metadata.get("file_name", "Unknown") if r.metadata else "Unknown",
            "pool": r.metadata.get("pool", "General") if r.metadata else "General",
            "chunk_index": r.metadata.get("chunk_index", 0) if r.metadata else 0,
            "score": round(r.score, 4),
            "content": r.content,
        }
        for r in reranked
    ]


def _fallback_answer(query: str, sources: List[Dict[str, Any]]) -> str:
    """Today's behavior — used when the LLM is disabled/unavailable."""
    if not sources:
        return (
            f"No relevant passages found for your query: '{query}'.\n"
            "Try uploading documents to your knowledge base first, or rephrase your question."
        )
    top = ", ".join(f"{s['file_name']} (pool: {s['pool']})" for s in sources[:3])
    body = "\n\n---\n\n".join(
        f"**[{i + 1}] {s['file_name']}** (score: {s['score']:.4f}, chunk #{s['chunk_index']})\n{s['content']}"
        for i, s in enumerate(sources)
    )
    return f"Found {len(sources)} relevant passage(s) for: '{query}'\nTop sources: {top}\n\n{body}"


async def stream_answer(
    *,
    user_id: str,
    query: str,
    top_k: int,
    rerank_top_k: int,
    hybrid_search,
    reranker,
    semantic_cache,
    llm,
) -> AsyncIterator[Tuple[str, Any]]:
    # 1. Cache — instant replay, no retrieval or generation.
    cached = semantic_cache.get_cached_result(user_id, query)
    if cached and cached.results:
        entry = cached.results[0]
        yield ("sources", entry.get("sources", []))
        if entry.get("reasoning"):
            yield ("thinking", entry["reasoning"])
        yield ("token", entry.get("answer", ""))
        yield ("done", {
            "answer": entry.get("answer", ""),
            "reasoning": entry.get("reasoning", ""),
            "sources": entry.get("sources", []),
            "refused": entry.get("refused", False),
            "cached": True,
        })
        return

    # 1b. Greeting / small-talk — answer conversationally, skip retrieval and the
    # model entirely. Not cached (cheap to recompute; keeps the cache for real Qs).
    if grounding.is_greeting(query):
        reply = grounding.greeting_response(query)
        yield ("sources", [])
        yield ("token", reply)
        yield ("done", {
            "answer": reply, "reasoning": "", "sources": [],
            "refused": False, "cached": False,
        })
        return

    # 2. Retrieve + rerank.
    results = hybrid_search.search(user_id, query=query, top_k=top_k)
    reranked = reranker.rerank(query=query, results=results, top_k=rerank_top_k) if rerank_top_k > 0 else results
    sources = _sources_from(reranked)
    yield ("sources", sources)

    # 3. Refusal gate — the model is never invoked past here if it fails. Two
    # distinct messages: nothing retrieved at all vs. retrieved-but-irrelevant.
    if not grounding.passes_relevance_gate(reranked, config.LLM_MIN_RELEVANCE_SCORE):
        message = grounding.NO_RESULTS_MESSAGE if not reranked else grounding.OUT_OF_SCOPE_MESSAGE
        yield ("refusal", message)
        yield ("done", {
            "answer": message, "reasoning": "",
            "sources": sources, "refused": True, "cached": False,
        })
        return  # deliberately not cached — the user may add relevant docs later

    # 4a. LLM disabled/unavailable → ranked-passage fallback (old behavior).
    if not getattr(llm, "ready", False):
        answer = _fallback_answer(query, sources)
        yield ("token", answer)
        semantic_cache.set_cached_result(user_id, query, [{"answer": answer, "sources": sources, "reasoning": ""}])
        yield ("done", {"answer": answer, "reasoning": "", "sources": sources, "refused": False, "cached": False})
        return

    # 4b. Grounded generation.
    system_prompt = grounding.build_system_prompt(
        [s["content"] for s in sources], thinking=config.LLM_THINKING_ENABLED,
    )
    splitter = grounding.ThinkingStreamSplitter()
    answer_parts: List[str] = []
    reasoning_parts: List[str] = []

    async for token in llm.generate_stream(system_prompt, query):
        for phase, text in splitter.feed(token):
            if phase == "thinking":
                reasoning_parts.append(text)
                yield ("thinking", text)
            else:
                answer_parts.append(text)
                yield ("token", text)
    for phase, text in splitter.flush():
        if phase == "thinking":
            reasoning_parts.append(text)
            yield ("thinking", text)
        else:
            answer_parts.append(text)
            yield ("token", text)

    answer = "".join(answer_parts).strip()
    reasoning = "".join(reasoning_parts).strip()
    if not answer:
        # Model produced only reasoning / nothing usable — fall back rather than
        # return an empty answer.
        answer = _fallback_answer(query, sources)
        yield ("token", answer)

    semantic_cache.set_cached_result(
        user_id, query, [{"answer": answer, "sources": sources, "reasoning": reasoning}]
    )
    yield ("done", {"answer": answer, "reasoning": reasoning, "sources": sources, "refused": False, "cached": False})


async def answer_query(*, user_id, query, top_k, rerank_top_k, hybrid_search, reranker, semantic_cache, llm) -> Dict[str, Any]:
    """Non-streaming: drain ``stream_answer`` into a final dict."""
    final = {"answer": "", "reasoning": "", "sources": [], "refused": False}
    async for event, data in stream_answer(
        user_id=user_id, query=query, top_k=top_k, rerank_top_k=rerank_top_k,
        hybrid_search=hybrid_search, reranker=reranker, semantic_cache=semantic_cache, llm=llm,
    ):
        if event == "done":
            final = {k: data[k] for k in ("answer", "reasoning", "sources", "refused")}
    return final
