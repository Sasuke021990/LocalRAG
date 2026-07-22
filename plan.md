# Vaultly — Feature Roadmap

Tracking document for the next phase of work. Direction: growing this from a
solo/homelab RAG tool toward a **real multi-tenant SaaS product**.

> Supersedes the previous version of this file (vector search / auth / CI
> plan — fully implemented, see git history). Nothing below is started yet;
> this is for planning and tracking, not a commitment to build everything.

## How to read this

- Checkboxes track status: `[ ]` not started, `[x]` done.
- **Phase** tags are a first-pass priority proposal, not final — confirm/
  reorder before work begins.
  - **P1** — near-term, foundational, do first
  - **P2** — important, bigger scope, sequence after P1
  - **P3** — later / backlog
- Each epic keeps its own section so items can be picked up independently.

---

## A. Billing & SaaS foundations — P1 (plan definition) / P2 (full enforcement)

### Plan tiers (confirmed 2026-07-22 — INR pricing)

| | **Free** | **Pro** | **Max** | **Customize** |
|---|---|---|---|---|
| Storage | 1 GB | 5 GB | 15 GB | Custom — contact us |
| Pools | Unlimited | Unlimited | Unlimited | Custom |
| Hybrid search + chat | ✓ | ✓ | ✓ | ✓ |
| API tokens | ✓ | ✓ | ✓ | ✓ |
| Webhooks | — | ✓ | ✓ | ✓ |
| Priority processing | — | ✓ | ✓ | ✓ |
| Team members / sharing | — | — | Up to 5 people | Custom |
| AI questions/day | 10 | 25 | Unlimited plan-wide, capped **30/user/day** | Custom |
| Price (monthly) | ₹0 | ₹59 | ₹79 | **Contact us** |
| Price (annual) | ₹0 | ₹600 | ₹800 | **Contact us** |

- [x] Define these tiers in `backend/billing/plans.py`, replacing the current stub
- [x] Make all quota numbers configurable via env (not hardcoded):
  - `FREE_AI_QUESTIONS_PER_DAY` (default 10)
  - `PRO_AI_QUESTIONS_PER_DAY` (default 25)
  - `MAX_AI_QUESTIONS_PER_DAY_PER_USER` (default 30)
  - `FREE_STORAGE_GB` / `PRO_STORAGE_GB` / `MAX_STORAGE_GB` (1 / 5 / 15)
  - `PRO_PRICE_MONTHLY_INR` / `PRO_PRICE_ANNUAL_INR` (59 / 600)
  - `MAX_PRICE_MONTHLY_INR` / `MAX_PRICE_ANNUAL_INR` (79 / 800)
- [x] Update `BillingPage.vue` to show these tiers, in ₹ not $ (backend-driven, monthly/annual toggle) — _mobile `BillingScreen.tsx` still pending (Epic F)_
- [x] **Customize plan card**: no price shown, "Contact us" button instead of "Subscribe" — different flow (no checkout)
- [x] **Contact-us lead capture**: form (name, email, company, message) → `POST /billing/contact`; emails `ADMIN_EMAIL` (reusing SMTP) + persists the lead in Redis. _Admin-panel view of leads still pending._
- [ ] Real Stripe (or Razorpay, given INR) integration replacing the billing stub — for Free/Pro/Max only; Customize is handled manually/off-platform after contact
- [x] Enforce AI-question daily quota per plan (`utils/quota.py`: daily counter, resets daily, 429 when exceeded; `/billing/subscription` exposes usage; Billing page shows "AI answers today")
- [ ] Team workspaces: invite up to 5 people (Max plan only), shared knowledge base, roles (owner/admin/member)
- [ ] Audit log: who uploaded/deleted/moved what, admin actions
- [ ] Data export & account deletion (GDPR-style portability / right-to-be-forgotten)
- [ ] Usage analytics dashboard for admins (queries/day, storage trends, active users)

**Feature-gating discipline (explicit requirement):** Free must expose *only*
what's in its row above — no silent extras. Same for Pro, Max, and Customize:
each plan gets exactly what's listed, nothing assumed. When enforcement is
built, gate every feature (webhooks, priority queue, team sharing, quota
ceilings) against the plan row, not against what's merely technically
possible.

## B. Chat experience — P1

- [x] **Pool-selection popup** — opens automatically every time the Chat page is entered (Dashboard's "Open chat" / "Ask a question", nav link), listing pools + "All pools"; dismissing without a pick defaults to "All pools" rather than trapping the user. **Replaced** the inline dropdown with a small pill in the header that reopens the same popup to switch pools mid-conversation.
- [x] **Conversational memory** — prior turns (last 3 exchanges, each truncated to 500 chars) are threaded into the prompt for both LLM backends (`grounding.trim_history`/`chat_messages`/`format_chat_prompt`), so follow-ups like "what about the express option?" resolve correctly from context. Verified end-to-end with a follow-up carrying zero topic words.
- [x] **Server-side chat history/persistence** — new `backend/chat/` module: Redis-backed conversations (sorted-set index, not a `KEYS` scan — see the reliability item below this was written to avoid), `/chat/conversations` CRUD, auto-created on the first message of a new chat. Frontend gets a resumable sidebar (`ConversationSidebar.vue`): list, open, inline rename, delete-with-confirm, "New chat".
- [x] **Saved-conversation caps per plan** — Free 5 / Pro 15 / Max 20 (env-configurable: `FREE_CONVERSATION_LIMIT`/`PRO_CONVERSATION_LIMIT`/`MAX_CONVERSATION_LIMIT`). Starting a new chat past the cap auto-deletes the least-recently-touched conversation (confirmed 2026-07-22 — no blocking/upgrade nag). Admin/operator accounts exempt (same pattern as the AI-question quota). Alongside this, stored messages no longer duplicate full retrieved-passage text (`sources`) — trimmed to file_name/pool/chunk_index/score (~70% smaller, measured), re-hydrated from the still-durable `chunk:*` data on read when a conversation is reopened.
- [ ] Citation click-to-preview — click `[1]` to see the exact source passage/doc
- [ ] Answer feedback (👍/👎) — eval signal, surfaces bad answers to admins

## C. Reliability & scaling — P1

- [ ] Fix BM25 cache staleness across multiple backend workers — `invalidate_bm25()` only clears the calling worker's in-memory index; a delete on worker A leaves worker B serving stale content. Breaks the moment you run >1 replica.
- [ ] Replace O(N) `KEYS` scans on hot paths (`list_documents`, cache stats, BM25 auto-load) with maintained index sets or `SCAN`
- [ ] Rate limiting on auth and query endpoints (currently open to abuse)
- [ ] Observability: structured logging, error tracking, metrics
- [ ] **Vector index disappears with no error, retrieval silently returns empty** — discovered 2026-07-22, root cause corrected same day: originally suspected as a Redis-restart survivability issue, but the real cause (see the CRITICAL incident item below) was the test suite's `redisearch_vector_available` fixture dropping the real `idx:chunks` index against a live Redis. That specific cause is now fixed. The **symptom** is still worth hardening against, since *something* (an operator running `FT.DROPINDEX`, a future bug, a Redis version upgrade) could still delete the index in production: retrieval then returns empty results with no error — chat looks "broken" (refuses everything) with nothing pointing at the cause unless you go looking for `KNN vector search failed: idx:chunks: no such index` in logs. `ensure_index()` only runs at backend process startup, so it doesn't self-heal mid-session. Fix ideas: have `/health` verify the index exists; or have `vector_index.knn_search()` detect "no such index" and recreate + retry once rather than silently returning `[]`.

- [x] **CRITICAL — fixed 2026-07-22: the test suite was flushing the production Redis.** `backend/tests/conftest.py`'s `redis_client` fixture calls `flushdb()` before/after every test — correct for an isolated test database, but every test run this session was executed via `docker exec <backend-container> pytest`, and that container's own `REDIS_HOST=redis`/`REDIS_PORT=6379` env vars (needed for the real app) silently pointed the fixture at the **live production Redis** instead of an isolated one. Found via the AOF log: **3,222 `FLUSHDB` commands** recorded. A second, independent bug compounded it: the `redisearch_vector_available` fixture called `vector_index.ensure_index()` (hardcoded to the real index name `idx:chunks`) then unconditionally ran `dropindex(delete_documents=True)` on it in a `finally` block — destroying real chunk data by construction, not just via the wrong env vars. Net effect: the real user account and all Redis-only data (conversations, cache) were repeatedly destroyed over the session; document *content* survived only because it's separately backed up to disk (`<DATA_DIR>/<user_id>/<pool>/*.json`, restored by `reindex_from_disk()` on backend startup) and the account itself was incidentally recreated by `_seed_default_admin()` (which reseeds `ADMIN_EMAIL` on every startup) — otherwise this would have been unrecoverable. User confirmed no relinking needed; orphaned Redis/disk data from the old account was deleted after confirmation.
  - **Fix, verified working**: `conftest.py` gained `_assert_safe_to_flush()` — inspects the connected Redis's actual data (refuses if any `user_email_index:*` key isn't an `@example.com` test address) before any destructive op. This doesn't trust environment variables at all, so it can't be fooled the same way again. Proved it by inserting a fake real-looking account and confirming the guard raised and refused to flush. The `redisearch_vector_available` fixture was rewritten to create/drop its own uniquely-prefixed throwaway index, never touching `idx:chunks`.
  - **Operational rule going forward**: never run this test suite via `docker exec` into the running backend container again. Use a separate, disposable Redis instance (e.g. `docker run --rm -d -p 16379:6379 redis/redis-stack:7.2.0-v10`) and pass `REDIS_HOST`/`REDIS_PORT` overrides explicitly — matching what CI already does correctly with its own ephemeral service container.

## D. Security hardening — P1

- [ ] Sanitize uploaded filenames — `file.filename` from a multipart upload is used directly in the file path; pool names are sanitized, filenames aren't (path-traversal risk)
- [ ] Email verification on signup (currently none)
- [ ] Brute-force protection on login/signup

## E. Knowledge Base UX — P2

- [ ] Multi-file / drag-multiple upload with a per-file progress queue (today's progress bar is single-file)
- [ ] Bulk select → move/delete
- [ ] Search/filter documents by name, pool, type, date
- [ ] Nested pools or tags (currently flat pools only)
- [ ] Re-process a document (e.g. after an embedding-model change)

## F. Mobile parity — P2

Mobile is missing everything web just got:
- [ ] Pool selector in chat (or the same entry popup as web, per B)
- [ ] Markdown rendering in chat bubbles
- [ ] Real upload progress bar (currently a spinner/toast, no phases)
- [ ] Image upload + OCR support

## G. Retrieval / AI quality — P3

- [ ] Table-aware PDF parsing (tables currently collapse to plain text)
- [ ] Semantic chunking instead of fixed-character chunking
- [ ] Eval harness — a "golden questions" regression suite so model/prompt changes don't silently degrade answer quality

## H. Account & Session — P1

- [x] **Idle session timeout with renewal popup** — `SESSION_IDLE_TIMEOUT_SECONDS` (default 60, env-configurable), exposed via `/auth/me`. Frontend tracks activity app-wide (`AppShell.vue`); idle past the timeout shows "Still there?"; unanswered for another full window → auto logout; "Continue session" resets the timer. Resolves only via its own buttons/backdrop, not incidental page activity, so it can't flicker open and vanish.
- [x] **Signup captures Username** — form requires it; API accepts it optionally (falls back to the email's local part server-side, so other API callers stay compatible); Google OAuth signup uses Google's profile name. Surfaced in the header, Dashboard greeting, and admin user list (still shows email alongside).

## I. UI Polish & Micro-interactions — P2

Requested explicitly: make the app feel more "addictive and attractive" via
motion. Candidate ideas (refine once we're ready to scope this properly):
- [ ] Page/route transition animations
- [ ] Chat message entrance animation (staggered fade/slide-in as messages arrive)
- [ ] Hover/press micro-interactions on buttons, cards, nav items
- [ ] Skeleton loaders instead of plain "Loading…" text
- [ ] Toast entrance/exit animation polish
- [ ] Extend the existing upload-milestone confetti (already in Knowledge Base) to more success moments
- [ ] Empty-state illustrations with subtle motion

## J. New ideas (open — to be filled in as we discuss)

- [ ] _(placeholder — add items here as they come up)_

---

## Open questions

1. **Customize plan scope** — what's actually configurable per customer (storage size, team size beyond 5, AI quota, support SLA)? _(Lead routing resolved: email to ADMIN_EMAIL + admin panel.)_
2. Confirm/adjust the Phase tags above — do B/C/D/H really come first, or should something else jump the queue?
3. Team workspaces (A) is a structural change (multi-user per tenant) — worth scoping as its own dedicated planning pass before starting.
4. Payment processor: Stripe doesn't natively settle in INR as smoothly as Razorpay/PayU — worth deciding before the Stripe-stub-replacement work starts.
5. Anything to add to section J from further discussion?
