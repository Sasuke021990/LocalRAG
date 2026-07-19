# LocalRAG — Fix All Analysis Findings

## Context
A prior read-only analysis of this repo found 8 concrete gaps between what LocalRAG claims to do and what it actually implements: fake vector search, a fake semantic cache, a mock ingestion stub, dead code, stale dependency manifests, no tests/CI, no auth with wide-open CORS, and hardcoded host-specific deploy paths. This plan fixes all of them, keeping the diff scoped and low-risk by reading the actual source (storage schema, call sites, dependency graph) rather than guessing.

**Key implementation fact**: documents are stored in Redis as a single JSON-blob **STRING** per document (`document:<category>:<file_name>`, `pipeline.py::_store_in_redis`), with `chunks`/`embeddings` as parallel lists inside that blob. RediSearch can't index a STRING, which is *why* no vector index exists today. The fix adds a second, derived representation: one RediSearch-indexed **HASH per chunk** (`chunk:<category>:<file_name>:<i>`), rebuildable at any time from the existing JSON blobs — so the existing `reindex_from_disk()` startup hook (already wired into `main.py`'s startup event) becomes the natural, zero-manual-step migration path: it already runs on every container start and restores `document:*` keys from disk backups, so it's extended to also (re)populate the chunk vector index at the same time. No new migration script needed.

Auth scope: API-key protection applies to **all** routes except `GET /` and `GET /health` (which must stay open for Docker healthchecks).

## Step 0 — Branch + plan artifact
1. `git checkout -b fix/vector-search-auth-tests` from `origin/main`.
2. Write this plan to `/home/user/LocalRAG/plan.md`, commit alone first (`docs: add implementation plan`).

## Step 1 — Real vector search (replaces word-overlap scoring)
New file `backend/retrieval/vector_index.py` — shared schema/index module used by both writer (`pipeline.py`) and reader (`hybrid_search.py`):
- `ensure_index()` — idempotent `FT.CREATE` (RediSearch, already bundled in the `redis/redis-stack` image both compose files use) over `chunk:*` HASHes: fields `content` (TEXT), `file_name`/`category` (TAG), `chunk_index` (NUMERIC), `embedding` (VECTOR, HNSW, FLOAT32, DIM=384, COSINE). Must swallow "index already exists" since it's called from two constructors.
- `chunk_key()`, `index_chunk()` (HSET with embedding packed as float32 bytes), `delete_chunks()`, `knn_search()` (RediSearch `KNN` query, dialect 2).

Edits:
- `backend/ingestion/pipeline.py`: `__init__` calls `vector_index.ensure_index()`; `_store_in_redis()` additionally writes one chunk HASH per chunk via `index_chunk()`; `delete_document()` also calls `delete_chunks()`; **`reindex_from_disk()`** unconditionally re-indexes each backup's chunks (idempotent HSET) — this is the migration path for existing deployments, needs a docstring note.
- `backend/retrieval/hybrid_search.py`: `__init__` loads a `SentenceTransformer("all-MiniLM-L6-v2", device=get_best_device())` (same model/device pattern already used in `pipeline.py`/`reranker.py`) and calls `ensure_index()`. `search_redis()` body is replaced: embed the query, call `vector_index.knn_search()`, map to `SearchResult(source='vector', ...)`. `fuse_results()`/RRF logic is untouched — it already generically fuses two ranked lists, so it starts fusing real vector + BM25 rankings automatically.
- Also delete `HybridSearchEngine.add_document()` (`hybrid_search.py`) in the same commit — confirmed dead code (zero call sites anywhere), superseded entirely by `pipeline.py`'s real ingestion path; keeping a parallel stub risks silent drift.

Risk note: pre-existing deployments' vector search returns empty until one backend restart runs the reindex migration — call this out in the PR description and a one-line addition to `DOCUMENTATION.md`.

## Step 2 — Real semantic cache
Edit `backend/retrieval/semantic_cache.py`:
- Load a `SentenceTransformer` the same way (lazy, per-class instance — minimal diff vs. sharing one model instance across classes).
- Keep the MD5 exact-match path first (cheap fast path).
- Extend `set_cached_result()` to also store the query's embedding, and maintain a small Redis SET index of active cache keys (cheaper than `KEYS` scan on the hot query path).
- Implement `_is_semantically_similar()` for real: cosine similarity between query embeddings; wire it into `get_cached_result()` as a fallback after an exact-match miss, iterating the key-index SET.
- New configurable threshold (default `0.92`, deliberately conservative to avoid false-positive stale hits), added to `Config`.

## Step 3 — Delete dead code
- `git rm backend/ingestion/chunker.py backend/ingestion/document_loader.py` — confirmed unused anywhere (`TextChunker`, `DocumentLoader` have zero import sites outside their own files); `document_loader.py` is additionally broken against pinned deps (`import PyPDF2`/`import pandas`, neither present in `backend/requirements.txt`). Refactoring `pipeline.py` to use them instead was considered and rejected — it would change chunk-boundary/parsing behavior for no functional gain.
- Remove `langchain`/`langchain-community` from `backend/requirements.txt` (their only consumer was `chunker.py`) after a final grep confirms no other usage.
- Flag as a noted follow-up (not in this pass): `pipeline.py::_parse_html` imports `bs4` but `beautifulsoup4` is missing from `backend/requirements.txt` — a pre-existing latent bug, out of the originally-requested scope.

## Step 4 — Remove stale dependency manifests
`git rm requirements.txt requirements-frontend.txt` at repo root — confirmed zero references in any Dockerfile, compose file, or doc (only `backend/requirements.txt`, via `Dockerfile`, and `frontend_streamlit/requirements.txt` are actually used).

## Step 5 — Auth + CORS
- `backend/utils/config.py`: add `API_KEY` (unset = auth disabled, preserving today's zero-friction local default), `CORS_ALLOWED_ORIGINS` (comma-separated, default `http://localhost:3000`), plus the new tunables from Steps 1/2. `main.py` currently reads Redis env vars directly instead of through this existing `Config` class — normalize that inconsistency while touching the file.
- `backend/main.py`: `CORSMiddleware` origins driven by `Config` instead of `["*"]`; add a `require_api_key` dependency (401 if `API_KEY` set and header mismatches, no-op if unset) applied to **every** route except `GET /` and `GET /health`.
- `frontend/server.js`: inject the API key server-side into proxied backend requests (via `http-proxy-middleware`'s `onProxyReq`) so it never reaches the browser bundle — same pattern already used for `BACKEND_URL`.
- `mcp/index.js`: read `LOCALRAG_API_KEY` and set it as a header on its axios calls, so the MCP integration keeps working once auth is enabled.

Behavior-change note: CORS moving off `"*"` by default *does* change behavior for any client accessing from a non-default origin — called out explicitly in the PR description.

## Step 6 — Parameterize hardcoded deploy paths
- New `.env.example` at repo root documenting `KNOWLEDGE_DATA_PATH`, `REDIS_DATA_PATH`, `API_KEY`, `CORS_ALLOWED_ORIGINS`, etc.
- `docker-compose.yml`: replace the hardcoded Windows path (`D:\DockerData\MyKnowledge:/app/data`) with `${KNOWLEDGE_DATA_PATH:-./data}:/app/data`; wire in the new env vars from Step 5.
- `docker-compose.truenas.yml`: replace the hardcoded TrueNAS pool paths with the same env-var pattern.
- Ensure `.env` is gitignored (add to `.gitignore` if not already covered).
- `README.md`: document the new "copy `.env.example` to `.env`" setup step.

## Step 7 — Tests + CI (last, since it should test the real implementations from Steps 1–3)
- `backend/tests/` (pytest): `test_pipeline.py` (chunking/parsing/store/delete/reindex round-trip, including the Step 1 migration path), `test_hybrid_search.py` (BM25, vector KNN round-trip, RRF fusion math), `test_semantic_cache.py` (exact-match + new similarity-match behavior). Use `fakeredis` if it covers RediSearch vector commands sufficiently, otherwise a `redis/redis-stack` service container in CI (decide at implementation time, same image already used in both compose files).
- `frontend/`: minimal `vitest` unit tests for `api.js`'s fetch wrappers; ensure `npm run build` is part of CI as a build-break check.
- New `.github/workflows/ci.yml`: parallel `backend-tests` and `frontend-build` jobs on push/PR, with pip/npm and HuggingFace-cache steps to keep model-download-dependent tests from being slow/flaky.

## Ordering
Steps 1+3 touch the same files (`hybrid_search.py`) and must land together. Step 7 must follow 1–3 (tests need real behavior to test). Steps 2, 4, 5, 6 are independent of each other and of 1/3, and can be sequenced for convenience but don't block one another.

## Critical files
- `backend/retrieval/vector_index.py` (new)
- `backend/ingestion/pipeline.py`
- `backend/retrieval/hybrid_search.py`
- `backend/retrieval/semantic_cache.py`
- `backend/main.py`, `backend/utils/config.py`
- `docker-compose.yml`, `docker-compose.truenas.yml`, `.env.example` (new)
- `backend/tests/*` (new), `.github/workflows/ci.yml` (new)

## Verification
- Backend: `cd backend && PYTHONPATH=. pytest tests/ -v` once Step 7 lands; manually exercise `POST /upload` → `POST /query` end-to-end against a running `docker compose up` stack and confirm results come from real KNN vector search (e.g. via `redis-cli FT.INFO idx:chunks` showing indexed docs, and query results ranking correctly for paraphrased queries that word-overlap scoring would have missed).
- Semantic cache: query the same question two different ways and confirm the second hits cache (check logs for the logged similarity score).
- Auth: confirm `GET /health` works with no key; confirm a protected route 401s without `x-api-key` once `API_KEY` is set, and succeeds with it; confirm the frontend and MCP server still work end-to-end with auth enabled.
- CI: push the branch and confirm both GitHub Actions jobs go green.
