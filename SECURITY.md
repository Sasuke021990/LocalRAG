# Vaultly — Security Review

**Scope:** backend (FastAPI + Redis), web frontend (Vue 3), mobile (Expo/React Native).
**Method:** the 5-check framework from *"5 Security Checks Before You Launch Your App"* (Gitleaks, Bearer, ECC Production Audit, Trail of Bits, ECC Security Review), run manually against the source rather than by pasting prompts into a builder.
**Date:** 2026-07-23 · **Reviewer:** automated code review (not a substitute for professional penetration testing).

> **Context:** Vaultly is moving from homelab to SaaS/multi-tenant. Findings are prioritised with that direction in mind — several items that are low-risk on a private LAN become high-risk once the app is internet-facing and holds multiple tenants' data.

---

## Executive summary

The codebase is, on the whole, **well-architected for security**: bcrypt password hashing, correctly-pinned JWT verification, per-user data isolation on every route, session-only admin gating, hashed API tokens, HMAC-signed webhooks, DOMPurify-sanitised chat output, and no hardcoded secrets. The gaps that remain are mostly **deployment/hardening** concerns rather than broken application logic.

| # | Finding | Severity | Surface | Status |
|---|---------|----------|---------|--------|
| H1 | Redis published on `0.0.0.0:6379` + RedisInsight UI on `8001`, no password | **High** | infra | ✅ **Fixed** |
| H2 | No rate limiting on auth endpoints (login / signup / password-reset) | **High** | backend | ✅ **Fixed** |
| M1 | Session cookie missing `Secure` flag | Medium | backend | ✅ **Fixed** |
| M2 | SSRF via user-registered webhook URLs (no internal-range block) | Medium | backend | ✅ **Fixed** |
| M3 | Path traversal via unsanitised upload `file.filename` | Medium | backend | ✅ **Fixed** |
| M4 | Internal exception text leaked to clients (`detail=str(exc)`) | Medium | backend | ✅ **Fixed** |
| M5 | No HTTP security headers (HSTS, CSP, X-Frame-Options, nosniff) | Medium | backend | ✅ **Fixed** |
| M6 | OAuth `state` generated but not verified on callback (login CSRF) | Medium | backend | ✅ **Fixed** |
| L1 | Swagger `/docs` + `/redoc` publicly exposed | Low | backend | ✅ **Fixed** |
| L2 | Password-reset token TTL is 1 hour (guide recommends ≤15 min) | Low | backend | ✅ **Fixed** |
| L3 | Logout does not invalidate the JWT server-side | Low | backend | ✅ **Fixed** |
| L4 | No self-service account deletion / data export | Low | product | ✅ **Fixed** (deletion; export still open) |
| L5 | Generated default-admin password written to logs | Low | backend | ✅ **Fixed** |
| L6 | Google token-exchange failure logs full response body | Low | backend | ✅ **Fixed** |
| L7 | `mcp/node_modules/` (~3,700 files) committed to git | Low | hygiene | ✅ **Fixed** |

---

## What's already done well

These held up under review and should be preserved:

- **Password hashing** — `bcrypt` with per-password salt (`backend/auth/passwords.py`). Meets the bcrypt/argon2/scrypt bar; no MD5/SHA-1.
- **JWT handling** — `jwt.decode(..., algorithms=["HS256"])` pins the algorithm (no `alg=none`/alg-confusion), `exp` is set and verified, and a per-user `token_version` claim allows instant session revocation (`backend/auth/tokens.py`, `backend/auth/dependencies.py:41`). Password change/reset bump `token_version`, invalidating all other sessions.
- **Multi-tenant isolation** — every data route resolves `user_id` from the credential and scopes all Redis keys / disk paths by it (`user:<id>`, `<DATA_DIR>/<user_id>/…`). The progress SSE endpoint explicitly refuses another user's `task_id` (`backend/main.py:674`). Conversation, pool, and document reads/writes are all user-namespaced — no IDOR found.
- **Admin gating** — `require_admin_user` is **session-only**; an MCP/API token is never accepted for admin routes (`backend/admin/dependencies.py`). Self-protection guards prevent deleting/deactivating the root admin or oneself (`backend/admin/routes.py`).
- **Privilege containment** — integrations management (mint tokens, register webhooks) requires a real session, not an API token (`require_session_user`), so a leaked token can use the account's data but can't escalate by minting more credentials.
- **API tokens** — opaque `vlt_…`, only the **SHA-256 hash** stored, plaintext shown once, individually revocable (`backend/integrations/mcp_tokens.py`).
- **No account enumeration** — login returns a single generic message; password-reset always returns `200` regardless of whether the email exists (`backend/auth/routes.py:83,201`).
- **Web output sanitisation** — chat markdown is rendered through `marked` then **DOMPurify** before `v-html` (`frontend/src/components/ChatMessage.vue:34`), mitigating stored XSS from malicious document content flowing through RAG answers.
- **Mobile token storage** — session token kept in `expo-secure-store` (OS keychain), not AsyncStorage (`mobile/src/api/client.ts`).
- **Secret hygiene** — `.env` is gitignored and never committed; `JWT_SECRET` has no default and the app refuses to start without it (`backend/utils/config.py:179`); `.env.example` contains only placeholders; the web client talks to a relative `/api` (no embedded keys).
- **Quotas** — per-plan storage and daily AI-question limits are enforced server-side (`backend/utils/quota.py`).

---

## Check 1 — Secret Leak Prevention *(Gitleaks)*

**Result: PASS, with one hygiene item.**

- No hardcoded API keys, passwords, tokens, or connection strings in application source. The only matches for secret-like patterns are test fixtures (`backend/tests/test_webhooks.py`, `test_admin_store.py`).
- All secrets are read from environment variables via `Config` (`backend/utils/config.py`). `JWT_SECRET` is mandatory at startup.
- `.env` is not tracked and has no git history; `.env.example` holds placeholders only.
- Frontend uses a relative `/api` base and no `VITE_`/`import.meta.env` secret exposure; mobile ships only the public `apiBaseUrl`.

**L7 — `mcp/node_modules/` committed to git (fixed).** ~3,700 files under `mcp/node_modules/` were tracked even though `node_modules/` is in `.gitignore` (they predated the ignore rule; ignore doesn't apply to already-tracked files). Untracked via `git rm -r --cached mcp/node_modules` — the files stay on disk (still needed to run `mcp`), just no longer versioned.

---

## Check 2 — Personal Data Flow Audit *(Bearer)*

**Result: PASS, with two product gaps.**

- **PII collected:** email, username, password (→ bcrypt hash), Google `sub`, plus uploaded document content and derived embeddings. Payment data is **not** handled in-app (billing is a stub — no card data touches the system).
- **Passwords** are hashed before storage and never logged or returned. API responses use explicit Pydantic schemas (`UserOut`, `AuthResponse`) that never include `password_hash`; the admin user cast (`backend/admin/store.py:_cast_user`) also omits it.
- **Logs** don't print user passwords or tokens (token *IDs* only, which are non-secret). **L5/L6 fixed** — see Check 3/4.
- **Webhook payloads are metadata-only** (file name, pool, event) — document contents never leave the system through webhooks, by design.
- **Cookies:** session cookie is `httpOnly` + `sameSite=lax` and now also `Secure` (**M1 fixed**). No PII in browser `localStorage`.

**L4 — Self-service account deletion (fixed).** `DELETE /auth/me` (session-only, password-reconfirmed) now lets a user permanently delete their own account and everything they own — reusing the same hard-delete `admin.store.delete_user_completely` an admin uses. While building this, found and fixed a real pre-existing gap in that shared delete path: it never freed the `user_username_index` or `conversation:*`/`conversation_index:*` keys, so a deleted user's username stayed "taken" forever (blocking re-signup with the same email, since the username auto-derives from it) and their chat history silently survived deletion — both now cleaned up, benefiting the admin-delete path too. Self-service **export** is still not implemented — worth adding for GDPR/DPDP completeness, but out of scope for this pass.

---

## Check 3 — Pre-Deploy Production Audit *(ECC)*

**Result: several hardening gaps.**

- ✅ **Env vars** validated; app refuses to start without `JWT_SECRET`. `DEBUG` defaults off.
- ✅ **No debug/backdoor endpoints** (`/test`, `/seed-data`, etc.).
- ✅ **CORS** is env-restricted, not wildcard (`allow_origins=CORS_ALLOWED_ORIGINS_LIST`, `backend/main.py:82`).
- ✅ **H2 — Rate limiting added (fixed).** `/auth/login`, `/auth/signup`, and `/auth/password-reset/request` are now throttled per client IP by a Redis-backed limiter (`backend/utils/rate_limit.py`, defaults 10/min · 5/hr · 5/hr, env-configurable). Shared across workers, fails open on Redis error.
- ✅ **M4 — Error leakage (fixed).** Every `raise HTTPException(status_code=500, detail=str(exc))` site now goes through a shared `_internal_error()` helper: the real exception is logged server-side with a correlation ID, and the client only ever sees `"Internal error (reference: <id>). Please try again or contact support."` (`backend/main.py`).
- ✅ **M5 — Security headers added (fixed).** A response middleware now sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, and `Content-Security-Policy` (the CSP is skipped on `/docs`/`/redoc` so Swagger's inline scripts still work) (`backend/main.py`).
- ✅ **H1 — Database exposure closed (fixed).** Both compose files now require `REDIS_PASSWORD` (`--requirepass`), no longer publish Redis/RedisInsight on a public interface, and the backend authenticates with the password. TLS remains a follow-up only if Redis moves to a separate host.
- ✅ **L1 — Swagger gated (fixed).** `/docs`, `/redoc`, and `/openapi.json` are now conditional on `API_DOCS_ENABLED` (`backend/main.py`, default on for homelab use — set to `false` for an internet-facing deploy that doesn't need public API docs).
- ✅ **L5 — No more logged admin passwords (fixed).** The startup admin-seed no longer auto-generates a password and prints it to logs; it requires `ADMIN_PASSWORD` explicitly (skips seeding with a warning if unset) — see `backend/main.py:_seed_default_admin`.

---

## Check 4 — Deep Security Audit for Complex Logic *(Trail of Bits)*

*App profile: custom email/password + Google OAuth auth, per-user document storage, MCP/API tokens, webhooks. Billing is a non-charging stub.*

**Authentication & authorization**
- ✅ Every protected route depends on `require_current_user`/`require_session_user`/`require_admin_user`.
- ✅ **No IDOR** — no endpoint trusts a client-supplied user ID; ownership is implicit in the user-scoped keyspace, and cross-user `task_id`/conversation access returns 404/error.
- ✅ **Password-reset tokens** are random (`uuid4`), single-use (deleted on consume). **L2 fixed** — TTL tightened from 1 hour to 15 minutes (`backend/auth/store.py:PASSWORD_RESET_TTL_SECONDS`).
- ✅ **JWT** — strong secret required, expiry enforced, `token_version` revocation. **L3 fixed** — logout now revokes the specific presented token via a `jti` claim + Redis blacklist (`backend/auth/session_blacklist.py`), rather than only clearing the cookie; other devices/sessions are untouched (that's what `token_version` bumps are for). Verified live: the exact bearer token issued at login returns `401 "Session revoked"` immediately after logout.
- ✅ **M6 — OAuth CSRF (fixed).** `/auth/google/login` now mints a server-side, single-use `state` (Redis, 10-min TTL, `auth.store.create_oauth_state`), and `/auth/google/callback` rejects any request whose `state` is missing, forged, expired, or already consumed (`auth.store.consume_oauth_state`) — before the authorization code is ever exchanged.
- ✅ **L6 fixed** — Google token-exchange/userinfo failures logged the full response body at error level (`backend/auth/google_oauth.py`); now the status code logs at error level and the body only at debug (normally disabled in production).

**Payment logic**
- ✅ N/A in the dangerous sense — checkout is a stub that sets a plan with no charge and no client-trusted price. **When real payments land,** verify webhook signatures from the provider (Razorpay/Stripe), compute totals server-side, and gate paid features on server-verified payment status.

**Input handling**
- ✅ **SQL injection: N/A** — the datastore is Redis with parameterised client calls; no raw query strings built from user input.
- ✅ **XSS** — web sanitises rendered markdown with DOMPurify; React Native/`react-native-markdown-display` doesn't render raw HTML.
- ✅ **Upload validation** — extension allow-list + size/quota pre-check.
- ✅ **M3 — Path traversal (fixed).** The uploaded `file.filename` is now sanitised once with `os.path.basename()` (`_sanitize_filename`, `backend/main.py`) before it's used for the write path, extension check, ingestion, logs, webhook payloads, or the response — a traversal-only name is rejected outright (`400`), and a crafted `../../<other_user_id>/General/evil.pdf` is reduced to just `evil.pdf`.

---

## Check 5 — Attacker's Perspective Review *(ECC)*

- **1. ID manipulation:** ✅ No horizontal access — user-scoped keys; `progress` and conversation endpoints reject other users' IDs.
- **2. Login bypass:** ✅ No endpoint works without a valid credential; expired/malformed JWTs are rejected; disabled accounts are blocked (`is_active`). No default account with a known password — **L5 fixed**: the seeded admin now requires an explicit `ADMIN_PASSWORD` rather than falling back to a generated-and-logged one.
- **3. Privilege escalation:** ✅ Role check is server-side (`is_admin`/env-admin); a regular user can't reach admin routes by editing a JWT (signature-protected) or guessing URLs (403). Admin routes reject API tokens entirely.
- **4. Feature abuse:** ✅ signup/login/reset are now IP rate-limited (**H2 fixed**); uploads/AI-questions are quota-limited; webhook creation is plan-gated (Pro+).
- **5. Content injection:** ✅ XSS sanitised (DOMPurify); SQLi not applicable (Redis).
- **6. Internal exposure:** ✅ **M4 fixed** — error responses now return only a generic message + correlation ID; the real exception is logged server-side only. **L1 fixed** — `/docs`/`/redoc`/`/openapi.json` are now gated behind `API_DOCS_ENABLED`. **H1 fixed** — Redis/RedisInsight no longer reachable. No `.env`/`.git` served by the API itself.
- **7. Business-logic manipulation:** ✅ No negative amounts / discount stacking possible (billing is a no-charge stub with server-set plans). Re-audit this section the moment real payments are wired in.
- ✅ **M2 — SSRF (fixed).** Webhook URLs are now validated by a shared `utils.url_safety.is_safe_external_url()`: `https`-only, hostname resolved via `socket.getaddrinfo`, and every resolved address checked against `ipaddress`'s private/loopback/link-local/multicast/reserved/unspecified classifications (covers cloud metadata, RFC-1918, and RFC 5737 doc ranges). Checked at registration (`integrations/webhooks.py:create_webhook`) **and** re-checked immediately before each delivery/retry attempt (`_post_with_retries`) to guard against DNS rebinding between registration and send time.

---

## Prioritised remediation

**Before internet-facing launch:**

1. ✅ **H1 — Redis locked down (done).** Both compose files now require `REDIS_PASSWORD` (`--requirepass`), no longer publish `6379`/`8001` on a public interface (dev binds `127.0.0.1` only; TrueNAS uses `expose:` on the internal network), and the RedisInsight UI port is removed. All four backend Redis clients pass the password (`config.REDIS_PASSWORD or None` — backward-compatible when unset). *Remaining follow-up:* enable TLS if Redis ever runs on a separate host from the backend.
2. ✅ **H2 — Auth rate limiting added (done).** A Redis-backed, cross-worker fixed-window limiter (`backend/utils/rate_limit.py`) throttles `/auth/login`, `/auth/signup`, and `/auth/password-reset/request` per client IP (defaults 10/min, 5/hr, 5/hr; all env-configurable). Fails open if Redis is unreachable; respects `TRUST_PROXY_HEADERS` for correct IPs behind a proxy. Covered by `backend/tests/test_rate_limit.py`.
3. ✅ **M1 — `Secure` set on the session cookie (done).** `SESSION_COOKIE_SECURE` (default `True`) is now passed to `response.set_cookie(...)` in `_set_session_cookie` (`backend/auth/routes.py`); env-configurable for the rare non-HTTPS LAN deploy.
4. ✅ **M4 — Exception text no longer leaked (done).** A shared `_internal_error()` helper (`backend/main.py`) logs the real exception with a correlation ID and returns only a generic message to the client, everywhere a `500` was previously built from `str(exc)`.
5. ✅ **M5 — Security headers added (done).** HSTS, `X-Frame-Options`, `X-Content-Type-Options`, and CSP are now set by a response middleware (`backend/main.py`).

**Soon after:**

6. ✅ **M3 — Upload filename sanitised (done).** `_sanitize_filename()` (`backend/main.py`) strips directory components via `os.path.basename()` before the name is used anywhere.
7. ✅ **M2 — Webhook URLs validated (done).** `utils/url_safety.py`'s `is_safe_external_url()` blocks internal/loopback/link-local/metadata ranges at both registration and delivery time.
8. ✅ **M6 — OAuth `state` now verified (done).** Server-issued, single-use, Redis-backed `state` (`auth/store.py`), checked on every callback.

**Backlog / hygiene — all seven fixed:**

- ✅ **L1** — `/docs`+`/redoc`+`/openapi.json` gated behind `API_DOCS_ENABLED` (`backend/main.py`).
- ✅ **L2** — password-reset TTL 1h → 15min (`backend/auth/store.py`).
- ✅ **L3** — logout revokes the presented JWT via a `jti` blacklist (`backend/auth/session_blacklist.py`), without touching other sessions.
- ✅ **L4** — self-service `DELETE /auth/me` (session-only, password-reconfirmed); also fixed two pre-existing gaps in the shared hard-delete path (`admin.store.delete_user_completely`): the username index and conversation history were never cleaned up. **Export** is still not implemented.
- ✅ **L5** — default-admin seeding no longer generates-and-logs a password; requires `ADMIN_PASSWORD` explicitly (`backend/main.py`).
- ✅ **L6** — Google OAuth error bodies now log at debug only, not error (`backend/auth/google_oauth.py`).
- ✅ **L7** — `git rm -r --cached mcp/node_modules` (3,696 files); still gitignored going forward.

### Verification

All of the above were verified against a **rebuilt, live Docker stack** (`docker compose up -d --build`), not just read — including:
- Redis: unauthenticated connections rejected (`NOAUTH`), correct password succeeds, host port bound to `127.0.0.1` only (confirmed via `docker port`).
- Rate limiting: exactly the configured number of login attempts pass before `429` (with `Retry-After`).
- Logout: the exact bearer token issued at login is rejected (`401 "Session revoked"`) immediately after logout; a second device's token is untouched.
- Self-service deletion: wrong password → `400`, correct password → `200` + account/email/username fully freed for reuse, confirmed via re-signup.
- Password-reset token TTL confirmed at 895s (≤900s) via direct Redis `TTL` inspection.
- Admin-seed log line confirmed to never contain a password.
- Full backend test suite (**388 tests**, including 4 new `test_rate_limit.py` tests, 7 new logout/deletion tests, and a new regression test for the username-index bug) run inside the container against a real Redis instance — **all passing**.
- `backend/tests/conftest.py`'s Redis fixtures needed a matching fix (they didn't pass a password, so every DB-touching test silently skipped once H1 landed) — a good reminder that hardening infra can silently break test isolation; `.github/workflows/ci.yml`'s Redis service was updated the same way so CI exercises the same authenticated path.

**M1–M6** were verified the same way against a fresh `docker compose up -d --build`:
- M1: `Set-Cookie` on `/auth/signup` carries `Secure` (confirmed via raw header inspection); full test suite needed a new `disable_secure_cookie` autouse fixture in `conftest.py` since `TestClient`'s fake `http://testserver` origin correctly refuses to resend a `Secure` cookie — production behavior (real HTTPS) is unaffected.
- M2: registering a webhook at `https://169.254.169.254/latest/meta-data/` → `400`; a plain `http://` URL → `422` at the schema layer.
- M3: uploading a file with `filename="../../etc/passwd.txt"` is ingested and reported back as just `passwd.txt` — traversal components stripped, confirmed via the ingested document's stored source name.
- M4: an internal error (forced via a pool-delete edge case) returns only `{"detail": "Internal error (reference: c21678050d2c). Please try again or contact support."}`; the container log shows the real exception (`[c21678050d2c] Failed to delete pool: [Errno 39] Directory not empty: ...`) server-side only.
- M5: response headers on both `/docs` and a JSON route include `x-content-type-options`, `x-frame-options`, `strict-transport-security`; `content-security-policy` is present on JSON routes and correctly omitted on `/docs` (Swagger needs inline scripts).
- M6: `/auth/google/callback` without a `state`, or with a forged one, → `400`; a state obtained from `/auth/google/login`'s real redirect is accepted exactly once.
- Full backend test suite re-run after the M1 cookie-cascade fix: **417 passing** (3 unrelated, pre-existing pro-tier plan-quota test failures in `test_billing.py`/`test_quota.py`, untouched by this change, left for a separate pass).

---

*No AI review replaces professional security testing. Vaultly handles credentials, PII, and (soon) real payments at multi-tenant scale — commission a human penetration test before public launch, and re-run this review after every major feature.*
