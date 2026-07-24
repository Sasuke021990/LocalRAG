"""Tests for the knowledge-graph store + extraction parsing (task.md §1a)."""

import pytest

from knowledge_graph import store
from generation import pipeline


class TestMergeAndGet:
    UID = "kg-user"
    POOL = "General"

    def test_merge_creates_nodes_and_edges(self, redis_client):
        store.merge_document(
            redis_client, self.UID, self.POOL, "policy.txt",
            nodes=["Refund Policy", "Digital Goods"],
            edges=[("Refund Policy", "Digital Goods", "excludes")],
        )
        graph = store.get_pool_graph(redis_client, self.UID, self.POOL)
        labels = {n["label"] for n in graph["nodes"]}
        assert {"Refund Policy", "Digital Goods"} <= labels
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["label"] == "excludes"

    def test_same_concept_across_documents_dedups_to_one_node(self, redis_client):
        store.merge_document(redis_client, self.UID, self.POOL, "a.txt", ["Refund Policy"], [])
        store.merge_document(redis_client, self.UID, self.POOL, "b.txt", ["refund policy"], [])
        graph = store.get_pool_graph(redis_client, self.UID, self.POOL)
        refund = [n for n in graph["nodes"] if n["id"] == "refund-policy"]
        assert len(refund) == 1
        # Backed by both documents now.
        assert refund[0]["source_count"] == 2

    def test_edge_endpoints_are_upserted_even_if_not_in_nodes(self, redis_client):
        # Only edges given, no standalone node labels — endpoints must still exist.
        store.merge_document(
            redis_client, self.UID, self.POOL, "a.txt",
            nodes=[], edges=[("Alpha", "Beta", "links")],
        )
        graph = store.get_pool_graph(redis_client, self.UID, self.POOL)
        assert {n["id"] for n in graph["nodes"]} == {"alpha", "beta"}
        assert len(graph["edges"]) == 1

    def test_self_loop_edge_skipped(self, redis_client):
        store.merge_document(
            redis_client, self.UID, self.POOL, "a.txt",
            nodes=[], edges=[("Same Thing", "same thing", "is")],
        )
        graph = store.get_pool_graph(redis_client, self.UID, self.POOL)
        assert graph["edges"] == []

    def test_overlong_label_rejected(self, redis_client):
        long_label = "x" * (store.MAX_LABEL_LEN + 1)
        store.merge_document(redis_client, self.UID, self.POOL, "a.txt", [long_label, "Ok"], [])
        graph = store.get_pool_graph(redis_client, self.UID, self.POOL)
        assert [n["label"] for n in graph["nodes"]] == ["Ok"]

    def test_empty_pool_graph(self, redis_client):
        graph = store.get_pool_graph(redis_client, self.UID, "EmptyPool")
        assert graph == {"nodes": [], "edges": []}


class TestRemoveDocument:
    UID = "kg-del-user"
    POOL = "General"

    def test_sole_source_node_deleted(self, redis_client):
        store.merge_document(redis_client, self.UID, self.POOL, "only.txt", ["Solo Concept"], [])
        store.remove_document(redis_client, self.UID, self.POOL, "only.txt")
        graph = store.get_pool_graph(redis_client, self.UID, self.POOL)
        assert graph["nodes"] == []

    def test_shared_node_kept_but_source_dropped(self, redis_client):
        store.merge_document(redis_client, self.UID, self.POOL, "a.txt", ["Shared"], [])
        store.merge_document(redis_client, self.UID, self.POOL, "b.txt", ["Shared"], [])
        store.remove_document(redis_client, self.UID, self.POOL, "a.txt")
        graph = store.get_pool_graph(redis_client, self.UID, self.POOL)
        shared = [n for n in graph["nodes"] if n["id"] == "shared"]
        assert len(shared) == 1
        assert shared[0]["source_count"] == 1

    def test_edge_removed_with_its_only_document(self, redis_client):
        store.merge_document(
            redis_client, self.UID, self.POOL, "a.txt",
            nodes=[], edges=[("X", "Y", "relates")],
        )
        store.remove_document(redis_client, self.UID, self.POOL, "a.txt")
        graph = store.get_pool_graph(redis_client, self.UID, self.POOL)
        assert graph["nodes"] == []
        assert graph["edges"] == []

    def test_no_dangling_edge_after_partial_delete(self, redis_client):
        # doc A: an X—Y edge; doc B: only mentions X. Deleting A must remove the
        # edge (its only source) and node Y (its only source), leaving X (kept
        # by B) with no dangling edge.
        store.merge_document(redis_client, self.UID, self.POOL, "a.txt", [], [("X", "Y", "rel")])
        store.merge_document(redis_client, self.UID, self.POOL, "b.txt", ["X"], [])
        store.remove_document(redis_client, self.UID, self.POOL, "a.txt")
        graph = store.get_pool_graph(redis_client, self.UID, self.POOL)
        assert {n["id"] for n in graph["nodes"]} == {"x"}
        assert graph["edges"] == []

    def test_remove_unknown_document_is_noop(self, redis_client):
        store.merge_document(redis_client, self.UID, self.POOL, "a.txt", ["Keep"], [])
        store.remove_document(redis_client, self.UID, self.POOL, "never-existed.txt")
        graph = store.get_pool_graph(redis_client, self.UID, self.POOL)
        assert [n["id"] for n in graph["nodes"]] == ["keep"]


class TestParseGraphJson:
    def test_plain_json(self):
        nodes, edges = pipeline._parse_graph_json('{"nodes": ["A", "B"], "edges": [["A", "B", "rel"]]}')
        assert nodes == ["A", "B"]
        assert edges == [("A", "B", "rel")]

    def test_markdown_fenced_json(self):
        raw = '```json\n{"nodes": ["A"], "edges": []}\n```'
        nodes, edges = pipeline._parse_graph_json(raw)
        assert nodes == ["A"]
        assert edges == []

    def test_prose_around_json(self):
        raw = 'Here is the graph:\n{"nodes": ["A"], "edges": []}\nHope that helps!'
        nodes, _ = pipeline._parse_graph_json(raw)
        assert nodes == ["A"]

    def test_edge_without_label_defaults(self):
        nodes, edges = pipeline._parse_graph_json('{"nodes": [], "edges": [["A", "B"]]}')
        assert edges == [("A", "B", "related to")]

    def test_malformed_returns_empty(self):
        assert pipeline._parse_graph_json("not json at all") == ([], [])
        assert pipeline._parse_graph_json("") == ([], [])
        assert pipeline._parse_graph_json('{"nodes": [1,2') == ([], [])

    def test_drops_malformed_edge_entries(self):
        nodes, edges = pipeline._parse_graph_json('{"nodes": [], "edges": [["A"], ["A", "B", "ok"], "x"]}')
        assert edges == [("A", "B", "ok")]


class _FakeLLM:
    def __init__(self, output="", ready=True):
        self.output = output
        self._ready = ready
        self.called = False

    @property
    def ready(self):
        return self._ready

    async def generate_stream(self, system, user, history=None):
        self.called = True
        for tok in self.output:
            yield tok


@pytest.mark.anyio
class TestExtractGraphElements:
    async def test_parses_llm_json(self):
        llm = _FakeLLM('{"nodes": ["A", "B"], "edges": [["A", "B", "rel"]]}')
        nodes, edges = await pipeline.extract_graph_elements(["some content"], llm)
        assert nodes == ["A", "B"]
        assert edges == [("A", "B", "rel")]

    async def test_empty_chunks_returns_empty_without_calling_llm(self):
        llm = _FakeLLM("should not run")
        assert await pipeline.extract_graph_elements([], llm) == ([], [])
        assert llm.called is False

    async def test_llm_not_ready_returns_empty(self):
        llm = _FakeLLM("x", ready=False)
        assert await pipeline.extract_graph_elements(["content"], llm) == ([], [])
        assert llm.called is False


@pytest.fixture
def anyio_backend():
    return "asyncio"
