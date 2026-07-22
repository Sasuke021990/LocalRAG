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

- [ ] Define these tiers in `backend/billing/plans.py`, replacing the current stub
- [ ] Make all quota numbers configurable via env (not hardcoded), e.g.:
  - `FREE_AI_QUESTIONS_PER_DAY` (default 10)
  - `PRO_AI_QUESTIONS_PER_DAY` (default 25)
  - `MAX_AI_QUESTIONS_PER_DAY_PER_USER` (default 30)
  - `FREE_STORAGE_GB` / `PRO_STORAGE_GB` / `MAX_STORAGE_GB` (1 / 5 / 15)
  - `PRO_PRICE_MONTHLY_INR` / `PRO_PRICE_ANNUAL_INR` (59 / 600)
  - `MAX_PRICE_MONTHLY_INR` / `MAX_PRICE_ANNUAL_INR` (79 / 800)
- [ ] Update `BillingPage.vue` / `PlanBadge.vue` / mobile `BillingScreen.tsx` to show these tiers, in ₹ not $
- [ ] **Customize plan card**: no price shown, "Contact us" button instead of "Subscribe" — different flow from the other three (no checkout)
- [ ] **Contact-us lead capture**: a form (name, email, company, message/needs) submitted to the backend; on submit, **email the admin** (reuse the existing SMTP setup in `auth/email_service.py`; send to `ADMIN_EMAIL`) with the lead details; leads also stored and visible in the admin panel for follow-up. Confirmed 2026-07-22: email is the required notification channel.
- [ ] Real Stripe (or Razorpay, given INR) integration replacing the billing stub — for Free/Pro/Max only; Customize is handled manually/off-platform after contact
- [ ] Enforce AI-question daily quota per plan (new counter, resets daily — separate from the existing storage quota in `utils/quota.py`)
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

- [ ] **Pool-selection popup** — clicking "open chat" / "ask a question" shows a modal listing available pools; user must pick one to continue. **Replaces** the inline pool dropdown currently in the Chat page header (confirmed 2026-07-22) — remove that dropdown once the popup lands; consider a small "change pool" affordance if users need to switch mid-conversation.
- [ ] **Conversational memory** — every question is currently answered with zero memory of prior turns in the same chat; a follow-up like "what about the express option?" has no context. Needs prior turns threaded into the grounding prompt.
- [ ] **Server-side chat history/persistence** — conversations currently live only in browser memory; a refresh loses everything. Need saved conversations, resume, rename, delete.
- [ ] Citation click-to-preview — click `[1]` to see the exact source passage/doc
- [ ] Answer feedback (👍/👎) — eval signal, surfaces bad answers to admins

## C. Reliability & scaling — P1

- [ ] Fix BM25 cache staleness across multiple backend workers — `invalidate_bm25()` only clears the calling worker's in-memory index; a delete on worker A leaves worker B serving stale content. Breaks the moment you run >1 replica.
- [ ] Replace O(N) `KEYS` scans on hot paths (`list_documents`, cache stats, BM25 auto-load) with maintained index sets or `SCAN`
- [ ] Rate limiting on auth and query endpoints (currently open to abuse)
- [ ] Observability: structured logging, error tracking, metrics

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

- [ ] **Idle session timeout with renewal popup** — after 1 minute of no activity in the app/web (configurable via env, e.g. `SESSION_IDLE_TIMEOUT_SECONDS`, default 60), show a "still there? continue session" popup. Confirm → refresh/extend the session. No response / decline → log out. Confirmed 2026-07-22: 1 minute is the real intended default, must be configurable.
- [ ] **Signup captures Username** — `SignupRequest` currently only has `email` + `password` (`backend/auth/schemas.py`); add `username`, store it (`auth/store.py` `create_user`), surface it in the UI (header, admin panel, audit log identity) instead of just email.

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
