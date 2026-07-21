"""
Grounding logic for AI answers — pure functions, no model or Redis needed.

The product rule (confirmed with the user): the AI must answer **only** from
the user's own retrieved documents — never its own world knowledge — and
**refuse** when the documents don't contain the answer. No LLM can be
mathematically forced to ignore its training, so enforcement is layered and
the intended failure mode is *refusal, not hallucination*:

1. A **refusal gate runs before the model is ever invoked** — empty retrieval
   or a top relevance score below the configured threshold returns the fixed
   refusal message and no generation happens.
2. A **hard system prompt** constrains the model to the numbered context
   passages, with deterministic decoding (temperature 0).
3. **Citations** are always returned — the exact passages given to the model.

This module holds (1) the gate, (2) the prompt builder (thinking-aware), and
(3) a parser that separates a model's optional <think> reasoning from its
final answer.
"""

import re
from typing import Any, List, Tuple

# Shown when retrieval comes back empty — nothing in the knowledge base matched.
NO_RESULTS_MESSAGE = (
    "I couldn't find anything about that in your documents or knowledge pools. "
    "Try uploading relevant files or rephrasing your question."
)

# Shown when the user asks something the retrieved passages don't cover — the
# grounded assistant has no world knowledge of its own to fall back on. Also
# the exact string the model is told to emit when the passages don't answer.
OUT_OF_SCOPE_MESSAGE = (
    "I can only answer using your documents and knowledge pools — "
    "I don't have knowledge beyond them."
)

# Back-compat alias: existing callers/tests import ``REFUSAL_MESSAGE`` and the
# grounded system prompt tells the model to reply with this exact string when
# the passages don't contain the answer.
REFUSAL_MESSAGE = OUT_OF_SCOPE_MESSAGE

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)

# Matches only when the *entire* message is a greeting / thanks / small-talk /
# capability question — so "hi" greets, but "hi, what does doc 3 say?" still
# goes through retrieval. Anchored at both ends; trailing punctuation allowed.
_GREETING_RE = re.compile(
    r"^\s*(?:"
    r"hi+|hey+|hello+|yo+|hiya|heya|howdy|"
    r"good\s*(?:morning|afternoon|evening|day)|greetings|"
    r"thanks(?:\s*a\s*lot)?|thank\s*you|thanx|thx|ty|cheers|"
    r"bye|goodbye|see\s*ya|see\s*you|"
    r"how\s*(?:are|r)\s*(?:you|u)(?:\s*doing)?|how'?s\s*it\s*going|"
    r"what'?s\s*up|wass?up|sup|"
    r"who\s*(?:are|r)\s*(?:you|u)|what\s*(?:can|do)\s*you\s*do|help"
    r")[\s!.,?'\"-]*$",
    re.IGNORECASE,
)


def is_greeting(query: str) -> bool:
    """True if the whole message is a greeting / thanks / small-talk / 'who are
    you' — cases the assistant should answer conversationally rather than treat
    as a document lookup."""
    return bool(_GREETING_RE.match(query or ""))


def greeting_response(query: str) -> str:
    """A short, friendly canned reply for a greeting/small-talk message. Canned
    (not model-generated) so it's instant, deterministic, and works even when
    the LLM is disabled — and always steers the user back to their documents."""
    q = (query or "").strip().lower()
    if q.startswith(("thank", "thanx", "thx", "ty", "cheers")):
        return "You're welcome! Ask me anything about your documents or knowledge pools."
    if q.startswith(("bye", "goodbye", "see ya", "see you")):
        return "Goodbye! Come back anytime you need answers from your knowledge base."
    if "who are you" in q or "who r you" in q or "what can you do" in q or "what do you do" in q or q == "help":
        return (
            "I'm Vaultly's assistant. I answer questions using only your uploaded "
            "documents and knowledge pools — ask me about anything you've added."
        )
    return (
        "Hi! 👋 I'm Vaultly's assistant. Ask me anything about your documents "
        "and knowledge pools."
    )


def passes_relevance_gate(reranked_results: List[Any], threshold: float) -> bool:
    """
    True only if there is at least one retrieved result whose score meets the
    threshold. ``reranked_results`` items may be objects with a ``.score``
    attribute or dicts with a ``"score"`` key.
    """
    if not reranked_results:
        return False

    def _score(r):
        return r["score"] if isinstance(r, dict) else getattr(r, "score", None)

    scores = [s for s in (_score(r) for r in reranked_results) if s is not None]
    if not scores:
        return False
    return max(scores) >= threshold


def _truncate_to_budget(chunks: List[str], char_budget: int) -> List[str]:
    """
    Keep as many whole chunks as fit in ``char_budget`` (in order); the chunk
    that would overflow is included but truncated, the rest are dropped. This
    protects the model's context window without silently losing the top hits.
    """
    out = []
    used = 0
    for c in chunks:
        if used >= char_budget:
            break
        remaining = char_budget - used
        if len(c) <= remaining:
            out.append(c)
            used += len(c)
        else:
            out.append(c[:remaining].rstrip() + " …")
            used = char_budget
    return out


def build_system_prompt(
    chunks: List[str],
    thinking: bool = False,
    char_budget: int = 8000,
) -> str:
    """
    Backend-neutral system instruction: constrains the model to the numbered
    context passages and tells it to refuse if they don't contain the answer.
    Used by both the embedded (raw-prompt) and the OpenAI-compatible (chat
    messages) backends. When ``thinking`` is True the model is asked to reason
    inside a ``<think>…</think>`` block first (see ``split_thinking``).
    """
    kept = _truncate_to_budget(chunks, char_budget)
    context = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(kept)) or "(no passages)"

    reasoning_line = (
        "First reason step by step inside a <think></think> block, then give the final answer.\n"
        if thinking
        else ""
    )

    return (
        "You are Vaultly's assistant. Answer the user's question using ONLY the "
        "numbered context passages below, which come from the user's own documents.\n"
        "Rules:\n"
        "- Use ONLY the passages. Never use outside or prior knowledge.\n"
        "- If the message is only a greeting or small talk, reply briefly and "
        "warmly, then invite them to ask about their documents.\n"
        f"- If the passages do not contain the answer, reply EXACTLY: \"{OUT_OF_SCOPE_MESSAGE}\"\n"
        "- Cite the passages you use like [1], [2].\n"
        f"{reasoning_line}"
        "\nContext passages:\n"
        f"{context}"
    )


def format_chat_prompt(system: str, user: str) -> str:
    """Wrap a system + user message in the Qwen chat template (embedded backend)."""
    return (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )


def build_grounded_prompt(
    query: str,
    chunks: List[str],
    thinking: bool = False,
    char_budget: int = 8000,
) -> str:
    """Qwen-template raw prompt string for the embedded (completion) backend."""
    return format_chat_prompt(build_system_prompt(chunks, thinking, char_budget), query)


def build_grounded_messages(
    query: str,
    chunks: List[str],
    thinking: bool = False,
    char_budget: int = 8000,
) -> List[dict]:
    """OpenAI-style chat messages for the inference-server backend."""
    return [
        {"role": "system", "content": build_system_prompt(chunks, thinking, char_budget)},
        {"role": "user", "content": query},
    ]


def split_thinking(text: str) -> Tuple[str, str]:
    """
    Split a raw model output into ``(reasoning, answer)``.

    Any ``<think>…</think>`` content becomes ``reasoning``; everything outside
    it is the ``answer``. If there's no think block, ``reasoning`` is empty and
    the whole text is the answer. An unterminated ``<think>`` (stream cut off)
    treats the rest as reasoning with an empty answer.
    """
    if "<think>" not in text:
        return "", text.strip()

    reasoning_parts = _THINK_RE.findall(text)
    answer = _THINK_RE.sub("", text)

    # Handle an unterminated <think> (no closing tag yet / truncated output).
    if "<think>" in answer:
        head, _, tail = answer.partition("<think>")
        reasoning_parts.append(tail)
        answer = head

    reasoning = "\n".join(p.strip() for p in reasoning_parts if p.strip())
    return reasoning.strip(), answer.strip()


def _split_safe(buf: str, tag: str):
    """
    Return ``(emit, hold)`` where ``hold`` is the longest suffix of ``buf`` that
    could be the start of ``tag`` (so a tag split across streamed tokens isn't
    emitted mid-match), and ``emit`` is the rest, safe to send now.
    """
    for k in range(min(len(tag) - 1, len(buf)), 0, -1):
        if buf.endswith(tag[:k]):
            return buf[:-k], buf[-k:]
    return buf, ""


class ThinkingStreamSplitter:
    """
    Incrementally routes streamed model tokens into ``("thinking", text)`` and
    ``("answer", text)`` events, stripping the ``<think>``/``</think>`` tags —
    so the UI can render live reasoning and the live answer in separate places.
    Tolerates tags that span multiple tokens.
    """

    def __init__(self):
        self.buf = ""
        self.in_think = False
        self.saw_think = False

    def feed(self, token: str):
        self.buf += token
        events = []
        while self.buf:
            if not self.in_think:
                idx = self.buf.find("<think>")
                if idx == -1:
                    emit, hold = _split_safe(self.buf, "<think>")
                    if emit:
                        events.append(("answer", emit))
                    self.buf = hold
                    break
                if idx > 0:
                    events.append(("answer", self.buf[:idx]))
                self.buf = self.buf[idx + len("<think>"):]
                self.in_think = True
                self.saw_think = True
            else:
                idx = self.buf.find("</think>")
                if idx == -1:
                    emit, hold = _split_safe(self.buf, "</think>")
                    if emit:
                        events.append(("thinking", emit))
                    self.buf = hold
                    break
                if idx > 0:
                    events.append(("thinking", self.buf[:idx]))
                self.buf = self.buf[idx + len("</think>"):]
                self.in_think = False
        return events

    def flush(self):
        """Emit any held-back remainder at end-of-stream."""
        if not self.buf:
            return []
        phase = "thinking" if self.in_think else "answer"
        out = [(phase, self.buf)]
        self.buf = ""
        return out
