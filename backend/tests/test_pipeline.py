"""Tests for ingestion.pipeline.DocumentIngestionPipeline."""

import json
from pathlib import Path

import pytest

from ingestion.pipeline import DocumentIngestionPipeline
from tests.conftest import REDIS_HOST, REDIS_PORT


@pytest.fixture
def pipeline(redis_client, no_vector_index):
    return DocumentIngestionPipeline(redis_host=REDIS_HOST, redis_port=REDIS_PORT, redis_db=0)


class TestChunking:
    def test_chunk_text_splits_on_sentence_boundaries(self, pipeline):
        # _chunk_text splits on [.!?]+ and rejoins with a single space,
        # so sentence-terminating punctuation is not preserved.
        text = "First sentence here. Second sentence follows! Third one too?"
        chunks = pipeline._chunk_text(text, chunk_size=1000, chunk_overlap=0)
        assert chunks == ["First sentence here Second sentence follows Third one too"]

    def test_chunk_text_respects_chunk_size(self, pipeline):
        text = ". ".join(f"Sentence number {i}" for i in range(20))
        chunks = pipeline._chunk_text(text, chunk_size=50, chunk_overlap=0)
        assert len(chunks) > 1
        for chunk in chunks:
            # A little slack: overlap/whitespace joining can push slightly past chunk_size.
            assert len(chunk) <= 70

    def test_chunk_text_empty_input(self, pipeline):
        assert pipeline._chunk_text("", 512, 50) == []

    def test_chunk_text_zero_chunk_size(self, pipeline):
        assert pipeline._chunk_text("hello world", 0, 0) == []

    def test_chunk_text_zero_overlap_does_not_crash(self, pipeline):
        # Regression test: _get_overlap used to IndexError when
        # chunk_overlap=0 (a legitimate value) and a chunk boundary was hit.
        text = ". ".join(f"Sentence number {i}" for i in range(20))
        chunks = pipeline._chunk_text(text, chunk_size=50, chunk_overlap=0)
        assert len(chunks) > 1


class TestParsers:
    def test_parse_txt(self, pipeline, tmp_path):
        f = tmp_path / "note.txt"
        f.write_text("hello world", encoding="utf-8")
        assert pipeline._parse_txt(str(f)) == "hello world"

    def test_parse_csv(self, pipeline, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
        result = pipeline._parse_csv(str(f))
        assert "a, b, c" in result
        assert "1, 2, 3" in result

    def test_parse_json_file(self, pipeline, tmp_path):
        f = tmp_path / "data.json"
        f.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        result = pipeline._parse_json_file(str(f))
        assert "key" in result and "value" in result

    def test_parse_xml(self, pipeline, tmp_path):
        f = tmp_path / "data.xml"
        f.write_text("<root><item>hello</item><item>world</item></root>", encoding="utf-8")
        result = pipeline._parse_xml(str(f))
        assert "hello" in result and "world" in result

    def test_validate_file_type(self, pipeline):
        assert pipeline.validate_file_type("doc.pdf") is True
        assert pipeline.validate_file_type("doc.exe") is False


class TestStorageRoundTrip:
    USER_A = "user-aaa"
    USER_B = "user-bbb"

    def test_store_list_delete(self, pipeline, redis_client):
        chunks = ["chunk one", "chunk two"]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]

        pipeline._store_in_redis("/tmp/report.pdf", chunks, embeddings, "Finance", self.USER_A)

        docs = pipeline.list_documents(self.USER_A)
        assert len(docs) == 1
        assert docs[0]["file_name"] == "report.pdf"
        assert docs[0]["pool"] == "Finance"
        assert docs[0]["chunk_count"] == 2

        freed = pipeline.delete_document("report.pdf", "Finance", self.USER_A)
        assert freed is not None
        assert pipeline.list_documents(self.USER_A) == []

    def test_delete_nonexistent_document_returns_none(self, pipeline):
        assert pipeline.delete_document("ghost.pdf", "General", self.USER_A) is None

    def test_list_documents_scoped_to_user(self, pipeline, redis_client):
        pipeline._store_in_redis("/tmp/mine.pdf", ["a"], [[0.1, 0.2]], "General", self.USER_A)
        pipeline._store_in_redis("/tmp/theirs.pdf", ["b"], [[0.3, 0.4]], "General", self.USER_B)

        a_docs = pipeline.list_documents(self.USER_A)
        b_docs = pipeline.list_documents(self.USER_B)

        assert [d["file_name"] for d in a_docs] == ["mine.pdf"]
        assert [d["file_name"] for d in b_docs] == ["theirs.pdf"]

    def test_delete_only_affects_owning_user(self, pipeline, redis_client):
        pipeline._store_in_redis("/tmp/mine.pdf", ["a"], [[0.1, 0.2]], "General", self.USER_A)
        pipeline._store_in_redis("/tmp/theirs.pdf", ["b"], [[0.3, 0.4]], "General", self.USER_B)

        pipeline.delete_document("mine.pdf", "General", self.USER_A)

        assert pipeline.list_documents(self.USER_A) == []
        assert [d["file_name"] for d in pipeline.list_documents(self.USER_B)] == ["theirs.pdf"]

    def test_reindex_from_disk_restores_document(self, pipeline, tmp_path):
        pool_dir = tmp_path / self.USER_A / "General"
        pool_dir.mkdir(parents=True)
        backup = {
            "file_name": "notes.txt",
            "pool": "General",
            "pool_assigned": True,
            "user_id": self.USER_A,
            "chunks": ["a chunk of text"],
            "embeddings": [[0.1] * 384],
            "chunk_count": 1,
            "processed_at": "2026-01-01T00:00:00",
        }
        (pool_dir / "notes.json").write_text(json.dumps(backup), encoding="utf-8")

        count = pipeline.reindex_from_disk(str(tmp_path))

        assert count == 1
        docs = pipeline.list_documents(self.USER_A)
        assert len(docs) == 1
        assert docs[0]["file_name"] == "notes.txt"

    def test_reindex_from_disk_missing_dir_returns_zero(self, pipeline, tmp_path):
        missing = tmp_path / "does-not-exist"
        assert pipeline.reindex_from_disk(str(missing)) == 0

    def test_document_still_at_true_when_present(self, pipeline, redis_client):
        pipeline._store_in_redis("/tmp/report.pdf", ["chunk"], [[0.1, 0.2]], "Finance", self.USER_A)
        assert pipeline.document_still_at(self.USER_A, "Finance", "report.pdf") is True

    def test_document_still_at_false_after_move_or_delete(self, pipeline, redis_client):
        pipeline._store_in_redis("/tmp/report.pdf", ["chunk"], [[0.1, 0.2]], "Finance", self.USER_A)
        pipeline.delete_document("report.pdf", "Finance", self.USER_A)
        assert pipeline.document_still_at(self.USER_A, "Finance", "report.pdf") is False

    def test_document_still_at_false_for_wrong_pool(self, pipeline, redis_client):
        pipeline._store_in_redis("/tmp/report.pdf", ["chunk"], [[0.1, 0.2]], "Finance", self.USER_A)
        assert pipeline.document_still_at(self.USER_A, "General", "report.pdf") is False

    def test_new_document_has_blank_summary(self, pipeline, redis_client):
        # summary is only populated later, by update_document_summary — a
        # freshly-stored document must not error/omit the key (task.md §1d).
        pipeline._store_in_redis("/tmp/report.pdf", ["chunk"], [[0.1, 0.2]], "Finance", self.USER_A)
        docs = pipeline.list_documents(self.USER_A)
        assert docs[0]["summary"] == ""


class TestUpdateDocumentSummary:
    USER_A = "user-summary"

    def test_updates_redis_blob(self, pipeline, redis_client):
        pipeline._store_in_redis("/tmp/report.pdf", ["chunk"], [[0.1, 0.2]], "Finance", self.USER_A)

        ok = pipeline.update_document_summary(self.USER_A, "Finance", "report.pdf", "A concise summary.")

        assert ok is True
        docs = pipeline.list_documents(self.USER_A)
        assert docs[0]["summary"] == "A concise summary."

    def test_updates_json_backup_on_disk(self, pipeline, redis_client, tmp_path, monkeypatch):
        from utils.config import config
        monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
        pipeline._save_json_backup("/tmp/report.pdf", ["chunk"], [[0.1, 0.2]], "Finance", self.USER_A)
        pipeline._store_in_redis("/tmp/report.pdf", ["chunk"], [[0.1, 0.2]], "Finance", self.USER_A)

        pipeline.update_document_summary(self.USER_A, "Finance", "report.pdf", "Backup should have this too.")

        backup_path = tmp_path / self.USER_A / "Finance" / "report.json"
        saved = json.loads(backup_path.read_text(encoding="utf-8"))
        assert saved["summary"] == "Backup should have this too."

    def test_missing_document_returns_false(self, pipeline, redis_client):
        ok = pipeline.update_document_summary(self.USER_A, "Finance", "ghost.pdf", "irrelevant")
        assert ok is False

    def test_does_not_touch_other_documents(self, pipeline, redis_client):
        pipeline._store_in_redis("/tmp/a.pdf", ["chunk"], [[0.1, 0.2]], "General", self.USER_A)
        pipeline._store_in_redis("/tmp/b.pdf", ["chunk"], [[0.3, 0.4]], "General", self.USER_A)

        pipeline.update_document_summary(self.USER_A, "General", "a.pdf", "summary for a")

        docs = {d["file_name"]: d["summary"] for d in pipeline.list_documents(self.USER_A)}
        assert docs["a.pdf"] == "summary for a"
        assert docs["b.pdf"] == ""
