# Vaultly — Task & Progress Tracker

**Purpose**: the authoritative, up-to-date pending-work list. `plan.md` (2026-07-22) has drifted significantly stale — a lot of what it still marks `[ ]` was completed in the sessions since. This file supersedes it going forward; `plan.md`'s still-open items are folded in below with corrected status. `SECURITY.md` and `defect.md` remain the detailed record for their respective audits — this file tracks and links to them rather than duplicating their full content.

**Status key**: `[x]` done & verified · `[ ]` not started · `[~]` partially done (see note)

> **Current priority (2026-07-24): mobile-first launch.** Web/backend work (§1's new features, §3 reliability items) is on hold unless it's a shared-backend blocker for mobile. Everything mobile-launch-related should be pulled to the top of this file as it's scoped.

---

## 0. What's already shipped (context, not action items)

Condensed so this doc is self-orienting without re-reading the whole history:

- **Auth**: username+email login, username uniqueness, idle-session timeout (non-dismissible-by-accident popup), self-service account deletion, JWT session revocation on logout (Redis blacklist), Google OAuth.
- **Chat**: pool-selection popup, conversational memory, server-side conversation persistence (list/rename/delete/resume), per-plan conversation caps, Markdown rendering, source-document-name display (not full passage dumps), admin-only timing indicator, Qwen3 `/think` `/no_think` hybrid-thinking wiring.
- **Billing**: Free/Pro/Max/Customize tiers defined and enforced (storage, AI-question quota, conversation caps, webhooks gate, priority-processing flag), contact-lead capture, mobile `BillingScreen.tsx` matches backend plans (no more stale USD data).
- **Knowledge Base**: pool creation flow, document upload with real per-phase progress + image/OCR support, move/delete documents.
- **Mobile**: full parity pass (auth, chat/pools/markdown/sources, upload progress, admin panel) + Expo SDK 51→54 upgrade.
- **Admin panel**: web + newly-built mobile version — stats, settings, user management (quota/admin-toggle/active-toggle/delete).
- **Security**: full 5-check audit (`SECURITY.md`) — both Highs fixed (Redis auth+lockdown, auth rate limiting), all 7 Lows fixed (Swagger gating, reset-token TTL, logout revocation, self-service deletion, no more logged admin passwords, quieter OAuth error logs, untracked `mcp/node_modules`), and all 6 Mediums fixed (Secure cookie, webhook SSRF guard, upload path-traversal sanitization, no more leaked exception text, HTTP security headers, OAuth state CSRF check — see §4 for verification detail).
- **Defects**: 4 reported bugs fixed and verified live — stale semantic cache after document delete/upload, stale cache after conversation delete, pool-creation Save button race (see `defect.md`).

---

## 1. New features — planned in full, not yet built

Specs below are locked from planning discussion; nothing in this section has any code written yet.

### 1a. Interactive Knowledge Graph
- [ ] NER/topic extraction: **LLM-based**, decoupled from the upload-blocking path (upload still completes fast; extraction runs as a background pass afterward)
- [ ] Graph storage in Redis: nodes + edges, each tracking which document(s) back them (source-list per node/edge)
- [ ] **Delete handling ("correct" version, locked)**: deleting a document removes it from every node/edge's source list; a node/edge with an empty source list is deleted entirely; still-supported nodes/edges are untouched
- [ ] **Backfill: none** — only documents uploaded *after* this ships get graph data; existing documents don't retroactively get processed
- [ ] **Platform: web + mobile from day one** (mobile via WebView embedding the same D3 view, per the original blueprint)
- [ ] New API: `GET /pools/{pool}/graph` → `{nodes, edges}`
- [ ] Web UI: D3.js force-directed graph — "Highlight Concept" selector, "Node Repulsion Force" slider (matches the provided mockups)
- [ ] **Plan gating**: visible in Free but faded/locked — tapping it prompts an upgrade, doesn't open. Full access on Pro/Max.

### 1b. Podcast Mode
- [ ] Summarizer prompt (new system prompt variant in `grounding.py`, reuses existing `generation/llm.py` pipeline)
- [ ] TTS: **xtts-api-server** (OpenAI-compatible `/v1/audio/speech`-shaped), config mirrors `LLM_*` pattern (`TTS_ENABLED`, `TTS_API_BASE`, `TTS_API_KEY`, `TTS_VOICE`)
- [ ] **v1 scope, locked simple**: audio generated and streamed directly to the client in one request — **never written to a persistent file server-side** (so "delete on listen/discard" is satisfied for free — nothing is ever stored to delete)
- [ ] **Cut for v1**: no lock-screen/background playback (foreground-only), no custom speed/skip controls (basic play/pause/seek only), no "Add to Canvas" (undefined concept, scope out until "Canvas" gets its own design pass)
- [ ] **Plan gating**: Free 1/day · Pro 3/day · Max 5/day — needs a `PODCAST_DAILY_LIMIT` config set per plan (same pattern as `FREE_AI_QUESTIONS_PER_DAY` etc.)

### 1c. Proactive Insights Feed
- [ ] **Simplified scope (locked)**: no external data fetching at all — only surfaces insights from the user's own existing pool content. Removes the entire "connectors + external evaluation agent" complexity from the original blueprint.
- [ ] Scheduler: simple daily loop (same in-process pattern already used for `local_llm.ensure_loaded()`), not precise cron — "roughly once a day" is fine
- [ ] **One LLM call**, not a two-step find+score pipeline: ask the LLM directly for one insight, telling it what was already shown yesterday so it doesn't repeat
- [ ] "Don't repeat" tracking: remember only the **last** insight shown per user (single Redis value, overwritten daily) — not a growing history
- [ ] No deep-linked pre-populated chat for v1 — show the insight text directly (notification or a simple screen)
- [ ] Push notifications: `expo-notifications` + Expo's push service (abstracts APNs/FCM) + new device-token storage — **net-new infra, nothing like this exists yet**
- [ ] **Plan gating (confirmed)**: Free 1 insight/day · Pro 2/day · Max 2/day — Pro = Max is intentional. All three numbers to be env-configurable later (same `FREE_*`/`PRO_*`/`MAX_*` pattern as the existing AI-question quota), not hardcoded.

### 1d. Document list with AI summaries — **FIXED**
- [x] Backend: `generation/grounding.py::build_summary_prompt()` (new one-shot prompt, forces `/no_think`) + `generation/pipeline.py::summarize_document()` (drains `generate_stream` into a string, same pattern as `stream_answer`) + `ingestion/pipeline.py::update_document_summary()` (read-modify-write on the Redis blob + JSON backup, mirrors `move_document`'s re-serialize). `summary` field added to `_store_in_redis`/`_save_json_backup`/`list_documents`/`_doc_meta`.
- [x] **Timing**: generated **after** ingestion is already marked complete, inside `main.py`'s `_process()` background task — wrapped in its own try/except so a slow/failed LLM call never retroactively fails an otherwise-successful upload. Runs via `run_coroutine_threadsafe` back onto the request's own event loop (not a second `asyncio.run()` loop in the worker thread) — needed because the embedded-LLM backend's `asyncio.Lock` binds to whichever loop first acquires it.
- [x] Web: `DocumentCard.vue` renders `document.summary` (line-clamped). Mobile: `DocumentRow.tsx` renders `doc.summary`, `Doc` interface updated.
- [x] 14 new tests (`test_grounding.py`, `test_ai_pipeline.py`, `test_pipeline.py`) + full suite (434 passed) + live end-to-end verification against a rebuilt Docker stack: uploaded a real refund-policy .txt, confirmed an accurate 3-sentence summary appeared in `GET /documents` ~20s after upload, no errors in logs.
- [ ] **Not yet visually verified in-browser** — the in-app browser tool was unavailable for this whole session; verified via direct API responses and manual template review instead. Do a real visual pass next time the browser tool is back.

### 1e. MCP/API token template section — **FIXED (web)**
- [x] **Gap found and fixed**: the curl/MCP examples only existed inside the show-once token-reveal modal — closing it lost them entirely, unlike `WebhookManager.vue`'s always-available collapsible template section. Added a matching persistent "API / MCP setup template" section to `TokenManager.vue` using a `YOUR_TOKEN` placeholder, so the format is always there to reference even without a live token in hand.
- [ ] **Mobile: not built at all.** There is no Integrations screen on mobile (`mobile/src/screens/`) — no token management, no webhook management. **Sequencing decided 2026-07-24: deferred to the end of the build order**, after the 3 headline mobile-launch features (Knowledge Graph §1a, Podcast Mode §1b, Insights Feed §1c) and Document summaries (§1d).

### 1f. Unlimited MCP/API tokens as an explicit plan detail — **FIXED**
- [x] Confirmed no token-count cap anywhere in the backend. `featureList()` in both `BillingPage.vue` and mobile's `BillingScreen.tsx` now renders "Unlimited API/MCP tokens" (was the vaguer "API token access") whenever a plan's `api_tokens` flag is set — true for every tier today. `billing/plans.py`'s docstring updated to state it explicitly too.

### 1g. Customize plan card — simplified display — **FIXED**
- [x] `BillingPage.vue` and mobile `BillingScreen.tsx`: the Customize card no longer renders the per-plan feature checklist or the "/ period" price suffix — just the plan name/Enterprise badge, the word **"Custom"**, and the **"Contact us"** button.

### 1h. New "Team/Org" plan tier — restructuring — **DESCOPED (2026-07-24)**

> Deliberately dropped from the mobile-launch push (per the 2026-07-24 mobile-first pivot, see top of file). Pricing/tier details below are kept for whenever this gets picked back up, not acted on now.

- [ ] **Remove** "Team members / sharing (up to 5)" from the **Max** plan
- [ ] **New plan tier** (name TBD — "Team Sharing" / "Org-wide" / other, not finalized): team sharing functionality, capped at **50 members per user**, priced **₹120/month · ₹1100/year**
- [ ] **Rest of the new plan's feature row (storage, AI-quota/day, webhooks, priority-processing) — deliberately left undecided.** Noted here only as a placeholder; will be discussed and filled in later, not blocking other work in the meantime.
- [ ] **Annual-discount badge (confirmed)**: shows on **all three** paid plans with annual pricing — Pro, Max, and the new Team/Org plan (Free is ₹0, no discount concept applies; Customize has no fixed price). Existing Pro/Max monthly/annual toggle already works, just needs the "save X%" badge added.
- [ ] Updated 5-tier matrix (storage/AI-quota columns intentionally TBD for the new tier — see above):

  | | Free | Pro | Max | **New (Team/Org)** | Customize |
  |---|---|---|---|---|---|
  | Team sharing | — | — | ~~5~~ *(removed)* | 50/user | Custom |
  | Price/mo | ₹0 | ₹59 *(discount badge)* | ₹79 *(discount badge)* | ₹120 *(discount badge)* | Contact us |
  | Price/yr | ₹0 | ₹600 | ₹800 | ₹1100 | Contact us |

---

## 2. Bug — LLM keeps processing after user navigates away — **FIXED**

- [x] **Confirmed root cause**: both LLM backends (`generation/llm.py`) run their actual generation call — a blocking HTTP read loop for `OpenAICompatibleLLM`, `llama.cpp`'s stream for `EmbeddedLLM` — in a background thread via `run_in_executor`. That thread had no way to know the client disconnected, so it kept pulling tokens (and the external inference server kept generating) for an answer nobody would ever receive.
- [x] **Fix**: both backends now hold a `threading.Event` (`cancel_event`) checked on every loop iteration in the background thread; it's set in a `finally` block wrapping the consumer side, which runs on both normal completion and on early teardown (`GeneratorExit`, when the caller stops iterating). For the `openai` backend specifically, the underlying `requests.Response` is also explicitly `.close()`d — the only thing that actually tells the *external* inference server to stop generating, not just us to stop reading.
- [x] `main.py::query_stream` explicitly checks `request.is_disconnected()` before each yield and calls `agen.aclose()` in a `finally` block, propagating cancellation down through `stream_answer` into the LLM backend.
- [x] Verified: 6 new unit tests (both backends, using an infinite fake token source — would hang past a 5s timeout if the fix regressed) + a live end-to-end test against the real Docker stack (killed a real streaming connection mid-answer, confirmed via logs that the cleanup chain fires and the background thread actually stops). Full suite: 402/402 passing.

---

## 3. Reliability & scaling — still open (from `plan.md` §C)

- [ ] **BM25 cache staleness across multiple backend workers** — `invalidate_bm25()` only clears the calling worker's in-memory index; breaks the moment you run >1 replica. Directly relevant now: the Proactive Insights Feed scheduler (§1c) will have the same multi-replica problem (needs a leader lock) if the app scales past one worker before that ships.
- [ ] Replace `KEYS` scans on hot paths with maintained index sets or `SCAN` — note: the new `clear_user_cache()` helper added this session (for the cache-invalidation defect fixes) also uses `KEYS`, consistent with the existing pattern but not yet addressed by this item.
- [~] Rate limiting — **auth endpoints done** (login/signup/password-reset, see `SECURITY.md` H2). Query/chat endpoints still unprotected from abuse.
- [ ] Observability: structured logging, error tracking, metrics
- [ ] Vector index silently disappearing with no self-heal (`/health` doesn't verify `idx:chunks` exists; `knn_search()` doesn't detect+recreate on "no such index")

## 4. Security — Medium findings (`SECURITY.md`) — **all 6 fixed**

| # | Finding | Fix |
|---|---|---|
| M1 | Session cookie missing `Secure` flag | ✅ `SESSION_COOKIE_SECURE` (default `True`) passed to `_set_session_cookie` |
| M2 | SSRF via user-registered webhook URLs | ✅ `utils/url_safety.py` blocks internal/loopback/link-local/metadata ranges at registration + delivery |
| M3 | Path traversal via unsanitised upload `file.filename` | ✅ `_sanitize_filename()` strips directory components via `os.path.basename()` |
| M4 | Internal exception text leaked to clients | ✅ `_internal_error()` helper — generic message + correlation ID to client, full detail logged server-side only |
| M5 | No HTTP security headers | ✅ middleware sets HSTS, CSP, X-Frame-Options, nosniff |
| M6 | OAuth `state` generated but never verified on callback | ✅ server-issued single-use Redis-backed state, verified on every callback |

Verified: full backend suite (417 passing, 3 unrelated pre-existing pro-tier quota test failures unrelated to this work) + live against a rebuilt Docker stack (see `SECURITY.md` "Verification" section for the exact checks run for each). Committed and pushed.

Plus: email verification on signup (`plan.md` §D) — still not implemented.

## 5. Everything else still open (carried from `plan.md`, condensed)

**Billing/SaaS**
- [ ] Real payment processor (Stripe/Razorpay) replacing the billing stub
- [ ] Audit log (who uploaded/deleted/moved what, admin actions)
- [ ] Data **export** (account deletion is done — see §0 — export is not)
- [ ] Usage analytics dashboard for admins

**Chat**
- [ ] Citation click-to-preview
- [ ] Answer feedback (👍/👎)

**Knowledge Base**
- [ ] Multi-file upload with per-file progress queue
- [ ] Bulk select → move/delete
- [ ] Search/filter documents by name/pool/type/date
- [ ] Nested pools or tags
- [ ] Re-process a document after an embedding-model change

**Retrieval/AI quality**
- [ ] Table-aware PDF parsing
- [ ] Semantic chunking (vs. fixed-character)
- [ ] Eval harness — golden-questions regression suite

**UI polish**
- [ ] Motion/animation pass (page transitions, message entrance, hover states, skeleton loaders) — no work started

---

## Open questions needing your decision

~~1. Proactive Insights Feed Pro/Max~~ — confirmed intentional, env-configurable later.
~~2. Annual-discount badge scope~~ — confirmed, all three paid plans.
~~3. Document-summary timing~~ — decided, upload-time background pass.
~~4. LLM-keeps-running bug~~ — confirmed (silent wasted compute) and fixed, see §2.

Still open:

1. **Team/Org plan** — final name, and the rest of its feature row (storage/AI-quota/webhooks/priority-processing). Deliberately deferred — not blocking other work.
