"""
Main FastAPI application — LocalRAG v2.0
=========================================
Endpoints:
  GET  /                            — health / version
  GET  /health                      — health check
  GET  /pools                       — list knowledge pools (+ doc counts)
  POST /pools                       — create a new pool
  DELETE /pools/{name}              — delete an empty pool
  GET  /documents                   — list all indexed documents
  DELETE /documents/{file_name}     — delete a document
  PATCH  /documents/{file_name}/pool — move/assign a document to a pool
  POST /upload                      — upload & ingest a document into a pool
  POST /query                       — hybrid search + rerank + cache
  GET  /progress/{task_id}          — SSE progress stream
  GET  /docs                        — Swagger UI (auto-generated)
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from admin import routes as admin_routes
from auth import routes as auth_routes
from auth.dependencies import require_current_user
from auth.redis_client import redis_client as auth_redis_client
from integrations import routes as integrations_routes
from integrations import webhooks
from generation import pipeline as answer_pipeline
from generation.llm import llm as local_llm
from ingestion.pipeline import DocumentIngestionPipeline
from retrieval.hybrid_search import HybridSearchEngine
from retrieval.reranker import CrossEncoderReranker
from retrieval.semantic_cache import SemanticCache
from utils import quota
from utils.config import config

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
DATA_DIR = Path(config.DATA_DIR)
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".csv", ".md", ".html", ".htm", ".json", ".xml"}

# ─── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="LocalRAG API",
    description=(
        "A fully local RAG system with hybrid BM25 + vector search, "
        "cross-encoder re-ranking, semantic caching, and pool-aware "
        "document management.\n\n"
        "All processed data is stored in Redis (fast retrieval) **and** as "
        "portable JSON backups under `<DATA_DIR>/<user_id>/<pool>/` (durability)."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router, prefix="/auth", tags=["Auth"])
app.include_router(integrations_routes.router, prefix="/integrations", tags=["Integrations"])
app.include_router(admin_routes.router, prefix="/admin", tags=["Admin"])


# ─── Component initialisation ─────────────────────────────────────────────────
try:
    ingestion_pipeline = DocumentIngestionPipeline(
        redis_host=config.REDIS_HOST,
        redis_port=config.REDIS_PORT,
        redis_db=config.REDIS_DB,
        embedding_model=config.EMBEDDING_MODEL_NAME,
    )
    hybrid_search = HybridSearchEngine(
        redis_host=config.REDIS_HOST,
        redis_port=config.REDIS_PORT,
        redis_db=config.REDIS_DB,
        embedding_model=config.EMBEDDING_MODEL_NAME,
    )
    reranker      = CrossEncoderReranker(model_name=config.CROSS_ENCODER_MODEL_NAME)
    semantic_cache = SemanticCache(
        redis_host=config.REDIS_HOST,
        redis_port=config.REDIS_PORT,
        redis_db=config.REDIS_DB,
        similarity_threshold=config.SEMANTIC_CACHE_SIMILARITY_THRESHOLD,
    )
    logger.info("All components initialised successfully")
except Exception as exc:
    logger.error(f"Failed to initialise components: {exc}")
    raise

# ─── Startup event ────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_reindex():
    """
    On every container start: create the data directory if needed, then
    scan all JSON backup files and restore any missing Redis entries.
    This guarantees the knowledge base survives container restarts.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    count = ingestion_pipeline.reindex_from_disk(str(DATA_DIR))
    logger.info(f"Startup complete — {count} document(s) re-indexed from disk")

    # Load the local LLM in the background (may download ~1GB on first run) so
    # it never blocks /health. When disabled/unavailable, /query degrades to
    # returning ranked passages.
    if local_llm.enabled:
        asyncio.create_task(asyncio.to_thread(local_llm.ensure_loaded))


# ─── Pydantic models ──────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str
    top_k: int = 10
    rerank_top_k: int = 5

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    processing_time: float
    reasoning: str = ""
    refused: bool = False

class PoolCreate(BaseModel):
    name: str


class PoolMove(BaseModel):
    current_pool: str = "General"
    new_pool: str


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ─── Root / health ────────────────────────────────────────────────────────────

@app.get("/", tags=["System"])
async def root():
    """Root endpoint — confirms the API is running."""
    return {"message": "LocalRAG API v2.0 is running", "version": "2.0.0"}


@app.get("/health", tags=["System"])
async def health_check():
    """Health check used by Docker and monitoring tools."""
    return {"status": "healthy", "version": "2.0.0"}


# ─── Pools ─────────────────────────────────────────────────────────────────────

def _sanitize_pool_name(name: str) -> str:
    """Strip path-traversal characters from a user-supplied pool name."""
    return name.strip().replace("/", "_").replace("\\", "_").replace("..", "_")


def _pool_document_counts(user_id: str) -> Dict[str, int]:
    """Map pool name → number of documents in it (from the Redis blobs)."""
    counts: Dict[str, int] = {}
    for doc in ingestion_pipeline.list_documents(user_id):
        counts[doc["pool"]] = counts.get(doc["pool"], 0) + 1
    return counts


@app.get("/pools", tags=["Pools"], summary="List all knowledge pools")
async def list_pools(user_id: str = Depends(require_current_user)):
    """
    Returns each of this user's knowledge pools with its document count.
    Pools are created automatically when a document is uploaded, or
    explicitly via ``POST /pools``.
    """
    try:
        user_dir = DATA_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        counts = _pool_document_counts(user_id)
        names = sorted(set(d.name for d in user_dir.iterdir() if d.is_dir()) | set(counts))
        pools = [{"name": name, "document_count": counts.get(name, 0)} for name in names]
        return {"pools": pools, "total": len(pools)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/pools", tags=["Pools"], summary="Create a new knowledge pool")
async def create_pool(request: PoolCreate, user_id: str = Depends(require_current_user)):
    """Creates a new (empty) pool folder under ``<DATA_DIR>/<user_id>/<name>/``."""
    try:
        name = _sanitize_pool_name(request.name)
        if not name:
            raise HTTPException(status_code=400, detail="Pool name cannot be empty")
        (DATA_DIR / user_id / name).mkdir(parents=True, exist_ok=True)
        return {"status": "created", "pool": name}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/pools/{name}", tags=["Pools"], summary="Delete an empty pool")
async def delete_pool(name: str, user_id: str = Depends(require_current_user)):
    """
    Deletes a pool. Refuses (409) if the pool still contains documents —
    move or delete them first. The default ``General`` pool cannot be
    deleted.
    """
    try:
        name = _sanitize_pool_name(name)
        if name == "General":
            raise HTTPException(status_code=400, detail="The default 'General' pool cannot be deleted")
        if _pool_document_counts(user_id).get(name, 0) > 0:
            raise HTTPException(status_code=409, detail="Pool is not empty — move or delete its documents first")
        pool_dir = DATA_DIR / user_id / name
        if not pool_dir.exists():
            raise HTTPException(status_code=404, detail="Pool not found")
        pool_dir.rmdir()  # empty-only; rmdir refuses a non-empty dir as a safety net
        return {"status": "deleted", "pool": name}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Documents ────────────────────────────────────────────────────────────────

@app.get("/documents", tags=["Documents"], summary="List all indexed documents")
async def list_documents(user_id: str = Depends(require_current_user)):
    """
    Returns metadata for every document this user has indexed in Redis.
    Includes file name, pool, whether the pool was explicitly chosen
    (``pool_assigned``), chunk count, and processing timestamp.
    """
    try:
        docs = ingestion_pipeline.list_documents(user_id)
        return {"documents": docs, "total": len(docs)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/documents/{file_name}", tags=["Documents"], summary="Delete a document")
async def delete_document(
    file_name: str,
    background_tasks: BackgroundTasks,
    pool: str = "General",
    user_id: str = Depends(require_current_user),
):
    """
    Removes the document from Redis **and** deletes its JSON backup from disk.
    Pass ``?pool=<name>`` to identify the correct document when the same
    file name exists in multiple pools.
    """
    try:
        freed_bytes = ingestion_pipeline.delete_document(file_name, pool, user_id)
        if freed_bytes is None:
            raise HTTPException(status_code=404, detail="Document not found")
        quota.record_deleted_document(ingestion_pipeline.redis_client, user_id, freed_bytes)
        hybrid_search.invalidate_bm25(user_id)
        background_tasks.add_task(
            webhooks.dispatch_event,
            auth_redis_client,
            user_id,
            "document.deleted",
            {"file_name": file_name, "pool": pool},
        )
        return {"status": "deleted", "file_name": file_name, "pool": pool}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.patch("/documents/{file_name}/pool", tags=["Documents"], summary="Move/assign a document to a pool")
async def move_document(
    file_name: str,
    request: PoolMove,
    user_id: str = Depends(require_current_user),
):
    """
    Move a document from ``current_pool`` to ``new_pool`` — also used to
    *assign* a document that was uploaded without an explicit pool (pass
    ``new_pool == current_pool`` to keep it where it is and just clear the
    "needs a pool" flag). Sets ``pool_assigned=true``.
    """
    new_pool = _sanitize_pool_name(request.new_pool)
    if not new_pool:
        raise HTTPException(status_code=400, detail="new_pool cannot be empty")
    meta = ingestion_pipeline.move_document(user_id, file_name, request.current_pool, new_pool)
    if meta is None:
        raise HTTPException(status_code=404, detail="Document not found in the given pool")
    hybrid_search.invalidate_bm25(user_id)
    return {"status": "moved", "document": meta}


# ─── Upload ───────────────────────────────────────────────────────────────────

@app.post("/upload", tags=["Documents"], summary="Upload and ingest a document")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Document file to ingest"),
    chunk_size: int = Form(512, description="Characters per chunk"),
    chunk_overlap: int = Form(50, description="Overlap between chunks"),
    pool: str = Form("", description="Destination knowledge pool (blank = default 'General', flagged for the user to assign)"),
    user_id: str = Depends(require_current_user),
):
    """
    Upload a document for ingestion into a knowledge pool.

    **Flow**:
    1. File is validated and saved to ``<DATA_DIR>/<user_id>/<pool>/<filename>``
    2. Background task: parse → chunk → embed → store → delete original
    3. JSON backup written to ``<DATA_DIR>/<user_id>/<pool>/<stem>.json``
    4. The original uploaded file is deleted after ingestion

    If ``pool`` is blank the document lands in the default ``General`` pool
    but is flagged ``pool_assigned=false`` so the UI can prompt the user to
    keep it there or move it to a chosen pool.

    Supported formats: ``.pdf``, ``.docx``, ``.txt``, ``.csv``, ``.md``,
    ``.html``, ``.json``, ``.xml``
    """
    try:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{file_ext}' is not supported. "
                       f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        # Blank pool → default to 'General' but flag it as not explicitly chosen.
        pool_explicitly_selected = bool(pool.strip())
        safe_pool = _sanitize_pool_name(pool) or "General"

        content = await file.read()

        # Cheap pre-check using the raw upload size as an upper-bound
        # heuristic -- rejects obviously-over-quota uploads immediately,
        # before any file is written or processing is queued. The
        # authoritative check (using the actual post-ingestion stored
        # size) happens in _process() below, since embedding overhead
        # isn't known until after processing.
        quota.check_upload_allowed(ingestion_pipeline.redis_client, user_id, len(content))

        # Ensure directory exists and save file
        pool_dir = DATA_DIR / user_id / safe_pool
        pool_dir.mkdir(parents=True, exist_ok=True)
        file_path = str(pool_dir / file.filename)

        with open(file_path, "wb") as fh:
            fh.write(content)

        # Queue background processing
        # NOTE: Plain `def` (not `async def`) so FastAPI routes this to a
        # threadpool executor — keeping the asyncio event loop free for other
        # requests while the heavy CPU work (parse → chunk → embed) runs.
        def _process():
            try:
                result = ingestion_pipeline.process_document(
                    file_path,
                    user_id=user_id,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    pool=safe_pool,
                    pool_assigned=pool_explicitly_selected,
                )
                logger.info(f"Processed: {file.filename} → {safe_pool} | {result['total_chunks']} chunks")

                quota.record_ingested_document(ingestion_pipeline.redis_client, user_id, result["stored_bytes"])
                if quota.is_over_quota(ingestion_pipeline.redis_client, user_id):
                    freed = ingestion_pipeline.delete_document(file.filename, safe_pool, user_id)
                    if freed is not None:
                        quota.record_deleted_document(ingestion_pipeline.redis_client, user_id, freed)
                    logger.warning(
                        f"Rolled back '{file.filename}' for user {user_id}: quota exceeded after ingestion"
                    )
                    webhooks.dispatch_event(
                        auth_redis_client, user_id, "document.ingest_failed",
                        {"file_name": file.filename, "pool": safe_pool, "reason": "quota_exceeded"},
                    )
                else:
                    # New/changed document set for this user — drop the stale BM25 cache.
                    hybrid_search.invalidate_bm25(user_id)
                    webhooks.dispatch_event(
                        auth_redis_client, user_id, "document.ingested",
                        {"file_name": file.filename, "pool": safe_pool,
                         "pool_assigned": pool_explicitly_selected, "chunk_count": result["total_chunks"]},
                    )
            except Exception as exc:
                logger.error(f"Background processing failed for '{file.filename}': {exc}")
                webhooks.dispatch_event(
                    auth_redis_client, user_id, "document.ingest_failed",
                    {"file_name": file.filename, "pool": safe_pool, "reason": "processing_error"},
                )

        background_tasks.add_task(_process)

        return {
            "status": "processing_started",
            "filename": file.filename,
            "pool": safe_pool,
            "pool_assigned": pool_explicitly_selected,
            "message": f"'{file.filename}' queued for ingestion in pool '{safe_pool}'",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Upload error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Query ────────────────────────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse, tags=["Search"], summary="Hybrid search + re-rank + cache")
async def query_documents(request: QueryRequest, user_id: str = Depends(require_current_user)):
    """
    Query the knowledge base using the full RAG pipeline:

    1. **Semantic cache** — return instantly if a matching query was cached
    2. **Hybrid search** — BM25 (sparse) + vector (dense) via Reciprocal Rank Fusion
    3. **Cross-encoder re-ranking** — re-score top-K with ``ms-marco-MiniLM-L-6-v2``
    4. **Answer assembly** — concatenate top chunks
    5. **Cache result** — store in Redis for future identical queries
    """
    try:
        start = asyncio.get_event_loop().time()
        result = await answer_pipeline.answer_query(
            user_id=user_id, query=request.query,
            top_k=request.top_k, rerank_top_k=request.rerank_top_k,
            hybrid_search=hybrid_search, reranker=reranker,
            semantic_cache=semantic_cache, llm=local_llm,
        )
        return QueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            processing_time=asyncio.get_event_loop().time() - start,
            reasoning=result.get("reasoning", ""),
            refused=result.get("refused", False),
        )
    except Exception as exc:
        logger.error(f"Query error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/query/stream", tags=["Search"], summary="Streaming grounded AI answer (SSE)")
async def query_stream(request: QueryRequest, user_id: str = Depends(require_current_user)):
    """
    Server-Sent Events version of ``/query`` that streams a grounded AI answer.

    Event sequence: ``sources`` (once) → ``thinking``* (only when thinking is
    enabled) → ``token``* → ``done``. If the refusal gate trips, it's
    ``sources`` → ``refusal`` → ``done`` and the model is never called.
    """
    async def _events():
        try:
            async for event, data in answer_pipeline.stream_answer(
                user_id=user_id, query=request.query,
                top_k=request.top_k, rerank_top_k=request.rerank_top_k,
                hybrid_search=hybrid_search, reranker=reranker,
                semantic_cache=semantic_cache, llm=local_llm,
            ):
                # JSON-encode every payload (even token strings) so the client
                # parses uniformly and newlines never break SSE framing.
                yield {"event": event, "data": json.dumps(data)}
        except Exception as exc:
            logger.error(f"Query stream error: {exc}")
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}

    return EventSourceResponse(_events())


# ─── SSE progress stream ──────────────────────────────────────────────────────

@app.get("/progress/{task_id}", tags=["System"], summary="SSE progress stream for a background task")
async def stream_progress(task_id: str, user_id: str = Depends(require_current_user)):
    """
    Server-Sent Events endpoint that streams progress updates (0–100 %)
    for a background ingestion task.
    """
    async def _generator():
        for i in range(10):
            yield {
                "event": "progress",
                "data": json.dumps({"progress": (i + 1) * 10, "message": f"Step {i + 1} / 10"}),
            }
            await asyncio.sleep(0.5)
        yield {"event": "complete", "data": json.dumps({"message": "Processing complete"})}

    return EventSourceResponse(_generator())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)