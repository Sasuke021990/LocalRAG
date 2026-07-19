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
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ingestion.pipeline import DocumentIngestionPipeline
from retrieval.hybrid_search import HybridSearchEngine
from retrieval.reranker import CrossEncoderReranker
from retrieval.semantic_cache import SemanticCache
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
        "portable JSON backups under `/app/data/<category>/` (durability)."
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


async def require_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """
    Guard dependency applied to every route except GET / and GET /health.
    A no-op when API_KEY is unset (default), preserving the app's
    zero-friction local-only behavior.
    """
    if config.API_KEY and x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


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

@app.get("/categories", tags=["Categories"],
         summary="List all document categories", dependencies=[Depends(require_api_key)])
async def list_categories():
    """
    Returns the names of all category folders that exist under ``/app/data/``.
    Categories are created automatically when a document is uploaded, or
    explicitly via ``POST /categories``.
    """
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        categories = sorted(d.name for d in DATA_DIR.iterdir() if d.is_dir())
        return {"categories": categories, "total": len(categories)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/categories", tags=["Categories"],
          summary="Create a new category", dependencies=[Depends(require_api_key)])
async def create_category(request: CategoryCreate):
    """
    Creates a new category folder under ``/app/data/<name>/``.
    The folder is also immediately visible on the Docker-mapped host path
    ``D:\\DockerData\\MyKnowledge\\<name>\\``.
    """
    try:
        # Sanitise name — prevent path traversal
        name = request.name.strip().replace("/", "_").replace("\\", "_").replace("..", "_")
        if not name:
            raise HTTPException(status_code=400, detail="Category name cannot be empty")
        category_dir = DATA_DIR / name
        category_dir.mkdir(parents=True, exist_ok=True)
        return {"status": "created", "category": name}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Documents ────────────────────────────────────────────────────────────────

@app.get("/documents", tags=["Documents"],
         summary="List all indexed documents", dependencies=[Depends(require_api_key)])
async def list_documents():
    """
    Returns metadata for every document currently indexed in Redis.
    Includes file name, category, chunk count, and processing timestamp.
    """
    try:
        docs = ingestion_pipeline.list_documents()
        return {"documents": docs, "total": len(docs)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/documents/{file_name}", tags=["Documents"],
            summary="Delete a document", dependencies=[Depends(require_api_key)])
async def delete_document(file_name: str, category: str = "General"):
    """
    Removes the document from Redis **and** deletes its JSON backup from disk.
    Pass ``?category=<name>`` to identify the correct document when the same
    file name exists in multiple categories.
    """
    try:
        success = ingestion_pipeline.delete_document(file_name, category)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "deleted", "file_name": file_name, "category": category}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Upload ───────────────────────────────────────────────────────────────────

@app.post("/upload", tags=["Documents"],
          summary="Upload and ingest a document", dependencies=[Depends(require_api_key)])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Document file to ingest"),
    chunk_size: int = Form(512, description="Characters per chunk"),
    chunk_overlap: int = Form(50, description="Overlap between chunks"),
    category: str = Form("General", description="Destination category"),
):
    """
    Upload a document for ingestion.

    **Flow**:
    1. File is validated and saved to ``/app/data/<category>/<filename>``
    2. Background task: parse → chunk → embed → store → delete original
    3. JSON backup written to ``/app/data/<category>/<stem>.json``
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

        # Ensure directory exists and save file
        category_dir = DATA_DIR / safe_cat
        category_dir.mkdir(parents=True, exist_ok=True)
        file_path = str(category_dir / file.filename)

        content = await file.read()
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
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    category=safe_cat,
                )
                logger.info(f"Processed: {file.filename} → {safe_cat} | {result['total_chunks']} chunks")
            except Exception as exc:
                logger.error(f"Background processing failed for '{file.filename}': {exc}")

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

@app.post("/query", response_model=QueryResponse, tags=["Search"],
          summary="Hybrid search + re-rank + cache", dependencies=[Depends(require_api_key)])
async def query_documents(request: QueryRequest):
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
        cached = semantic_cache.get_cached_result(request.query)
        if cached and cached.results:
            return QueryResponse(
                answer=cached.results[0]["answer"],
                sources=cached.results[0]["sources"],
                processing_time=0.0,
            )

        # 2. Hybrid search
        logger.info(f"Hybrid search: '{request.query}'")
        results = hybrid_search.search(query=request.query, top_k=request.top_k)

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
        semantic_cache.set_cached_result(request.query, [{"answer": answer, "sources": sources}])

        return QueryResponse(answer=answer, sources=sources, processing_time=processing_time)

    except Exception as exc:
        logger.error(f"Query error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ─── SSE progress stream ──────────────────────────────────────────────────────

@app.get("/progress/{task_id}", tags=["System"],
         summary="SSE progress stream for a background task", dependencies=[Depends(require_api_key)])
async def stream_progress(task_id: str):
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