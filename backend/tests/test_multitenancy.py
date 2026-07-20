"""
End-to-end cross-user isolation test exercising the full ingestion pipeline
stack together (parse -> chunk -> embed -> store -> list -> delete), using
real user rows created via auth.store (test_user / second_test_user
fixtures) instead of hardcoded user-id strings.

Complements the narrower, single-module isolation tests already in
test_pipeline.py / test_hybrid_search.py / test_semantic_cache.py /
test_vector_index.py by proving the isolation holds when everything runs
together through DocumentIngestionPipeline.process_document, not just at
each layer in isolation.
"""

import pytest

from ingestion.pipeline import DocumentIngestionPipeline
from tests.conftest import REDIS_HOST, REDIS_PORT


@pytest.fixture
def pipeline(redis_client, no_vector_index):
    return DocumentIngestionPipeline(redis_host=REDIS_HOST, redis_port=REDIS_PORT, redis_db=0)


class TestFullPipelineIsolationBetweenTwoUsers:
    def test_full_pipeline_isolation_between_two_users(
        self, pipeline, redis_client, tmp_path, test_user, second_test_user
    ):
        file_a = tmp_path / "alice_notes.txt"
        file_a.write_text("Alice's private research notes about quarterly revenue.", encoding="utf-8")
        file_b = tmp_path / "bob_notes.txt"
        file_b.write_text("Bob's private research notes about hiring plans.", encoding="utf-8")

        result_a = pipeline.process_document(str(file_a), test_user, category="General")
        result_b = pipeline.process_document(str(file_b), second_test_user, category="General")

        assert result_a["status"] == "success"
        assert result_b["status"] == "success"

        docs_a = pipeline.list_documents(test_user)
        docs_b = pipeline.list_documents(second_test_user)

        assert [d["file_name"] for d in docs_a] == ["alice_notes.txt"]
        assert [d["file_name"] for d in docs_b] == ["bob_notes.txt"]

        # Deleting user A's document must not affect user B's document.
        freed = pipeline.delete_document("alice_notes.txt", "General", test_user)
        assert freed is not None

        assert pipeline.list_documents(test_user) == []
        assert [d["file_name"] for d in pipeline.list_documents(second_test_user)] == ["bob_notes.txt"]

    def test_process_document_deletes_original_upload_file(self, pipeline, tmp_path, test_user):
        file_a = tmp_path / "temp_upload.txt"
        file_a.write_text("some content to embed", encoding="utf-8")

        pipeline.process_document(str(file_a), test_user, category="General")

        assert not file_a.exists()
