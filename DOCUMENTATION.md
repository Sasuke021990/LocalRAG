# LocalRAG v2.0 — Complete Documentation

> **Private Knowledge Intelligence** — Hybrid Search · Cross-Encoder Re-ranking · Semantic Caching · Zero Cloud

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Data Flow](#3-data-flow)
4. [Storage Strategy](#4-storage-strategy)
5. [Category System](#5-category-system)
6. [API Reference](#6-api-reference)
7. [Frontend Guide](#7-frontend-guide)
8. [Docker Setup](#8-docker-setup)
9. [Backup and Restore](#9-backup--restore)
10. [Configuration](#10-configuration)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Overview

LocalRAG is a **fully local RAG system**. Upload documents, organise them into categories, and search using hybrid BM25 + vector search fused via Reciprocal Rank Fusion. Results are re-ranked with a cross-encoder neural model and repeated queries are served instantly from semantic cache.

**Nothing leaves your machine.** No cloud APIs, no telemetry.

---

## 2. Architecture

`
Frontend (Streamlit :8501)
        |  HTTP
        v
Backend (FastAPI :8000)
  |-- Ingestion Pipeline
  |     - File parser (PDF/DOCX/TXT/CSV/MD/HTML/JSON/XML)
  |     - Text chunker (overlap)
  |     - Embedding generator (all-MiniLM-L6-v2, 384-dim)
  |-- Retrieval Engine
  |     - BM25 sparse search
  |     - Vector dense search
  |     - RRF Fusion
  |     - Cross-encoder rerank (ms-marco-MiniLM-L-6-v2)
  |-- Semantic Cache (Redis)
        v
Redis Stack (:6379)
  - Document chunks + embeddings (key: document:<category>:<file>)
  - Semantic query cache
  - RedisInsight UI (:8001)
        v
Mounted Volume
  Container: /app/data
  Host:      D:\DockerData\MyKnowledge\
    <category>/
      document.json   <- JSON backup (original file deleted after ingest)
`

### Services

| Service | Port | Purpose |
|---|---|---|
| local-rag-frontend | 8501 | Streamlit UI |
| local-rag-backend  | 8000 | FastAPI REST API |
| local-rag-redis    | 6379 | Vector store + cache |
| RedisInsight       | 8001 | Redis browser UI |

---

## 3. Data Flow

### 3.1 Document Upload and Ingestion

`
User uploads file via UI
  -> POST /upload (with category)
  -> File saved to /app/data/<category>/<filename>
  -> Background Task:
       1. Validate file type
       2. Parse document
       3. Chunk text (with overlap)
       4. Generate embeddings (all-MiniLM-L6-v2, 384-dim)
       5a. Store in Redis   key: document:<category>:<file>
       5b. Save JSON backup /app/data/<category>/<stem>.json
       6. DELETE original file
`

### 3.2 Query / Search

`
User types a question
  -> POST /query {query, top_k, rerank_top_k}
  -> 1. Semantic Cache lookup
         CACHE HIT:  return instantly
         CACHE MISS: continue
  -> 2. Hybrid Search (BM25 + Vector, fused via RRF)
  -> 3. Cross-Encoder Reranking (ms-marco-MiniLM-L-6-v2)
  -> 4. Build answer from top-K chunks
  -> 5. Store result in cache
  -> Return {answer, sources, processing_time}
`

### 3.3 Container Restart (Auto Re-index)

`
Container starts
  -> @startup: reindex_from_disk("/app/data")
  -> Scan all *.json files under /app/data/<category>/
  -> For each JSON backup:
       if Redis key NOT exists -> restore to Redis
  -> API ready — zero data loss
`

---

## 4. Storage Strategy

LocalRAG uses two complementary storage layers:

| Layer | Technology | Location | Purpose |
|---|---|---|---|
| Fast store | Redis | Docker volume redis_data | Sub-millisecond search |
| Durable backup | JSON files | /app/data/<category>/ -> D:\DockerData\MyKnowledge\ | Survive container wipes |

### Redis Key Format

    document:<category>:<original_filename>

    Examples:
      document:General:company_policy.pdf
      document:Research:arxiv_paper.pdf
      document:Finance:q4_report.docx

### JSON Backup Format

Each processed document produces a .json file at:
    D:\DockerData\MyKnowledge\<category>\<stem>.json

Example uploading research_paper.pdf to category Research:
    D:\DockerData\MyKnowledge\
      Research\
        research_paper.json   <- backup (original .pdf is deleted)

JSON structure:
`json
{
  "file_name":    "research_paper.pdf",
  "category":     "Research",
  "chunks":       ["chunk 1 text...", "chunk 2 text..."],
  "embeddings":   [[0.12, -0.34, ...], [0.56, 0.78, ...]],
  "chunk_count":  42,
  "processed_at": "2026-05-20T18:30:00.123456"
}
`

### Survival Matrix

| Event | Redis data | JSON backups | Recovery |
|---|---|---|---|
| docker-compose restart | Safe | Safe | None needed |
| docker-compose down | Safe | Safe | None needed |
| docker-compose down -v | LOST | Safe | Auto re-indexed on next start |
| docker volume prune | LOST | Safe | Auto re-indexed on next start |
| Delete D:\DockerData\MyKnowledge | Safe (until restart) | LOST | Re-upload documents |
| New machine | LOST | Copy folder | Copy + restart |

---

## 5. Category System

Categories are real directories on your mapped volume. Creating a category Finance immediately creates D:\DockerData\MyKnowledge\Finance\.

### Via UI
Knowledge Base tab -> Categories panel -> enter name -> Create Category

### Via API
    curl -X POST http://localhost:8000/categories \
      -H "Content-Type: application/json" \
      -d '{"name": "Finance"}'

### Default Category
If no category is specified, documents go to General.

---

## 6. API Reference

Full interactive docs at: http://localhost:8000/docs

### GET /
Returns API version and status.
Response: {"message": "LocalRAG API v2.0 is running", "version": "2.0.0"}

### GET /health
Health check.
Response: {"status": "healthy", "version": "2.0.0"}

### GET /categories
List all categories.
Response: {"categories": ["Finance", "General", "Research"], "total": 3}

### POST /categories
Create a new category.
Body: {"name": "Legal"}
Response: {"status": "created", "category": "Legal"}

### GET /documents
List all indexed documents with metadata.
Response: {
  "documents": [{
    "key": "document:Research:paper.pdf",
    "file_name": "paper.pdf",
    "category": "Research",
    "chunk_count": 42,
    "processed_at": "2026-05-20T18:30:00",
    "embedding_dimension": 384
  }],
  "total": 1
}

### DELETE /documents/{file_name}?category=Research
Delete from Redis and disk.
Response: {"status": "deleted", "file_name": "paper.pdf", "category": "Research"}

### POST /upload
Upload and ingest a document.
Form fields:
  file          - Document file (required)
  category      - Target category (default: General)
  chunk_size    - Characters per chunk (default: 512)
  chunk_overlap - Overlap between chunks (default: 50)

Response: {
  "status": "processing_started",
  "filename": "report.pdf",
  "category": "Finance",
  "message": "'report.pdf' queued for ingestion in category 'Finance'"
}

NOTE: Processing is asynchronous. Poll GET /documents to confirm completion.

### POST /query
Search the knowledge base.
Body: {"query": "What is the refund policy?", "top_k": 10, "rerank_top_k": 5}
Response: {
  "answer": "Based on the retrieved documents...",
  "sources": [{
    "file_name": "policy.pdf",
    "category": "General",
    "chunk_index": 3,
    "score": 0.9823,
    "content": "The refund policy states..."
  }],
  "processing_time": 0.342
}

If query was found in semantic cache, processing_time will be 0.0.

### GET /progress/{task_id}
Server-Sent Events stream for background task progress.

---

## 7. Frontend Guide

Access at http://localhost:8501

### Stats Bar
Four live-updating cards:
- Documents   - total in Redis
- Categories  - number of folders
- Hybrid Search - always active
- Backend API - green=online, red=offline

### Chat Tab
1. Adjust Retrieve and After rerank sliders
2. Optionally select a Category Filter
3. Type your question -> press Send
4. Click Sources to see which chunks were used

### Knowledge Base Tab

Left panel - Categories:
- Create new category folders
- See document count per category

Right panel - Upload:
1. Select target category
2. Set chunk size/overlap (defaults are fine)
3. Drop files onto upload area
4. Click Ingest Selected Documents
5. Processing is async - refresh after a few seconds

Right panel - Document Library:
- Search by name
- Filter by category
- See: name, category, chunk count, embedding dimension, date
- Click trash icon to delete (removes Redis + JSON backup)

### API Docs Tab
Embeds Swagger UI - click any endpoint, Try it out, Execute to test live.

---

## 8. Docker Setup

### Start
    cd "F:\Projects\VS Code\LocalRAG"
    docker-compose up -d

### Stop (preserves data)
    docker-compose down

### Stop and wipe Redis volume (JSON backups safe)
    docker-compose down -v

### Rebuild after code changes
    docker-compose up --build -d

### View logs
    docker-compose logs -f
    docker logs local-rag-backend -f

### Service URLs
    http://localhost:8501  - Streamlit frontend
    http://localhost:8000  - FastAPI backend
    http://localhost:8000/docs  - Swagger UI
    http://localhost:8001  - RedisInsight

---

## 9. Backup and Restore

### Backup
    Copy-Item -Recurse "D:\DockerData\MyKnowledge" "D:\Backups\MyKnowledge-20260521"

### Restore to new machine
1. Copy D:\DockerData\MyKnowledge\ to the new machine
2. Update docker-compose.yml volume path if needed
3. Run docker-compose up -d
4. Startup re-index will auto-populate Redis from JSON backups

### Inspect a document
    Get-Content "D:\DockerData\MyKnowledge\Research\my_paper.json" | python -m json.tool

---

## 10. Configuration

### Environment Variables
| Variable | Default | Description |
|---|---|---|
| REDIS_HOST | redis | Redis hostname |
| REDIS_PORT | 6379 | Redis port |
| REDIS_DB   | 0    | Redis database |

### Embedding Model
Default: all-MiniLM-L6-v2 (384-dim, ~80MB, fast)
Change in backend/main.py: embedding_model="BAAI/bge-small-en-v1.5"

### Reranker Model
Default: cross-encoder/ms-marco-MiniLM-L-6-v2
Change in backend/main.py: model_name="cross-encoder/ms-marco-MiniLM-L-12-v2"

### Volume Path
Edit docker-compose.yml:
    volumes:
      - D:\DockerData\MyKnowledge:/app/data

---

## 11. Troubleshooting

### Backend won't start
    docker logs local-rag-backend
Common: Redis not ready (wait 10s), port 8000 in use.

### Documents not appearing after upload
Processing is async - wait 10-30s then check:
    curl http://localhost:8000/documents

### Files not in D:\DockerData\MyKnowledge
Original files ARE deleted after ingestion. Only *.json backups persist.

### Query returns empty results
BM25 index rebuilds at runtime. After uploading, results appear on the next query.

### Frontend shows Backend API: Offline
Backend needs ~30-60s on first start (downloads ML models).
    docker ps
    docker logs local-rag-backend

### docker-compose down -v lost Redis data
JSON backups in D:\DockerData\MyKnowledge are intact. Just run:
    docker-compose up -d
Startup re-index restores everything automatically.
