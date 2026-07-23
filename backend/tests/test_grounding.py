"""Unit tests for generation.grounding — pure logic, no Redis or model."""

import pytest

from generation import grounding


class TestGreetingDetection:
    @pytest.mark.parametrize("msg", [
        "hi", "Hi!", "hello", "hey", "heyy", "yo",
        "good morning", "Good Evening.", "greetings",
        "thanks", "thank you", "thx", "ty", "cheers",
        "bye", "goodbye", "see you",
        "how are you", "how's it going", "what's up", "sup",
        "who are you?", "what can you do", "help",
    ])
    def test_greetings_detected(self, msg):
        assert grounding.is_greeting(msg) is True

    @pytest.mark.parametrize("msg", [
        "hi, what does the report say?",
        "what is the refund policy?",
        "summarize document 2",
        "hello world program in python",  # not a bare greeting
        "",
    ])
    def test_non_greetings_not_detected(self, msg):
        assert grounding.is_greeting(msg) is False

    def test_thanks_response(self):
        assert "welcome" in grounding.greeting_response("thanks").lower()

    def test_capability_response_mentions_documents(self):
        r = grounding.greeting_response("who are you?").lower()
        assert "document" in r or "knowledge pool" in r

    def test_default_greeting_is_friendly(self):
        assert "vaultly" in grounding.greeting_response("hi").lower()


class TestRefusalMessages:
    def test_no_results_and_out_of_scope_are_distinct(self):
        assert grounding.NO_RESULTS_MESSAGE != grounding.OUT_OF_SCOPE_MESSAGE

    def test_refusal_message_is_out_of_scope_alias(self):
        assert grounding.REFUSAL_MESSAGE == grounding.OUT_OF_SCOPE_MESSAGE


class TestRelevanceGate:
    def test_empty_results_fail(self):
        assert grounding.passes_relevance_gate([], threshold=0.0) is False

    def test_all_below_threshold_fail(self):
        results = [{"score": 0.1}, {"score": 0.2}]
        assert grounding.passes_relevance_gate(results, threshold=0.5) is False

    def test_one_above_threshold_passes(self):
        results = [{"score": 0.1}, {"score": 0.9}]
        assert grounding.passes_relevance_gate(results, threshold=0.5) is True

    def test_works_with_objects(self):
        class R:
            def __init__(self, s): self.score = s
        assert grounding.passes_relevance_gate([R(0.9)], threshold=0.5) is True

    def test_threshold_is_inclusive(self):
        assert grounding.passes_relevance_gate([{"score": 0.5}], threshold=0.5) is True


class TestPromptBuilder:
    def test_prompt_contains_all_chunks_and_query(self):
        p = grounding.build_grounded_prompt("what is X?", ["alpha chunk", "beta chunk"])
        assert "alpha chunk" in p
        assert "beta chunk" in p
        assert "what is X?" in p
        assert "[1]" in p and "[2]" in p

    def test_prompt_includes_refusal_instruction(self):
        p = grounding.build_grounded_prompt("q", ["c"])
        assert grounding.REFUSAL_MESSAGE in p

    def test_thinking_flag_adds_reasoning_instruction(self):
        assert "<think>" in grounding.build_grounded_prompt("q", ["c"], thinking=True)
        assert "<think>" not in grounding.build_grounded_prompt("q", ["c"], thinking=False)

    def test_oversized_chunks_truncated_to_budget(self):
        big = "x" * 5000
        p = grounding.build_grounded_prompt("q", [big, big, big], char_budget=6000)
        # Total context can't blow far past the budget (+ prompt scaffolding).
        assert len(p) < 6000 + 2000
        assert "…" in p  # truncation marker present

    def test_empty_chunks_still_builds(self):
        p = grounding.build_grounded_prompt("q", [])
        assert "(no passages)" in p

    def test_messages_builder_shape(self):
        msgs = grounding.build_grounded_messages("what is X?", ["alpha", "beta"])
        assert [m["role"] for m in msgs] == ["system", "user"]
        assert "alpha" in msgs[0]["content"] and "beta" in msgs[0]["content"]
        assert grounding.REFUSAL_MESSAGE in msgs[0]["content"]
        assert msgs[1]["content"] == "what is X?"

    def test_system_prompt_shared_by_both_builders(self):
        sys_only = grounding.build_system_prompt(["chunk"])
        assert sys_only in grounding.build_grounded_prompt("q", ["chunk"])
        assert grounding.build_grounded_messages("q", ["chunk"])[0]["content"] == sys_only

    def test_prompt_includes_history_between_system_and_current_turn(self):
        history = [{"role": "user", "content": "earlier question"}, {"role": "assistant", "content": "earlier answer"}]
        p = grounding.build_grounded_prompt("follow-up", ["chunk"], history=history)
        assert p.index("earlier question") < p.index("follow-up")
        assert "earlier answer" in p

    def test_messages_include_history_between_system_and_current_turn(self):
        history = [{"role": "user", "content": "earlier question"}, {"role": "assistant", "content": "earlier answer"}]
        msgs = grounding.build_grounded_messages("follow-up", ["chunk"], history=history)
        assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
        assert msgs[1]["content"] == "earlier question"
        assert msgs[2]["content"] == "earlier answer"
        assert msgs[3]["content"] == "follow-up"

    def test_no_history_is_a_no_op(self):
        assert grounding.build_grounded_prompt("q", ["c"]) == grounding.build_grounded_prompt("q", ["c"], history=None)
        assert grounding.build_grounded_messages("q", ["c"], history=None) == grounding.build_grounded_messages("q", ["c"])


class TestThinkingDirective:
    def test_thinking_true_appends_think(self):
        assert grounding.thinking_directive(True) == " /think"

    def test_thinking_false_appends_no_think(self):
        assert grounding.thinking_directive(False) == " /no_think"

    def test_directive_is_a_suffix_not_a_replacement(self):
        query = "what is X?"
        assert (query + grounding.thinking_directive(True)).startswith(query)
        assert (query + grounding.thinking_directive(False)).startswith(query)


class TestChatMessagesAndFormatting:
    def test_chat_messages_no_history(self):
        msgs = grounding.chat_messages("sys", "usr")
        assert msgs == [{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}]

    def test_chat_messages_with_history(self):
        history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        msgs = grounding.chat_messages("sys", "usr", history)
        assert msgs == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "usr"},
        ]

    def test_format_chat_prompt_with_history_order(self):
        history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        p = grounding.format_chat_prompt("sys", "usr", history)
        assert p.index("sys") < p.index("\na<") < p.index("\nb<") < p.index("\nusr<")
        assert p.endswith("<|im_start|>assistant\n")


class TestTrimHistory:
    def test_empty_history(self):
        assert grounding.trim_history([]) == []
        assert grounding.trim_history(None) == []

    def test_keeps_last_n_turns(self):
        history = [{"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(10)]
        trimmed = grounding.trim_history(history, max_turns=2)
        assert len(trimmed) == 4
        assert [m["content"] for m in trimmed] == ["6", "7", "8", "9"]

    def test_truncates_long_messages(self):
        history = [{"role": "user", "content": "x" * 1000}]
        trimmed = grounding.trim_history(history, max_chars_per_message=100)
        assert len(trimmed[0]["content"]) <= 102
        assert trimmed[0]["content"].endswith("…")

    def test_short_messages_untouched(self):
        history = [{"role": "user", "content": "short"}]
        assert grounding.trim_history(history) == [{"role": "user", "content": "short"}]

    def test_missing_role_defaults_to_user(self):
        trimmed = grounding.trim_history([{"content": "no role given"}])
        assert trimmed[0]["role"] == "user"


class TestSplitThinking:
    def test_no_think_block_returns_whole_answer(self):
        reasoning, answer = grounding.split_thinking("Just the answer.")
        assert reasoning == ""
        assert answer == "Just the answer."

    def test_extracts_think_block(self):
        reasoning, answer = grounding.split_thinking("<think>reasoning here</think>Final answer.")
        assert reasoning == "reasoning here"
        assert answer == "Final answer."

    def test_unterminated_think_is_all_reasoning(self):
        reasoning, answer = grounding.split_thinking("<think>still thinking")
        assert reasoning == "still thinking"
        assert answer == ""

    def test_multiline_think(self):
        reasoning, answer = grounding.split_thinking("<think>line1\nline2</think>\nAnswer")
        assert "line1" in reasoning and "line2" in reasoning
        assert answer == "Answer"


class TestThinkingStreamSplitter:
    def _collect(self, tokens):
        s = grounding.ThinkingStreamSplitter()
        out = []
        for t in tokens:
            out.extend(s.feed(t))
        out.extend(s.flush())
        thinking = "".join(text for phase, text in out if phase == "thinking")
        answer = "".join(text for phase, text in out if phase == "answer")
        return thinking, answer

    def test_plain_answer_all_answer(self):
        thinking, answer = self._collect(["Hello ", "world", "."])
        assert thinking == ""
        assert answer == "Hello world."

    def test_think_then_answer(self):
        thinking, answer = self._collect(["<think>reason</think>", "The answer."])
        assert thinking == "reason"
        assert answer == "The answer."

    def test_tag_split_across_tokens(self):
        # '<think>' and '</think>' arrive broken across token boundaries.
        thinking, answer = self._collect(["<th", "ink>rea", "son</thi", "nk>Ans", "wer"])
        assert thinking == "reason"
        assert answer == "Answer"

    def test_unterminated_think_flushed_as_thinking(self):
        thinking, answer = self._collect(["<think>still going"])
        assert thinking == "still going"
        assert answer == ""
