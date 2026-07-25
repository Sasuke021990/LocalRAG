"""
Regression tests for the conversation-history/pool isolation bug: a client
can resend an existing ``conversation_id`` after switching the active pool
via the pool picker without starting a new chat (mobile's ``choosePool()``
doesn't reset ``activeConversationId``/``history`` — see
``mobile/src/stores/chatStore.ts``). Before the fix, ``_history_from``
threaded every prior turn into the prompt regardless of which pool they
belonged to, so a question asked while scoped to pool "General" could read
as if it were about a completely different pool's documents, because the
model was still seeing chat history about that other pool.

Imports ``main`` directly, which pulls in the full generation/retrieval
stack (embedding model, cross-encoder, LLM client) -- slower than the
lighter-weight route tests in this suite, but ``_history_from`` is plain,
dependency-free logic and this is the only place it's defined.
"""

from main import _history_from


def _conv(pool: str = "", messages=None):
    return {"pool": pool, "messages": messages or []}


HISTORY = [
    {"role": "user", "content": "remember BANANA123"},
    {"role": "assistant", "content": "ok, BANANA123 noted"},
]


class TestHistoryPoolScoping:
    def test_returns_full_history_when_pool_matches(self):
        assert _history_from(_conv("General", HISTORY), "General") == HISTORY

    def test_returns_empty_history_when_pool_differs(self):
        # The exact bug: same conversation_id, different pool than last used.
        assert _history_from(_conv("Car", HISTORY), "General") == []

    def test_none_and_blank_pool_are_equivalent(self):
        # A brand-new conversation (conv["pool"] == "") queried with pool=None
        # (the "All pools" / unscoped case) must not be treated as a mismatch.
        assert _history_from(_conv("", HISTORY), None) == HISTORY
        assert _history_from(_conv(None, HISTORY), "") == HISTORY  # defensive: conv.get("pool") missing entirely too

    def test_missing_pool_key_treated_as_blank(self):
        conv = {"messages": HISTORY}  # no "pool" key at all
        assert _history_from(conv, None) == HISTORY

    def test_empty_conversation_returns_empty_regardless(self):
        assert _history_from(_conv("General", []), "General") == []
