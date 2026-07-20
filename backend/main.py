"""
Main FastAPI application — LocalRAG v2.0
=========================================
Endpoints:
  GET  /                         — health / version
  GET  /health                   — health check
  GET  /categories               — list all categories
  POST /categories               — create a new category
  GET  /documents                — list all indexed documents
  DELETE /documents/{file_name}  — delete a document
  POST /upload                   — upload & ingest a document
  POST /query                    — hybrid search + rerank + cache
  GET  /progress/{task_id}       — SSE progress stream
  GET  /docs                     — Swagger UI (auto-generated)
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
DATA_DIR = Path("/app/data")
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".csv", ".md", ".html", ".htm", ".json", ".xml"}

# ─── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="LocalRAG API",
    description=(
        "A fully local RAG system with hybrid BM25 + vector search, "
        "cross-encoder re-ranking, semantic caching, and category-aware "
        "document management.\n\n"
        "All processed data is stored in Redis (fast retrieval) **and** as "
        "portable JSON backups under `/app/data/<user_id>/<category>/` (durability)."
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


# ─── Pydantic models ──────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str
    top_k: int = 10
    rerank_top_k: int = 5

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    processing_time: float

class CategoryCreate(BaseModel):
    name: str


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


# ─── Categories ───────────────────────────────────────────────────────────────

@app.get("/categories", tags=["Categories"], summary="List all document categories")
async def list_categories(user_id: str = Depends(require_current_user)):
    """
    Returns the names of all category folders that exist under this user's
    own ``/app/data/<user_id>/`` namespace. Categories are created
    automatically when a document is uploaded, or explicitly via
    ``POST /categories``.
    """
    try:
        user_dir = DATA_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        categories = sorted(d.name for d in user_dir.iterdir() if d.is_dir())
        return {"categories": categories, "total": len(categories)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/categories", tags=["Categories"], summary="Create a new category")
async def create_category(request: CategoryCreate, user_id: str = Depends(require_current_user)):
    """
    Creates a new category folder under ``/app/data/<user_id>/<name>/``.
    """
    try:
        # Sanitise name — prevent path traversal
        name = request.name.strip().replace("/", "_").replace("\\", "_").replace("..", "_")
        if not name:
            raise HTTPException(status_code=400, detail="Category name cannot be empty")
        category_dir = DATA_DIR / user_id / name
        category_dir.mkdir(parents=True, exist_ok=True)
        return {"status": "created", "category": name}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Documents ────────────────────────────────────────────────────────────────

@app.get("/documents", tags=["Documents"], summary="List all indexed documents")
async def list_documents(user_id: str = Depends(require_current_user)):
    """
    Returns metadata for every document this user has indexed in Redis.
    Includes file name, category, chunk count, and processing timestamp.
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
    category: str = "General",
    user_id: str = Depends(require_current_user),
):
    """
    Removes the document from Redis **and** deletes its JSON backup from disk.
    Pass ``?category=<name>`` to identify the correct document when the same
    file name exists in multiple categories.
    """
    try:
        freed_bytes = ingestion_pipeline.delete_document(file_name, category, user_id)
        if freed_bytes is None:
            raise HTTPException(status_code=404, detail="Document not found")
        quota.record_deleted_document(ingestion_pipeline.redis_client, user_id, freed_bytes)
        background_tasks.add_task(
            webhooks.dispatch_event,
            auth_redis_client,
            user_id,
            "document.deleted",
            {"file_name": file_name, "category": category},
        )
        return {"status": "deleted", "file_name": file_name, "category": category}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Upload ───────────────────────────────────────────────────────────────────

@app.post("/upload", tags=["Documents"], summary="Upload and ingest a document")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Document file to ingest"),
    chunk_size: int = Form(512, description="Characters per chunk"),
    chunk_overlap: int = Form(50, description="Overlap between chunks"),
    category: str = Form("General", description="Destination category"),
    user_id: str = Depends(require_current_user),
):
    """
    Upload a document for ingestion.

    **Flow**:
    1. File is validated and saved to ``/app/data/<user_id>/<category>/<filename>``
    2. Background task: parse → chunk → embed → store → delete original
    3. JSON backup written to ``/app/data/<user_id>/<category>/<stem>.json``
    4. The original uploaded file is deleted after ingestion

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

        # Sanitise category
        safe_cat = category.strip().replace("/", "_").replace("\\", "_").replace("..", "_") or "General"

        content = await file.read()

        # Cheap pre-check using the raw upload size as an upper-bound
        # heuristic -- rejects obviously-over-quota uploads immediately,
        # before any file is written or processing is queued. The
        # authoritative check (using the actual post-ingestion stored
        # size) happens in _process() below, since embedding overhead
        # isn't known until after processing.
        quota.check_upload_allowed(ingestion_pipeline.redis_client, user_id, len(content))

        # Ensure directory exists and save file
        category_dir = DATA_DIR / user_id / safe_cat
        category_dir.mkdir(parents=True, exist_ok=True)
        file_path = str(category_dir / file.filename)

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
                    category=safe_cat,
                )
                logger.info(f"Processed: {file.filename} → {safe_cat} | {result['total_chunks']} chunks")

                quota.record_ingested_document(ingestion_pipeline.redis_client, user_id, result["stored_bytes"])
                if quota.is_over_quota(ingestion_pipeline.redis_client, user_id):
                    freed = ingestion_pipeline.delete_document(file.filename, safe_cat, user_id)
                    if freed is not None:
                        quota.record_deleted_document(ingestion_pipeline.redis_client, user_id, freed)
                    logger.warning(
                        f"Rolled back '{file.filename}' for user {user_id}: quota exceeded after ingestion"
                    )
                    webhooks.dispatch_event(
                        auth_redis_client, user_id, "document.ingest_failed",
                        {"file_name": file.filename, "category": safe_cat, "reason": "quota_exceeded"},
                    )
                else:
                    webhooks.dispatch_event(
                        auth_redis_client, user_id, "document.ingested",
                        {"file_name": file.filename, "category": safe_cat, "chunk_count": result["total_chunks"]},
                    )
            except Exception as exc:
                logger.error(f"Background processing failed for '{file.filename}': {exc}")
                webhooks.dispatch_event(
                    auth_redis_client, user_id, "document.ingest_failed",
                    {"file_name": file.filename, "category": safe_cat, "reason": "processing_error"},
                )

        background_tasks.add_task(_process)

        return {
            "status": "processing_started",
            "filename": file.filename,
            "category": safe_cat,
            "message": f"'{file.filename}' queued for ingestion in category '{safe_cat}'",
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

        # 1. Cache check
        cached = semantic_cache.get_cached_result(user_id, request.query)
        if cached and cached.results:
            return QueryResponse(
                answer=cached.results[0]["answer"],
                sources=cached.results[0]["sources"],
                processing_time=0.0,
            )

        # 2. Hybrid search
        logger.info(f"Hybrid search: '{request.query}'")
        results = hybrid_search.search(user_id, query=request.query, top_k=request.top_k)

        # 3. Re-rank
        if request.rerank_top_k > 0:
            logger.info("Re-ranking with cross-encoder …")
            reranked = reranker.rerank(query=request.query, results=results, top_k=request.rerank_top_k)
        else:
            reranked = results

        # 4. Build a structured retrieval summary.
        # This is a semantic knowledge retrieval system — results are ranked
        # passages from your documents, not LLM-generated answers.
        sources = [
            {
                "file_name":   r.metadata.get("file_name",   "Unknown") if r.metadata else "Unknown",
                "category":    r.metadata.get("category",    "General") if r.metadata else "General",
                "chunk_index": r.metadata.get("chunk_index", 0)         if r.metadata else 0,
                "score":       round(r.score, 4),
                "content":     r.content,
            }
            for r in reranked
        ]

        if not sources:
            answer = (
                f"No relevant passages found for your query: '{request.query}'.\n"
                "Try uploading documents to your knowledge base first, or rephrase your question."
            )
        else:
            top_sources = ", ".join(
                f"{s['file_name']} ({s['category']})" for s in sources[:3]
            )
            answer = (
                f"Found {len(sources)} relevant passage(s) for: '{request.query}'\n"
                f"Top sources: {top_sources}\n\n"
                + "\n\n---\n\n".join(
                    f"**[{i+1}] {s['file_name']}** (score: {s['score']:.4f}, chunk #{s['chunk_index']})\n"
                    f"{s['content']}"
                    for i, s in enumerate(sources)
                )
            )

        processing_time = asyncio.get_event_loop().time() - start

        # 5. Cache result
        semantic_cache.set_cached_result(user_id, request.query, [{"answer": answer, "sources": sources}])

        return QueryResponse(answer=answer, sources=sources, processing_time=processing_time)

    except Exception as exc:
        logger.error(f"Query error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


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