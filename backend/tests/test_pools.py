"""
Tests for knowledge-pool behavior at the pipeline level: upload flag,
move/assign between pools, and cross-pool isolation.

Driven through DocumentIngestionPipeline directly (with no_vector_index)
rather than the HTTP app, matching test_multitenancy.py's pattern — the
full app needs redis-stack to construct, which isn't available here.
"""

import pytest

from ingestion.pipeline import DocumentIngestionPipeline
from tests.conftest import REDIS_HOST, REDIS_PORT


@pytest.fixture(autouse=True)
def _isolated_data_dir(monkeypatch, tmp_path):
    from utils.config import config

    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def pipeline(redis_client, no_vector_index):
    return DocumentIngestionPipeline(redis_host=REDIS_HOST, redis_port=REDIS_PORT, redis_db=0)


def _ingest(pipeline, tmp_path, user, name, pool, pool_assigned=True):
    f = tmp_path / name
    f.write_text(f"content of {name}", encoding="utf-8")
    return pipeline.process_document(str(f), user, pool=pool, pool_assigned=pool_assigned)


class TestPoolAssignedFlag:
    def test_explicit_pool_is_assigned(self, pipeline, tmp_path):
        result = _ingest(pipeline, tmp_path, "u1", "a.txt", "Finance", pool_assigned=True)
        assert result["pool"] == "Finance"
        assert result["pool_assigned"] is True
        assert pipeline.list_documents("u1")[0]["pool_assigned"] is True

    def test_unassigned_upload_is_flagged(self, pipeline, tmp_path):
        # Mirrors the API path: no pool chosen → lands in General, flagged.
        result = _ingest(pipeline, tmp_path, "u1", "b.txt", "General", pool_assigned=False)
        assert result["pool"] == "General"
        assert result["pool_assigned"] is False
        doc = pipeline.list_documents("u1")[0]
        assert doc["pool"] == "General"
        assert doc["pool_assigned"] is False


class TestMoveDocument:
    def test_move_to_another_pool(self, pipeline, tmp_path):
        _ingest(pipeline, tmp_path, "u1", "doc.txt", "General", pool_assigned=False)

        meta = pipeline.move_document("u1", "doc.txt", "General", "Research")
        assert meta is not None
        assert meta["pool"] == "Research"
        assert meta["pool_assigned"] is True

        docs = pipeline.list_documents("u1")
        assert len(docs) == 1
        assert docs[0]["pool"] == "Research"
        # Old pool key is gone, new one present.
        assert pipeline.redis_client.exists("document:u1:General:doc.txt") == 0
        assert pipeline.redis_client.exists("document:u1:Research:doc.txt") == 1

    def test_assign_in_place_same_pool_flips_flag(self, pipeline, tmp_path):
        _ingest(pipeline, tmp_path, "u1", "doc.txt", "General", pool_assigned=False)
        meta = pipeline.move_document("u1", "doc.txt", "General", "General")
        assert meta["pool"] == "General"
        assert meta["pool_assigned"] is True
        assert pipeline.list_documents("u1")[0]["pool_assigned"] is True

    def test_move_missing_document_returns_none(self, pipeline):
        assert pipeline.move_document("u1", "ghost.txt", "General", "Research") is None

    def test_move_does_not_touch_other_users(self, pipeline, tmp_path):
        _ingest(pipeline, tmp_path, "u1", "mine.txt", "General")
        _ingest(pipeline, tmp_path, "u2", "theirs.txt", "General")

        pipeline.move_document("u1", "mine.txt", "General", "Research")

        # u2's document is untouched.
        u2 = pipeline.list_documents("u2")
        assert [d["file_name"] for d in u2] == ["theirs.txt"]
        assert u2[0]["pool"] == "General"


class TestPoolIsolation:
    def test_documents_grouped_by_pool(self, pipeline, tmp_path):
        _ingest(pipeline, tmp_path, "u1", "a.txt", "Finance")
        _ingest(pipeline, tmp_path, "u1", "b.txt", "Research")

        by_pool = {}
        for d in pipeline.list_documents("u1"):
            by_pool.setdefault(d["pool"], []).append(d["file_name"])
        assert by_pool == {"Finance": ["a.txt"], "Research": ["b.txt"]}
