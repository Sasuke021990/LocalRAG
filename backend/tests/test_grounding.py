"""Unit tests for generation.grounding — pure logic, no Redis or model."""

from generation import grounding


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
