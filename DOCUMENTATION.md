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
  Host:      $KNOWLEDGE_DATA_PATH
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
| Durable backup | JSON files | /app/data/<category>/ -> $KNOWLEDGE_DATA_PATH | Survive container wipes |

### Redis Key Format

    document:<category>:<original_filename>

    Examples:
      document:General:company_policy.pdf
      document:Research:arxiv_paper.pdf
      document:Finance:q4_report.docx

### Vector Index

Each chunk is additionally written to its own HASH (`chunk:<category>:<file>:<chunk_index>`)
and indexed by a RediSearch HNSW vector field (`idx:chunks`, cosine
similarity, 384-dim) so queries can run a real KNN search instead of
scanning every chunk. This index is fully derived from the `document:*`
blobs and is rebuilt automatically by the startup re-index if it's ever
out of date. Inspect it directly with:

    redis-cli FT.INFO idx:chunks

### JSON Backup Format

Each processed document produces a .json file at:
    $KNOWLEDGE_DATA_PATH/<category>/<stem>.json

Example uploading research_paper.pdf to category Research:
    $KNOWLEDGE_DATA_PATH/
      Research/
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
| Delete $KNOWLEDGE_DATA_PATH | Safe (until restart) | LOST | Re-upload documents |
| New machine | LOST | Copy folder | Copy + restart |

---

## 5. Category System

Categories are real directories on your mapped volume. Creating a category Finance immediately creates $KNOWLEDGE_DATA_PATH/Finance/.

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

Every route below except `GET /`, `GET /health`, and `POST /auth/*` requires
a signed-in session — an httpOnly cookie (set automatically for web
clients) or an `Authorization: Bearer <token>` header (mobile/API
clients). See section 10 for `JWT_SECRET`.

### POST /auth/signup
Create an account. Body: {"email": "you@example.com", "password": "at least 8 chars"}
Response: {"user_id", "email", "storage_used_bytes", "storage_quota_bytes", "session_token"}
Also sets the session cookie.

### POST /auth/login
Body: {"email", "password"}. Same response shape as signup.

### POST /auth/logout
No body required. Clears the session cookie. Response: {"status": "logged_out"}

### GET /auth/me
Requires a session. Response: {"user_id", "email", "storage_used_bytes", "storage_quota_bytes"}

### GET /auth/google/login
Redirects to Google's consent screen. Requires `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` configured.

### GET /auth/google/callback?code=...
Google redirects here after consent. Exchanges the code for the user's Google identity,
finds-or-creates a Vaultly account (linking by email if a password-based account already
exists with the same address), sets the session cookie, and redirects to `FRONTEND_BASE_URL`.

### POST /auth/password-reset/request
Body: {"email"}. Always returns `{"status": "ok"}` regardless of whether the email is
registered (never leaks account existence). If it is, sends a reset link via SMTP
(requires `SMTP_HOST` configured; silently no-ops otherwise).

### POST /auth/password-reset/confirm
Body: {"token", "new_password"}. Sets the new password and invalidates every existing
session for that account (including a possibly-hijacked one -- exactly the scenario a
reset is meant to recover from). Response: {"status": "password_updated"}. 400 if the
token is invalid or has expired (tokens are single-use, 1-hour TTL).

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

## 6a. Integrations API (MCP/API tokens + webhooks)

These routes let a user connect external AI tools and receive event
notifications. All `POST /integrations/*` and management routes require a
**logged-in session** — an MCP/API token is deliberately **not** accepted
here (it can read/write your data, but it cannot mint more tokens or
register webhooks). Data routes like `/query` accept either a session or a
token.

### API tokens

A token is an opaque, revocable credential (`vlt_…`) you paste into an MCP
client or API caller. It authenticates as you, so `/query`, `/documents`,
`/upload`, etc. all work with an `Authorization: Bearer vlt_…` header.
Only a SHA-256 hash is stored; the plaintext is shown **once**.

- **POST /integrations/tokens** — Body: `{"name": "my-laptop"}`. Response:
  `{"token_id", "name", "token": "vlt_…", "prefix", "created_at"}`. The
  `token` field is the only time you'll see the secret — copy it now.
- **GET /integrations/tokens** — `{"tokens": [{"token_id", "name",
  "prefix", "created_at", "last_used_at"}], "total"}`. Never returns the
  secret.
- **DELETE /integrations/tokens/{token_id}** — Revoke immediately.
  `{"status": "revoked", "token_id"}`.

### Webhooks

Register HTTP endpoints Vaultly POSTs to on document lifecycle events.
Payloads carry **metadata only** (never document content).

Supported events: `document.ingested`, `document.deleted`,
`document.ingest_failed`.

- **POST /integrations/webhooks** — Body: `{"url": "https://…",
  "events": ["document.ingested"], "secret": "optional"}`. A signing
  secret is generated if omitted and returned in the response so you can
  verify deliveries.
- **GET /integrations/webhooks** — List your webhooks (with delivery
  stats: `last_status`, `last_delivered_at`, `failure_count`).
- **DELETE /integrations/webhooks/{webhook_id}** — Remove it.
- **POST /integrations/webhooks/{webhook_id}/test** — Send a `ping` event
  to verify connectivity.

**Delivery format.** Each delivery is a POST with JSON body
`{"event", "timestamp", "data": {…}}` and headers:

| Header | Meaning |
| --- | --- |
| `X-Vaultly-Event` | The event type (or `ping` for a test) |
| `X-Vaultly-Delivery` | Unique delivery id |
| `X-Vaultly-Signature` | `sha256=<hmac>` of the exact body, keyed by your webhook secret |

**Verifying the signature** (Python):

```python
import hmac, hashlib
expected = "sha256=" + hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
assert hmac.compare_digest(expected, request.headers["X-Vaultly-Signature"])
```

Delivery is best-effort with up to `WEBHOOK_MAX_RETRIES` attempts and a
`WEBHOOK_TIMEOUT_SECONDS` per-attempt timeout (see section 10).

---

## 6b. Admin API (metadata-only)

Operator endpoints for managing users and runtime settings. **All admin
routes require a logged-in admin session** — an MCP/API token is never
accepted. A user is an admin if their email matches `ADMIN_EMAIL`
(section 10) or another admin has promoted them.

> **Privacy guarantee (architectural, not cosmetic):** no admin endpoint
> can return any user's document content, chunk text, query history, or
> cache entries. Admins see only account metadata (email, storage
> used/quota, status, created_at) and *counts* (documents, webhooks,
> tokens). This is enforced in the data-access layer.

### Users
- **GET /admin/users?limit=&offset=** — List users with metadata + document count.
- **GET /admin/users/{user_id}** — One user's metadata + document/webhook/token counts.
- **PATCH /admin/users/{user_id}/quota** — Body: `{"quota_bytes": 5368709120}`. Increase/decrease a user's storage quota.
- **PATCH /admin/users/{user_id}/status** — Body: `{"is_active": false}`. Deactivate (their sessions immediately 403) or reactivate an account.
- **PATCH /admin/users/{user_id}/admin** — Body: `{"is_admin": true}`. Promote/demote an admin.
- **DELETE /admin/users/{user_id}** — Permanently delete a user and **all** their data (documents, chunks, cache, tokens, webhooks, disk backups).

The root admin (`ADMIN_EMAIL`) and your own account are protected: you
cannot deactivate, demote, or delete them (400).

### System
- **GET /admin/stats** — Aggregate metadata: `{total_users, active_users, admin_users, total_storage_used_bytes, total_documents, total_webhooks, total_tokens}`.
- **GET /admin/settings** — Current runtime settings.
- **PATCH /admin/settings** — Body: `{"name": "signups_enabled", "value": false}` or `{"name": "default_storage_quota_bytes", "value": 2147483648}`. Runtime-mutable settings (take effect immediately, no restart): `signups_enabled` (open/close public registration) and `default_storage_quota_bytes` (quota new signups inherit).

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
    Copy-Item -Recurse "$KNOWLEDGE_DATA_PATH" "$KNOWLEDGE_DATA_PATH-backup-20260521"

### Restore to new machine
1. Copy $KNOWLEDGE_DATA_PATH to the new machine
2. Update docker-compose.yml volume path if needed
3. Run docker-compose up -d
4. Startup re-index will auto-populate Redis from JSON backups

### Inspect a document
    Get-Content "$KNOWLEDGE_DATA_PATH/Research/my_paper.json" | python -m json.tool

---

## 10. Configuration

### Environment Variables
Set these in `.env` (copy from `.env.example`) — `docker-compose.yml` reads them at startup.

| Variable | Default | Description |
|---|---|---|
| REDIS_HOST | redis | Redis hostname |
| REDIS_PORT | 6379 | Redis port |
| REDIS_DB   | 0    | Redis database |
| KNOWLEDGE_DATA_PATH | ./data | Host directory mounted at /app/data |
| REDIS_DATA_PATH | (named volume) | Host directory mounted at /data (TrueNAS compose only) |
| JWT_SECRET | (required) | Signs account session tokens (`openssl rand -hex 32`) — app refuses to start without it |
| SESSION_COOKIE_MAX_AGE_SECONDS | 604800 (7 days) | Session lifetime |
| DEFAULT_STORAGE_QUOTA_BYTES | 1073741824 (1 GiB) | Default per-account storage quota |
| FRONTEND_BASE_URL | http://localhost:3000 | Used to build password-reset links and the post-OAuth-login redirect |
| ADMIN_EMAIL | (unset) | Email of the operator/admin account — grants access to the metadata-only admin panel (`/admin/*`) |
| GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET | (unset) | Optional — enables "Sign in with Google" when both are set |
| GOOGLE_REDIRECT_URI | http://localhost:3000/api/auth/google/callback | Must match the redirect URI registered in the Google Cloud Console |
| SMTP_HOST / SMTP_USER / SMTP_PASSWORD | (unset) | Optional — enables password-reset emails when SMTP_HOST is set |
| SMTP_PORT / SMTP_FROM / SMTP_USE_TLS | 587 / noreply@vaultly.local / True | SMTP delivery settings |
| CORS_ALLOWED_ORIGINS | http://localhost:3000 | Comma-separated list of allowed CORS origins |
| SEMANTIC_CACHE_SIMILARITY_THRESHOLD | 0.92 | Minimum cosine similarity for a semantic cache hit |
| WEBHOOK_MAX_RETRIES | 3 | Delivery attempts per webhook event before giving up |
| WEBHOOK_TIMEOUT_SECONDS | 5 | Per-attempt HTTP timeout for webhook delivery |

### Embedding Model
Default: all-MiniLM-L6-v2 (384-dim, ~80MB, fast)
Change in backend/main.py: embedding_model="BAAI/bge-small-en-v1.5"

### Reranker Model
Default: cross-encoder/ms-marco-MiniLM-L-6-v2
Change in backend/main.py: model_name="cross-encoder/ms-marco-MiniLM-L-12-v2"

### Volume Path
Set `KNOWLEDGE_DATA_PATH` in `.env` (docker-compose.yml reads it via
`${KNOWLEDGE_DATA_PATH:-./data}` — no need to edit the compose file itself):
    KNOWLEDGE_DATA_PATH=/your/host/path

---

## 11. Troubleshooting

### Backend won't start
    docker logs local-rag-backend
Common: Redis not ready (wait 10s), port 8000 in use.

### Documents not appearing after upload
Processing is async - wait 10-30s then check:
    curl http://localhost:8000/documents

### Files not in $KNOWLEDGE_DATA_PATH
Original files ARE deleted after ingestion. Only *.json backups persist.

### Query returns empty results
BM25 index rebuilds at runtime. After uploading, results appear on the next query.

### Frontend shows Backend API: Offline
Backend needs ~30-60s on first start (downloads ML models).
    docker ps
    docker logs local-rag-backend

### docker-compose down -v lost Redis data
JSON backups in $KNOWLEDGE_DATA_PATH are intact. Just run:
    docker-compose up -d
Startup re-index restores everything automatically.
