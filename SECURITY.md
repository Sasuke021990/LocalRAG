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
| M1 | Session cookie missing `Secure` flag | Medium | backend | Open |
| M2 | SSRF via user-registered webhook URLs (no internal-range block) | Medium | backend | Open |
| M3 | Path traversal via unsanitised upload `file.filename` | Medium | backend | Open |
| M4 | Internal exception text leaked to clients (`detail=str(exc)`) | Medium | backend | Open |
| M5 | No HTTP security headers (HSTS, CSP, X-Frame-Options, nosniff) | Medium | backend | Open |
| M6 | OAuth `state` generated but not verified on callback (login CSRF) | Medium | backend | Open |
| L1 | Swagger `/docs` + `/redoc` publicly exposed | Low | backend | Open |
| L2 | Password-reset token TTL is 1 hour (guide recommends ≤15 min) | Low | backend | Open |
| L3 | Logout does not invalidate the JWT server-side | Low | backend | Open |
| L4 | No self-service account deletion / data export | Low | product | Open |
| L5 | Generated default-admin password written to logs | Low | backend | Open |
| L6 | Google token-exchange failure logs full response body | Low | backend | Open |
| L7 | `mcp/node_modules/` (~3,700 files) committed to git | Low | hygiene | Open |

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

**L7 — `mcp/node_modules/` committed to git.** ~3,700 files under `mcp/node_modules/` are tracked even though `node_modules/` is in `.gitignore` (they predate the ignore rule; ignore doesn't apply to already-tracked files). This bloats the repo and pulls third-party code into your own history/supply-chain surface.
Fix:
```bash
git rm -r --cached mcp/node_modules && git commit -m "chore: stop tracking mcp/node_modules"
```

---

## Check 2 — Personal Data Flow Audit *(Bearer)*

**Result: PASS, with two product gaps.**

- **PII collected:** email, username, password (→ bcrypt hash), Google `sub`, plus uploaded document content and derived embeddings. Payment data is **not** handled in-app (billing is a stub — no card data touches the system).
- **Passwords** are hashed before storage and never logged or returned. API responses use explicit Pydantic schemas (`UserOut`, `AuthResponse`) that never include `password_hash`; the admin user cast (`backend/admin/store.py:_cast_user`) also omits it.
- **Logs** don't print user passwords or tokens (token *IDs* only, which are non-secret). See L5/L6 for two exceptions.
- **Webhook payloads are metadata-only** (file name, pool, event) — document contents never leave the system through webhooks, by design.
- **Cookies:** session cookie is `httpOnly` + `sameSite=lax` (good) but **missing `Secure`** → see M1. No PII in browser `localStorage`.

**L4 — No self-service data deletion/export.** Users can't delete their own account or export their data; only an admin can delete a user (`DELETE /admin/users/{id}`). For a SaaS handling EU/India users, add a self-service "delete my account & data" flow (and ideally export) to meet GDPR/DPDP expectations.

---

## Check 3 — Pre-Deploy Production Audit *(ECC)*

**Result: several hardening gaps.**

- ✅ **Env vars** validated; app refuses to start without `JWT_SECRET`. `DEBUG` defaults off.
- ✅ **No debug/backdoor endpoints** (`/test`, `/seed-data`, etc.). Only `/`, `/health`, `/docs`, `/redoc`.
- ✅ **CORS** is env-restricted, not wildcard (`allow_origins=CORS_ALLOWED_ORIGINS_LIST`, `backend/main.py:82`).
- ✅ **H2 — Rate limiting added (fixed).** `/auth/login`, `/auth/signup`, and `/auth/password-reset/request` are now throttled per client IP by a Redis-backed limiter (`backend/utils/rate_limit.py`, defaults 10/min · 5/hr · 5/hr, env-configurable). Shared across workers, fails open on Redis error.
- ❌ **M4 — Error leakage.** Multiple handlers do `raise HTTPException(status_code=500, detail=str(exc))` (`backend/main.py:244,259,283,331,494,601`). Raw exception text (Redis errors, file paths, internals) is returned to the client. Return a generic message + a correlation ID; log the detail server-side only.
- ❌ **M5 — No security headers.** No HSTS, `X-Frame-Options`, `X-Content-Type-Options: nosniff`, or CSP on responses. Add a middleware (or set them at the frontend/reverse-proxy tier).
- ✅ **H1 — Database exposure closed (fixed).** Both compose files now require `REDIS_PASSWORD` (`--requirepass`), no longer publish Redis/RedisInsight on a public interface, and the backend authenticates with the password. TLS remains a follow-up only if Redis moves to a separate host.

---

## Check 4 — Deep Security Audit for Complex Logic *(Trail of Bits)*

*App profile: custom email/password + Google OAuth auth, per-user document storage, MCP/API tokens, webhooks. Billing is a non-charging stub.*

**Authentication & authorization**
- ✅ Every protected route depends on `require_current_user`/`require_session_user`/`require_admin_user`.
- ✅ **No IDOR** — no endpoint trusts a client-supplied user ID; ownership is implicit in the user-scoped keyspace, and cross-user `task_id`/conversation access returns 404/error.
- ✅ **Password-reset tokens** are random (`uuid4`), single-use (deleted on consume), and TTL'd (`backend/auth/store.py:178`). **L2:** TTL is 1 hour — tighten to ≤15 min.
- ✅ **JWT** — strong secret required, expiry enforced, `token_version` revocation. **L3:** logout only deletes the cookie; a captured bearer token stays valid until `exp` (stateless-JWT tradeoff — acceptable, but document it, and consider a short-lived-token + refresh model or a logout revocation list for SaaS).
- ⚠️ **M6 — OAuth CSRF.** `/auth/google/login` generates a `state` but `/auth/google/callback` never verifies it (`backend/auth/routes.py:145`, self-noted in the code). Store `state` (signed cookie or Redis, short TTL) and compare on callback.

**Payment logic**
- ✅ N/A in the dangerous sense — checkout is a stub that sets a plan with no charge and no client-trusted price. **When real payments land,** verify webhook signatures from the provider (Razorpay/Stripe), compute totals server-side, and gate paid features on server-verified payment status.

**Input handling**
- ✅ **SQL injection: N/A** — the datastore is Redis with parameterised client calls; no raw query strings built from user input.
- ✅ **XSS** — web sanitises rendered markdown with DOMPurify; React Native/`react-native-markdown-display` doesn't render raw HTML.
- ✅ **Upload validation** — extension allow-list + size/quota pre-check.
- ❌ **M3 — Path traversal.** The uploaded `file.filename` is used unsanitised to build the write path: `file_path = str(pool_dir / file.filename)` (`backend/main.py:409`), and the extension check (`os.path.splitext(file.filename)[1]`) still passes for a name like `../../<other_user_id>/General/evil.pdf`. Because `pathlib` resolves `..`, a crafted filename can write outside the user's directory — potentially into another tenant's folder. Sanitise with `os.path.basename()` (and reject names containing separators) before joining.

---

## Check 5 — Attacker's Perspective Review *(ECC)*

- **1. ID manipulation:** ✅ No horizontal access — user-scoped keys; `progress` and conversation endpoints reject other users' IDs.
- **2. Login bypass:** ✅ No endpoint works without a valid credential; expired/malformed JWTs are rejected; disabled accounts are blocked (`is_active`). No default account with a *known* password (the seeded admin uses a generated password — but see L5).
- **3. Privilege escalation:** ✅ Role check is server-side (`is_admin`/env-admin); a regular user can't reach admin routes by editing a JWT (signature-protected) or guessing URLs (403). Admin routes reject API tokens entirely.
- **4. Feature abuse:** ✅ signup/login/reset are now IP rate-limited (**H2 fixed**); uploads/AI-questions are quota-limited; webhook creation is plan-gated (Pro+).
- **5. Content injection:** ✅ XSS sanitised (DOMPurify); SQLi not applicable (Redis).
- **6. Internal exposure:** ⚠️ **L1** — `/docs` + `/redoc` publish the full API surface unauthenticated; **M4** — error responses leak internals. **H1 (Redis/RedisInsight reachable) is now fixed.** No `.env`/`.git` served by the API itself.
- **7. Business-logic manipulation:** ✅ No negative amounts / discount stacking possible (billing is a no-charge stub with server-set plans). Re-audit this section the moment real payments are wired in.
- ⚠️ **M2 — SSRF.** A user registers a webhook URL that Vaultly then POSTs to (`backend/integrations/webhooks.py:137`), and can trigger delivery on demand via `POST /integrations/webhooks/{id}/test`. There's no block-list for internal targets, so a webhook can point at `http://169.254.169.254/…` (cloud metadata), `http://localhost:6379`, or RFC-1918 hosts. The response body isn't returned, but status/timing is stored (`last_status`) — a blind SSRF + oracle. Validate the URL at registration: require `https`, resolve the host, and reject loopback/link-local/private/metadata ranges (guard against DNS-rebinding by re-checking at delivery).

---

## Prioritised remediation

**Before internet-facing launch:**

1. ✅ **H1 — Redis locked down (done).** Both compose files now require `REDIS_PASSWORD` (`--requirepass`), no longer publish `6379`/`8001` on a public interface (dev binds `127.0.0.1` only; TrueNAS uses `expose:` on the internal network), and the RedisInsight UI port is removed. All four backend Redis clients pass the password (`config.REDIS_PASSWORD or None` — backward-compatible when unset). *Remaining follow-up:* enable TLS if Redis ever runs on a separate host from the backend.
2. ✅ **H2 — Auth rate limiting added (done).** A Redis-backed, cross-worker fixed-window limiter (`backend/utils/rate_limit.py`) throttles `/auth/login`, `/auth/signup`, and `/auth/password-reset/request` per client IP (defaults 10/min, 5/hr, 5/hr; all env-configurable). Fails open if Redis is unreachable; respects `TRUST_PROXY_HEADERS` for correct IPs behind a proxy. Covered by `backend/tests/test_rate_limit.py`.
3. **M1 — Set `Secure` on the session cookie** (and keep `httpOnly`+`sameSite`). One line in `_set_session_cookie` (`backend/auth/routes.py:36`).
4. **M4 — Stop leaking exception text**; return generic errors + correlation IDs.
5. **M5 — Add security headers** (middleware or proxy).

**Soon after:**

6. **M3 — `os.path.basename()` the upload filename** and reject path separators.
7. **M2 — Validate webhook URLs** against internal ranges.
8. **M6 — Verify the OAuth `state`** on callback.

**Backlog / hygiene:** L1 (gate or disable `/docs` in prod), L2 (15-min reset TTL), L3 (logout revocation story), L4 (self-service account deletion/export), L5–L6 (avoid secrets in logs), L7 (`git rm --cached mcp/node_modules`).

---

*No AI review replaces professional security testing. Vaultly handles credentials, PII, and (soon) real payments at multi-tenant scale — commission a human penetration test before public launch, and re-run this review after every major feature.*
