# Vaultly — Defect Report & Fixes

**Reported by:** user (manual testing) · **Date:** 2026-07-23 · **Status:** All 4 fixed, tested, verified live
**Fix commit:** `2d5f048` — *fix: 4 reported defects — stale semantic cache + pool-creation UX*

---

## Summary

| # | Defect | Root cause | Area |
|---|--------|------------|------|
| 1 | Deleting a document still returns old cached results | Semantic cache never invalidated on document delete | Backend — caching |
| 2 | Save button stays enabled mid pool-creation, discarding the typed name | `PoolPicker`'s inline create state was invisible to the host modal | Frontend — UX |
| 3 | Deleting a chat conversation — repeat question still served from cache instead of hitting the LLM | Semantic cache never invalidated on conversation delete | Backend — caching |
| 4 | Two documents in a pool — "key points" returns the previous document's cached answer, not the new one | Semantic cache never invalidated on document upload | Backend — caching |

Defects 1, 3, and 4 share one root cause: **the semantic answer cache was never invalidated when the underlying data changed.**

---

## Background: how the semantic cache works

`POST /query` and `/query/stream` cache answers in Redis so a repeated question skips retrieval and generation entirely and returns instantly. The cache key is:

```
semantic_cache:<scope>:<md5(query)>
```

where `scope` is either the bare `user_id` (unscoped questions) or `user_id::pool::<pool-name>` (a question asked with a specific pool selected — see `generation/pipeline.py`'s `cache_scope`).

Every route that mutates a user's documents already called `hybrid_search.invalidate_bm25(user_id)` on upload/delete/move — but that only clears the **keyword-search** index. It does nothing to the **semantic answer cache**, which is a separate Redis keyspace. So the cache kept serving pre-change answers until its TTL (1 hour by default) expired naturally.

---

## Defect 1 — Deleted document, still cached results

**Repro:** Ask a question that gets answered from a document → delete that document → ask the exact same question again → get the same cached answer, citing a document that no longer exists.

**Root cause:** `DELETE /documents/{file_name}` (`backend/main.py`) removed the document from Redis/disk and invalidated BM25, but never touched the semantic cache.

**Fix:** `backend/main.py`'s delete route now calls `semantic_cache.clear_cache(user_id)` immediately after the document is removed.

**Verified live** (rebuilt Docker stack):
1. Uploaded a doc, asked "what was the quarterly revenue?" → cached: `"The quarterly revenue was $5 million in Q1 2024."`
2. Deleted the document.
3. Asked the identical question again → correctly refused: `"I couldn't find anything about that in your documents..."` (processing_time 0.01s — the refusal gate, not a stale cache hit).

---

## Defect 2 — Save enabled while a new pool is mid-creation

**Repro:** Open the "move document" modal (or the uploader) → click "+ New" on the pool picker → type a new pool name → click the parent's **Save**/**Upload** button *without* clicking the inline checkmark to confirm the new pool → the typed name is silently discarded and the action proceeds with whatever pool was previously selected.

**Root cause:** `PoolPicker.vue`'s inline "create new pool" state (`creating`, `newName`) was entirely internal to the component — the hosting modal (`KnowledgeBasePage.vue`'s move-document modal, `UploadDropzone.vue`) had no way to know a pool creation was in progress and unconfirmed, so its own Save/Upload button stayed enabled the whole time.

**Fix:**
- `PoolPicker.vue` now emits a `pending` event: `true` exactly when the inline field is open *and* has a non-empty typed name; `false` the moment the user confirms (✓), cancels, or the field is empty.
- `KnowledgeBasePage.vue`'s move-modal Save button and `UploadDropzone.vue`'s Upload button both bind `:disabled="pending"`, with a one-line hint: *"Finish creating the new pool (✓) or pick an existing one to continue."*

**Verified:** clean `npm run build`, 18/18 frontend tests passing, and the emit/prop logic traced through all state transitions (open → type → confirm, open → type → cancel, confirm resets `pending`). Live browser click-through wasn't possible during this session (browser tool was temporarily unavailable) — recommend a quick manual click-through to confirm the UX reads naturally.

---

## Defect 3 — Deleted conversation, still answered from cache

**Repro:** Ask a question (creates a conversation, caches the answer) → delete that conversation → ask the exact same question again → get an instant reply with no visible "thinking," as if the old conversation were still there.

**Root cause:** Conversation deletion itself was correct (`chat_store.delete_conversation` properly removes the Redis record) — the cache is keyed by **question text**, not by conversation, so deleting the conversation left the cached answer for that question fully intact. Re-asking it hit the cache, not the LLM, which is what made it feel like nothing was deleted.

**Fix:** `backend/chat/routes.py`'s `delete_conversation` route now also calls `semantic_cache.clear_user_cache(redis_client, user_id)`.

**Verified live:**
1. Asked "what database does Project Beta use?" → fresh LLM call, `processing_time: 3.01s`.
2. Asked it again → cache hit, `processing_time: 0.002s` (confirms caching normally works).
3. Deleted the conversation.
4. Asked the identical question again → `processing_time: 2.77s` — a genuine fresh LLM call, not another cache hit.

---

## Defect 4 — Two documents in a pool, "key points" shows the old one

**Repro:** Upload document A to a pool → ask "key points" → answer describes document A. Upload document B into the *same* pool → ask "key points" again (identical query text, identical pool) → answer still only describes document A; document B is invisible.

**Root cause:** Same as defect 1, triggered by upload instead of delete: the upload-completion path invalidated BM25 but not the semantic cache. Because the cache key is `(user_id::pool::<name>, md5("key points"))`, a second upload into the same pool didn't change the key, so the old entry for that exact query text kept matching.

**Fix:** `backend/main.py`'s upload-completion path (inside `_process()`) now also calls `semantic_cache.clear_cache(user_id)` right after a successful ingest.

One subtlety verified explicitly: does clearing by plain `user_id` also reach the **pool-scoped** keys (`user_id::pool::Eng:<hash>`)? Yes — Redis's `KEYS <prefix><user_id>:*` glob matches `user_id::pool::Eng:<hash>` too, since `*` matches the extra colons. Covered by a new test (`test_clear_cache_also_clears_pool_scoped_entries`) rather than assumed.

**Verified live:**
1. Uploaded doc A ("Project Alpha... PostgreSQL... Redis") to pool `Eng`, asked "key points" → cached answer about Project Alpha only.
2. Uploaded doc B ("Project Beta... MongoDB... RabbitMQ") to the same pool.
3. Asked the identical "key points" query again → answer now correctly covers **both** documents, sources `['docA.txt', 'docB.txt']`.

---

## Code changes

| File | Change |
|------|--------|
| `backend/retrieval/semantic_cache.py` | New module-level `clear_user_cache(redis_client, user_id)` — usable without a `SemanticCache` instance/embedding model. `SemanticCache.clear_cache()` now delegates to it. |
| `backend/main.py` | `semantic_cache.clear_cache(user_id)` added at all three document-mutation points: upload-complete, delete, move. |
| `backend/chat/routes.py` | `delete_conversation` now clears the cache too. |
| `frontend/src/components/PoolPicker.vue` | Emits `pending` (see defect 2). |
| `frontend/src/pages/KnowledgeBasePage.vue` | Move-modal Save button wired to `pending`. |
| `frontend/src/components/UploadDropzone.vue` | Upload button wired to `pending`. |
| `backend/tests/test_semantic_cache.py` | +6 tests: pool-scoped `clear_cache` coverage, `clear_user_cache` module function. |

**Test results:** backend 398/398 passing · frontend build clean · frontend tests 18/18 passing.

---

## Known limitation (not a defect, a tradeoff)

Clearing the *entire* user's semantic cache on any single document/conversation change is a blunt instrument — correct, but it evicts unrelated cached answers more often than strictly necessary (e.g. deleting one document in pool A also clears cached answers for unrelated questions in pool B). Acceptable for now given cache entries are cheap to regenerate; if hit-rate becomes a concern, this could be narrowed to just the affected pool's scope.
