# Vaultly — Task & Progress Tracker

**Purpose**: the authoritative, up-to-date pending-work list. `plan.md` (2026-07-22) has drifted significantly stale — a lot of what it still marks `[ ]` was completed in the sessions since. This file supersedes it going forward; `plan.md`'s still-open items are folded in below with corrected status. `SECURITY.md` and `defect.md` remain the detailed record for their respective audits — this file tracks and links to them rather than duplicating their full content.

**Status key**: `[x]` done & verified · `[ ]` not started · `[~]` partially done (see note)

> **Current priority (2026-07-24): mobile-first launch.** Web/backend work (§1's new features, §3 reliability items) is on hold unless it's a shared-backend blocker for mobile. Everything mobile-launch-related should be pulled to the top of this file as it's scoped.
>
> **Housekeeping reminder**: `mobile/app.json`'s `apiBaseUrl` is currently pointed at a local LAN IP (`http://192.168.1.6:8000`) for live device testing against the dev Docker backend, and is **deliberately left uncommitted** so the in-progress test session isn't broken by a revert. **Must be reverted to `https://api.vaultly.app` before it's committed or any build is shipped.**

## Security fix — stored XSS in mobile Knowledge Graph WebView (2026-07-25) — **FIXED**

Found during a full security review against a comprehensive checklist (auth, secrets, network, input validation, Android config, performance, privacy). Full findings below the fix.

- [x] **Vulnerability**: `mobile/src/components/graphHtml.ts` embedded `JSON.stringify(graphData)` raw into a `<script>` tag (`var DATA = ${payload};`). `JSON.stringify` doesn't escape `/`, and node/edge labels come from LLM extraction over uploaded-document content (`backend/generation/pipeline.py::extract_graph_elements`) with **no character filtering** before storage. A label containing literal `</script>` (via an adversarial document or a prompt-injected extraction) would close the script tag early and inject arbitrary HTML/script into the WebView — a stored XSS with network egress (no CSP existed, `WebView` had `originWhitelist={['*']}`, no `onMessage` bridge to native code so it couldn't escalate to the app itself, but could exfiltrate anything visible in-WebView or redirect to a phishing page).
- [x] **Fix**: every `<` character in the stringified payload is now escaped to its JS unicode-escape form before interpolation (neutralizes `</script>` and any other tag while round-tripping to the exact same JS value at parse time — see `graphHtml.ts`'s `.replace(/</g, ...)` call). Added a `Content-Security-Policy` meta tag (`default-src 'none'`) as defense-in-depth — can't block the legitimate inline script itself (`'unsafe-inline'` needed, no per-render nonce), but blocks `connect-src`/`img-src`/`frame-src` so even a future escaping regression can't exfiltrate or navigate away.
- [x] 4 new tests in `graphHtml.test.ts` (new file) — confirms exactly one legitimate `</script>` survives a malicious label, confirms the escaped payload round-trips to the identical original label via `eval`, confirms benign labels are unaffected, confirms the CSP tag is present. Full mobile suite: 14/14 passing. `tsc --noEmit` clean, full `expo export` bundle succeeds.
- [x] **Not device-verified** — fix is unit-tested and bundle-verified but hasn't been re-opened on a physical device yet since landing.

**Everything else checked in the same review came back either already-sound** (JWT `HS256` pinned on encode+decode, bcrypt hashing, session/token revocation via `token_version`+`jti` blacklist, admin routes session-only, mobile token in `expo-secure-store` not `AsyncStorage`, zero hardcoded secrets, zero `console.*` calls anywhere in mobile source, no native `android/`/`ios/` dirs yet so manifest/exported-component/ProGuard/backup-config items are N/A until `expo prebuild`) **or already tracked** in the mobile launch-readiness audit above (mobile logout not hitting the backend, no account deletion, Google Sign-In hidden for v1, no biometric auth, no cert pinning) — not re-listed here to avoid duplication.

---

## Mobile launch-readiness audit (2026-07-25) — Phase 1 (all P0s) fixed same day

Full read-through of all 41 mobile source files (~3,400 lines) plus a systematic pass over every one of the 34 API call sites, cross-checked against the backend and web. Goal stated by the user: a bug-free, attractive, addictive, user-friendly mobile app. Original verdict: feature coverage is genuinely good (~85% of web) and where error-handling is done well (Admin screen) it's excellent — but there's a **systemic weakness**: errors are silently swallowed across most of the app, which is directly why chat "felt broken." All 6 P0 launch blockers below are now fixed — the app can build and submit, and the worst silent-failure paths are closed. P1/P2 below are still open.

### 🔴 P0 — Launch blockers — **ALL 6 FIXED (2026-07-25, "Phase 1")**

- [x] **1. Chat errors render an empty bubble — FIXED.** `ChatMsg` gained an `error?: string` field; `chatStore.ts`'s `onError` now sets it (backend's real message, or a generic fallback) instead of discarding it; `ChatBubble.tsx` renders a distinct rose error state instead of an empty bubble. Also fixed the underlying `query.ts` bug where a failure could get silently retried a second time (risked double-consuming the daily AI-question quota) before ever reaching `onError`. 3 new tests in `chatStore.test.ts`.
- [x] **2. Password-change session break — FIXED.** Backend's `POST /auth/change-password` now returns the fresh `session_token` in the JSON body (previously cookie-only); `SettingsScreen.tsx` persists it via `setToken()` immediately after a successful change. 1 new backend test; live-verified end-to-end against a rebuilt Docker stack (old token confirmed dead, new token confirmed working).
- [x] **3. No global 401 handling — FIXED.** `client.ts` gained a `setUnauthorizedHandler()` registration point (avoids a circular import with `authStore.ts`), wired up once in `App.tsx`: any 401 now force-logs-out, clears the React Query cache (closes a related "stale data visible after logout" gap), and shows a "Session expired" alert — but only when there was actually a session to lose, so a plain failed login attempt (also a 401) doesn't trigger a spurious alert. 2 new tests in `client.test.ts`.
- [x] **4. No account deletion on mobile — FIXED.** New `authApi.deleteAccount()` + `authStore.deleteAccount()`, and a "Danger zone" card in `SettingsScreen.tsx` (password re-confirmation + a destructive `Alert.alert` gate before the irreversible call). 2 new tests; live-verified end-to-end (wrong password → 400, correct password → 200 + old token immediately dead). *Noted in passing: web also has no UI for this — backend-only since the L4 security fix — out of scope for this mobile-focused pass.*
- [x] **5. Google Sign-In — hidden for v1, as decided.** Removed the button, handler, and now-unused imports from `LoginScreen.tsx`. The deep-link exchange plumbing (`authStore.loginWithGoogleCode`, `api/auth.ts::googleTokenExchange`) is left in place, unused, for whenever the backend gets fixed to support it properly.
- [x] **6. App icon / splash / assets / eas.json — FIXED.** Generated real on-brand assets (`mobile/assets/icon.png`, `adaptive-icon.png`, `splash.png`) matching the exact indigo→pink gradient + vault/padlock glyph already used in the app's own `Wordmark.tsx` — not generic placeholders. Wired into `app.json` (`icon`, `splash.image`, `android.adaptiveIcon.foregroundImage` + a proper solid `backgroundColor` for contrast, plus `ios.buildNumber`/`android.versionCode`). New `eas.json` with standard development/preview/production build profiles. Also fixed an unrelated-but-real `expo-doctor` finding along the way: `react-native-reanimated`'s missing `react-native-worklets` peer dependency (could crash a real, non-Expo-Go build) — installed. `expo-doctor`: **18/18 checks passing** (was 17/18 before the peer-dep fix).
- [x] **Verification across all 6**: mobile Jest suite 21/21 passing, `tsc --noEmit` clean, full `expo export` bundle succeeds, `expo-doctor` 18/18. Backend suite 461/461 passing. **Not yet re-tested on a physical device** — all verified via typecheck/tests/bundle/live-curl against the rebuilt backend, not an actual Expo Go session. Do a real device pass before calling Phase 1 fully done.

### 🟠 P1 — Broken or misleading

- [ ] **7. Logout never calls the backend.** `authStore.logout()` only clears the local SecureStore token — it never hits an equivalent of the web's logout, so the L3 JWT-blacklist fix (session revocation on logout) is bypassed entirely on mobile; a "logged out" token stays valid until natural expiry.
- [ ] **8. Streaming never actually streams on-device.** React Native's `fetch` doesn't expose a readable `body.getReader()`, so `streamQuery` (`api/query.ts:60-61`) **always** silently falls into `fallback()` — it waits for the *entire* answer to arrive, then fake-types it back at ~30ms/word. A 500-word answer adds roughly 15 seconds of artificial delay after the real answer already arrived.
- [ ] **9. `res.ok` is never checked in the streaming fallback path.** `query.ts:59` — a 429 (quota) or 403 response falls through into `fallback()`, which throws, which is caught by the same silent `onError` from #1 → empty bubble, no indication it was a quota/permission issue specifically.
- [ ] **10. No pull-to-refresh anywhere except Admin.** `Screen.tsx` (the shared screen wrapper) has no `RefreshControl` — Home, Knowledge, Graph, and Billing can't be refreshed with the universal mobile gesture.
- [ ] **11. Document summaries and graph data never auto-appear after upload.** They land 20-30s post-upload via the background pass (§1a/§1d); nothing re-fetches automatically. A user watches the progress bar finish, sees no summary, and reasonably assumes it failed.
- [ ] **12. No error boundary anywhere in the app.** One render-time error in any screen = permanent white screen, no recovery path.
- [ ] **13. No offline/network-loss handling.** Airplane mode produces the exact same silent nothing as every other kind of failure (feeds into the P0/P1 silent-failure pattern below).
- [ ] **14. No dark mode.** `app.json` hardcodes `"userInterfaceStyle": "light"`; every design token in `theme/tokens.ts` is light-only. Widely expected by users in 2026; also directly hurts the "attractive" goal.
- [ ] **15. Move/delete touch targets are too small and sit adjacent.** The `FolderInput`/`Trash2` icons added to `DocumentRow`/pool rows are ~18px with no larger hit area, and the destructive delete action sits right next to the harmless move action — easy to mis-tap.

### 🟡 P2 — Polish / "addictive" gaps

- [ ] **16. Zero animation anywhere** — `react-native-reanimated` is an installed dependency but genuinely unused (verified: no `Animated`/`withTiming`/`useSharedValue` in the codebase). No transitions, no skeleton loaders, no micro-interactions.
- [ ] **17. No haptic feedback** on send/upload/delete/any action.
- [ ] **18. No accessibility labels anywhere** — zero `accessibilityLabel` usage in the entire codebase; unusable with a screen reader.
- [ ] **19. Logout has no confirmation** — a single stray tap logs the user out immediately.
- [ ] **20. No visible "New chat" entry point on the Chat screen itself** — it's buried inside the separate Conversations sub-screen.
- [ ] **21. Daily AI-question quota is invisible everywhere except the Billing screen** — not shown on Home or in Chat, so users hit the limit with no warning.
- [ ] **22. No copy / retry / regenerate / stop-generation controls on chat answers** — table-stakes for a modern chat UI, present on neither platform's mobile client today.
- [ ] **23. Minor auth-form gaps**: no password-visibility toggle, no email keyboard type on login/signup, no return-key field chaining.

### Request-handling audit — every API call site checked

Traced all 34 call sites across `stores/`, `screens/`, and `components/` for try/catch coverage and user-visible feedback.

| Handling quality | Count | Examples |
|---|---|---|
| ✅ Properly handled (try/catch + user-visible success/error) | 21 | All auth flows, all conversation ops, pool create/move/delete, checkout, contact form, **all 8 Admin mutations** (`AdminScreen.tsx` — genuinely excellent, includes optimistic-update rollback on failure at line 56; this is the pattern to copy everywhere else) |
| ⚠️ Partial (catches the error but shows nothing useful) | 4 | Upload progress stream, the (now-hidden) Google flow, `listConversations`, password-change session handling |
| ❌ Silent failure (no catch / empty catch / no error UI at all) | 9 | See below |

**The 9 silent failures, specifically:**
- [ ] `streamQuery.onError` (`chatStore.ts:145`) discards the error entirely — feeds P0 #1
- [ ] `deleteDocument` in `KnowledgeScreen.tsx:72` has **no try/catch at all** — a bare `await` inside `onPress`; failure is an unhandled rejection and the document silently stays
- [ ] `authStore.refresh()` (`authStore.ts:43`) has no try/catch, and its caller `KnowledgeScreen.refresh()` (`KnowledgeScreen.tsx:38-41`) doesn't wrap it either
- [ ] `listConversations` (`chatStore.ts:74`) uses a deliberately empty `catch {}` — a failed fetch looks identical to "no conversations yet"
- [ ] `fetchPlans` and `fetchSubscription` in `BillingScreen.tsx:58-59` both use `.catch(() => {})` — a failure renders the Billing screen with no plans and no explanation
- [ ] `uploadWithProgress`'s `onError` handler in `KnowledgeScreen.tsx:58` is literally `() => {}` — the progress bar freezes mid-upload forever with no feedback
- [ ] **All 9 `useQuery` call sites** (Home ×2, Knowledge ×2, Chat ×1, Graph ×3, Billing) — verified zero screens ever render `isError`/`.error`. A failed fetch is indistinguishable from a genuinely-empty result — **"you have no documents" when the real problem is the server being unreachable.** Aggravating case: in `KnowledgeGraphScreen.tsx:40`, if the subscription fetch itself fails, `allowed` **defaults to `true`**, so a Free user can briefly slip past the paywall while a Pro user with a network blip sees "no graph" instead of an actual error.
- [ ] `useFonts`'s error is discarded in `App.tsx:34` (only `[fontsLoaded]` is destructured) — if font loading ever fails, the app renders an empty `<View/>` forever with no timeout and no recovery.

**Root cause, app-wide:** there is no shared failure path. Three structural pieces are missing:
- [ ] No global 401 interceptor (→ P0 #3)
- [ ] No `QueryClient` global `onError`/`retry` config — `App.tsx:19` is a bare `new QueryClient()`
- [ ] No error boundary (→ P1 #12)

### Infrastructure gaps for already-planned features

- [ ] **Podcast Mode (§1b)** needs `expo-av` (playback) and `expo-file-system` (on-device storage) — neither is installed.
- [ ] **Proactive Insights Feed (§1c)** needs `expo-notifications` — not installed, no push infra exists on mobile at all yet.
- [ ] **Camera-capture upload (§1i)** needs `expo-camera` or `expo-image-picker` — neither is installed.
- [ ] **Store submission** additionally needs: privacy-policy/terms links somewhere in the app, iOS permission usage strings (camera, photo library once the above land), and real `ios.buildNumber`/`android.versionCode` values in `app.json`.

### Recommended order

1. ✅ **Phase 1 — stop the bleeding (P0 items 1-6) — DONE 2026-07-25.** Chat error surfacing → global 401 handling → password-change session break → account deletion → hide the Google button → app icon/splash/`assets/`/`eas.json`. See the P0 section above for what actually landed for each.
2. **Phase 2 — trust (P1 items 7-15) — not started.** Logout hits the backend → fix `res.ok` handling → pull-to-refresh everywhere → auto-refresh after upload → error boundary → offline handling.
3. **Phase 3 — delight (P2 items 16-23) — not started.** Animations → dark mode → haptics → chat message actions → bigger touch targets → quota visibility → accessibility labels.

---

## 0. What's already shipped (context, not action items)

Condensed so this doc is self-orienting without re-reading the whole history:

- **Auth**: username+email login, username uniqueness, idle-session timeout (non-dismissible-by-accident popup), self-service account deletion, JWT session revocation on logout (Redis blacklist), Google OAuth.
- **Chat**: pool-selection popup, conversational memory, server-side conversation persistence (list/rename/delete/resume), per-plan conversation caps, Markdown rendering, source-document-name display (not full passage dumps), admin-only timing indicator, Qwen3 `/think` `/no_think` hybrid-thinking wiring.
- **Billing**: Free/Pro/Max/Customize tiers defined and enforced (storage, AI-question quota, conversation caps, webhooks gate, priority-processing flag), contact-lead capture, mobile `BillingScreen.tsx` matches backend plans (no more stale USD data).
- **Knowledge Base**: pool creation flow, document upload with real per-phase progress + image/OCR support, per-document AI summaries (§1d), move/delete documents — **mobile now has full pool-management parity with web** (upload-time pool picker, assign/move/create/delete pool — see §1a).
- **Knowledge Graph** (§1a): per-pool concept graph built by a background LLM pass, web (D3.js) + mobile (WebView) UIs, Pro+ gated, live-tested on device with bugs found and fixed.
- **Mobile**: full parity pass (auth, chat/pools/markdown/sources, upload progress, admin panel, Knowledge Base pool management, Knowledge Graph) + Expo SDK 51→54 upgrade. Still missing: an Integrations screen (tokens/webhooks — see §1e, deferred).
- **Admin panel**: web + newly-built mobile version — stats, settings, user management (quota/admin-toggle/active-toggle/delete).
- **Security**: full 5-check audit (`SECURITY.md`) — both Highs fixed (Redis auth+lockdown, auth rate limiting), all 7 Lows fixed (Swagger gating, reset-token TTL, logout revocation, self-service deletion, no more logged admin passwords, quieter OAuth error logs, untracked `mcp/node_modules`), and all 6 Mediums fixed (Secure cookie, webhook SSRF guard, upload path-traversal sanitization, no more leaked exception text, HTTP security headers, OAuth state CSRF check — see §4 for verification detail).
- **Defects**: 4 reported bugs fixed and verified live — stale semantic cache after document delete/upload, stale cache after conversation delete, pool-creation Save button race (see `defect.md`). Plus a 5th found and fixed this session: graph data attaching to the wrong pool on a fast pool-move (§1a).

---

## 1. New features — planned in full, not yet built

Specs below are locked from planning discussion; nothing in this section has any code written yet.

### 1a. Interactive Knowledge Graph — **FIXED, live-tested on device (2026-07-25)**

Backend, web, and mobile all shipped, then put through two rounds of real on-device testing (Expo Go against the dev Docker backend) that found and fixed a genuine data-correctness bug plus several mobile parity gaps and UI issues.

**Core feature:**
- [x] NER/topic extraction: **LLM-based**, decoupled from the upload-blocking path — `generation/pipeline.py::extract_graph_elements()` (drains `generate_stream`, tolerant JSON parse) wired into `main.py` `_process()`'s background pass right after the summary step, own try/except, `run_coroutine_threadsafe` onto the request loop.
- [x] Graph storage in Redis: `knowledge_graph/store.py` — nodes + edges, each with a source-document list; concepts dedup across documents by slug. Keys mirror the webhooks SET+per-item convention.
- [x] **Delete handling (locked "correct" version)**: `store.remove_document()` strips a doc from every element's source list and deletes any left empty; shared elements survive. Wired into `delete_document` and the cross-pool branch of `move_document`. An invariant (edge endpoints always superset the edge's sources) + a dangling-edge skip in `get_pool_graph` guarantee no stranded edges.
- [x] **Backfill: none** — extraction only runs on new uploads; the endpoint returns an empty graph for pools with only pre-feature documents.
- [x] **Platform: web + mobile.** Web: `KnowledgeGraphPage.vue` (real D3.js force graph). Mobile: `KnowledgeGraphScreen.tsx` embeds a WebView. *Deviation from blueprint:* the mobile WebView renders a **self-contained vanilla-JS force graph** (`components/graphHtml.ts`) rather than inlining the 270 KB D3 bundle into an HTML string — same force-directed UX, no external fetch, works offline. Noted intentionally.
- [x] New API: `GET /pools/{pool}/graph` → `{nodes, edges}` (gated).
- [x] **Plan gating**: `knowledge_graph` feature flag (Free False, Pro/Max/Customize True). Endpoint 403s on Free; web + mobile both show a lock/upsell card with a "See plans"/"Upgrade" CTA instead of the graph.

**Found + fixed during on-device testing:**
- [x] **Data-correctness bug**: a document moved to a new pool *while* background graph extraction was still running (a 10-30s LLM call) got its graph attached to the OLD pool — `_process()` captured the upload-time pool in a closure and the late-finishing extraction blindly merged into that stale value. Fixed with `ingestion_pipeline.document_still_at()`, a guard checked immediately before the merge that skips it if the doc moved elsewhere in the meantime (mirrors the safe no-op `update_document_summary` already had). Found and purged 11 orphaned nodes / 10 orphaned edges this bug had left in a real account.
- [x] **Mobile subscription-cache bug**: the Graph tab kept showing "upgrade to Pro" after the user had already upgraded on the Billing tab, because bottom-tab screens stay mounted and cache the old plan. Fixed with a focus-triggered refetch + explicit cache invalidation on plan change.
- [x] **Mobile layout bug**: the pool-chip row stretched into a giant pill, stealing the graph's vertical space (a horizontal `ScrollView` in a flex column grows to fill height by default in RN). Pinned to content height.
- [x] **Graph UI, both platforms**: white halo behind labels + truncation + tap-to-declutter (dense graphs were unreadable); real minimum-distance node collision (charge/repulsion alone let nodes cluster too close); a floating "Recenter" button to reset pan/zoom; a "Highlight concept" picker on mobile (was tap-only); pinch-to-zoom + one-finger pan on mobile's WebView graph.
- [x] **Mobile pool management** (was entirely missing before this pass — upload always went to "General", no way to move/create/delete a pool): pool picker at upload time, "needs a pool" assignment strip, move-to-pool per document, dedicated "New pool" flow, delete-empty-pool. New shared `PoolPickerSheet.tsx` component; added the missing `deletePool` API call (existed on web, not on mobile).
- [x] **Mobile HomeScreen**: stat cards now tappable → Knowledge tab (mirrors web).
- [x] 458 backend tests total (35 for the graph store/extraction/gating + 3 for the pool-move race guard), full web Vite build clean, mobile `tsc` clean + full `expo export` bundle succeeds after every change.
- [ ] **The final round of fixes (recenter button, collision spacing) has not yet been re-verified on-device** — was mid-session when they landed. Confirm on next device pass.
- [x] **Small extraction-only model, built and tested but not yet committed (2026-07-25)**: new `config.LLM_GRAPH_MODEL` env var (blank by default, falls back to `LLM_MODEL`) — graph extraction is structured JSON output, not conversation, so it can run on something much smaller (e.g. `qwen3-0.6b`) than the full chat model. `generate_stream()` on both LLM backends now takes an optional `model` override (embedded backend ignores it — one GGUF loaded, nothing to switch to). Wired through `docker-compose.yml`, `docker-compose.truenas.yml`, `.env.example`. 460/460 tests passing (2 new). **Held per an explicit "don't implement until I say" pause — code exists locally, not committed/pushed.**

**Pending redesign (decided 2026-07-25): move extraction to a nightly batch job**
- [ ] **Change the processing model from "immediately after upload" to a scheduled nightly cron at 3am.** All documents uploaded that day get their graph extraction processed in one overnight batch; results appear for the user the next day. Motivation: the per-upload LLM extraction has been unreliable (see the LLM-stability item in §3) and batching moves that cost off the interactive path.
- [ ] **Requirement: each document must reach a definitive terminal state** (100% success or an explicit recorded failure) — no silently-stuck documents. Needs per-document processing status tracked in Redis, retries with backoff inside the batch, and a way to see/re-run failures.
- [ ] ⚠️ **Known caveat (flagged, accepted):** batching alone does **not** fix the underlying LLM instability — it relocates the failures to 3am rather than eliminating them. The retry/terminal-state requirement above is what actually addresses reliability, so it is not optional.
- [x] **Decided 2026-07-25**: the per-document AI summary (§1d) **also moves to this nightly batch** — both extraction and summarization run together in the same overnight pass, sharing the same per-document terminal-state/retry machinery. §1d's original "immediate, upload-time" timing is superseded by this.
- [ ] Scheduler infra note: this is the second feature needing a scheduler (Insights Feed §1c is the other). Build one shared scheduling mechanism rather than two, and mind the multi-worker leader-lock problem called out in §3.

### 1b. Podcast Mode
- [ ] Summarizer prompt (new system prompt variant in `grounding.py`, reuses existing `generation/llm.py` pipeline)
- [x] **TTS engine decided 2026-07-25: the "Audio Studio" API**, not `xtts-api-server` as originally spec'd. Custom REST API (not OpenAI-compatible), documented at `F:\Projects\Gravity\Audio\docs\API.md`, base `http://localhost:8888/api/v1`:
  - `GET /engines` → lists `edge` (cloud, Microsoft Edge Read Aloud) and `piper` (local, offline neural TTS)
  - `GET /voices?engine=piper` → voice IDs per engine
  - `POST /synthesize` → `{input, engine, voice, speed}` → raw audio bytes (`audio/mpeg` for edge, `audio/wav` for piper); `X-Cache-Status` header (`HIT`/`MISS`, Redis-backed on their side)
  - Config should mirror the `LLM_*` pattern regardless: `TTS_ENABLED`, `TTS_API_BASE=http://localhost:8888/api/v1`, `TTS_ENGINE` (edge/piper), `TTS_VOICE`.
- [ ] **Storage model (REVISED 2026-07-25 — supersedes the earlier "streamed only, never persisted" note):** still **never written to a persistent file server-side** (nothing stored in the cloud or on the host), but the finished audio **is saved on the user's own device** so it survives navigating away and can be replayed. Generation **must not be cancelled** when the user leaves the Podcast screen — it completes in the background and the file lands on-device.
- [ ] **Old-file cleanup**: starting a new podcast deletes the previously stored on-device audio (one podcast retained at a time, per user).
- [ ] ⚠️ **Implementation conflict to resolve**: §2's client-disconnect fix deliberately *stops* LLM generation when the client goes away. Podcast needs the opposite (keep going). In practice, navigating between screens inside a live RN app does **not** drop an in-flight fetch, so foreground navigation is fine — but this must be verified, and the two behaviors kept deliberately distinct (chat: cancel on disconnect; podcast: run to completion).
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
- [x] **Mobile: visually confirmed on a real device** during the Knowledge Graph testing pass (2026-07-25) — summaries render correctly under each document row in the Knowledge Base list.
- [ ] **Web: still not visually verified in-browser** — the in-app browser tool was unavailable all session. Do a real visual pass next time it's back.
- [ ] ⚠️ **Timing superseded 2026-07-25**: this was built as an immediate upload-time background pass (still accurately describes the current shipped code above). It is now moving to the nightly 3am batch alongside graph extraction — see §1a. Not yet re-implemented; this section still describes the live behavior until that lands.

### 1e. MCP/API token template section — **FIXED (web)**
- [x] **Gap found and fixed**: the curl/MCP examples only existed inside the show-once token-reveal modal — closing it lost them entirely, unlike `WebhookManager.vue`'s always-available collapsible template section. Added a matching persistent "API / MCP setup template" section to `TokenManager.vue` using a `YOUR_TOKEN` placeholder, so the format is always there to reference even without a live token in hand.
- [ ] **Mobile: not built at all.** There is no Integrations screen on mobile (`mobile/src/screens/`) — no token management, no webhook management. **Sequencing decided 2026-07-24: deferred to the end of the build order**, after the 3 headline mobile-launch features (Knowledge Graph §1a, Podcast Mode §1b, Insights Feed §1c) and Document summaries (§1d).

### 1f. Unlimited MCP/API tokens as an explicit plan detail — **FIXED**
- [x] Confirmed no token-count cap anywhere in the backend. `featureList()` in both `BillingPage.vue` and mobile's `BillingScreen.tsx` now renders "Unlimited API/MCP tokens" (was the vaguer "API token access") whenever a plan's `api_tokens` flag is set — true for every tier today. `billing/plans.py`'s docstring updated to state it explicitly too.

### 1g. Customize plan card — simplified display — **FIXED**
- [x] `BillingPage.vue` and mobile `BillingScreen.tsx`: the Customize card no longer renders the per-plan feature checklist or the "/ period" price suffix — just the plan name/Enterprise badge, the word **"Custom"**, and the **"Contact us"** button.

### 1i. New features & UX improvements — requested 2026-07-25 (from device testing notes)

Everything here is **newly requested and unbuilt**. Ordered roughly by dependency/impact.

**Restructure: dedicated Pools tab (decided — replaces the in-place pool UI built 2026-07-25)**
- [ ] **New "Pools" tab** owning everything pool-related: create, rename, move documents between pools, delete, and general pool management.
- [ ] **Knowledge Base tab becomes upload-only** — the pool picker / assign strip / move / create / delete UI added to `KnowledgeScreen.tsx` earlier this session moves out to the new tab. (That work isn't wasted — `PoolPickerSheet.tsx` and the `deletePool` API call get reused.)
- [ ] **No silent default-General assignment**: after a successful upload, show a success popup that asks the user to file the document — into General, a new pool, or an existing one. General remains an *option*, just not an automatic destination. (The existing `pool_assigned=false` flag already models "not yet filed" and should back this.)
- [x] **Decided 2026-07-25: mobile-only.** Web does **not** get a separate Pools tab — it keeps its current single-page Knowledge Base with inline pool management exactly as-is. This restructure applies to mobile only.

**Chat**
- [ ] **Fix: LLM failure silently degrades to a raw passage dump.** When the inference server errors/times out, `generate_stream` yields nothing and `stream_answer` falls back to `_fallback_answer()`, which dumps raw scored passages with no indication anything failed. Users read this as "chat is broken/weird." Show an explicit "AI is temporarily unavailable — please try again" state instead. **This is the root cause of the reported "chat not working properly."**
- [ ] **Web pre-template behavior**: the "Summarise the {pool} pool" suggestion chip (`ChatPage.vue:144`) should list **every document in the pool with its short summary**, reusing the stored per-document summaries from §1d rather than a generic RAG retrieval.
- [ ] **Mobile: deliberately NO pre-templates.** The suggestion chips ("Summarise the X pool", "What are the key points?", "List the pros and cons") exist on web (`ChatPage.vue:139-149`) and mobile has none — **keep it that way.** Recorded so a future parity pass doesn't "helpfully" add them.
- [ ] **AI needs user context**: give the model access to the user's name (and other profile context) so chat replies, notifications, and the Insights Feed (§1c) can address the user personally.

**Knowledge Base / upload**
- [ ] **Camera capture upload (mobile)**: take a photo in-app and upload it directly, alongside the existing file picker. Backend already OCRs images, so this is a client-side capture + existing upload path.
- [ ] **Animation above the progress bar** while a document is embedding — the current bar is functional but flat; add motion to make the wait feel alive.

**Mobile UX fixes**
- [ ] **Move-to-pool button is too small to tap reliably** (the `FolderInput` icon added to `DocumentRow`). Needs a bigger target — likely a row overflow menu (⋮ → Move / Delete) rather than two tiny adjacent icons. Also revisit the delete icon at the same time, same problem.

**Cross-cutting**
- [ ] **UI/UX polish pass — analyse gaps and raise the whole app to a professional, enterprise-grade standard.** Deliberately broad; needs its own scoping pass once the structural changes above land (a polish pass before the Pools-tab restructure would be wasted work). Supersedes/absorbs the vague "motion pass" item in §5.
- [ ] **MCP**: remove the API text from MCP *(user note — exact intent not yet confirmed; likely the `curlExample()` block in the token-reveal modal / template section. **Explicitly deferred by the user 2026-07-25 ("will think of it at last")** — not blocking, revisit at the end of this build order.)*

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

- [ ] **LLM inference-server instability (observed live 2026-07-25)** — backend logs show repeated `Read timed out` (120s) and `Response ended prematurely` against `host.docker.internal:1235`, causing both failed graph extractions and degraded chat answers. Two distinct problems:
  - *Infra side (likely outside the codebase):* the currently-configured model (`ornith-1.0-9b-uncensored`) may be too slow/heavy for the host, and/or `LLM_MAX_CONCURRENCY=8` may be overloading the inference server. Worth measuring before assuming a code fix.
  - *Code side (definitely ours):* every failure is caught and swallowed (`generation/llm.py` logs and yields zero tokens), so the user gets a silent fallback instead of an error — see the chat fix in §1i. Retries/backoff around LLM calls are also absent everywhere.
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
- [ ] Motion/animation pass (page transitions, message entrance, hover states, skeleton loaders) — no work started. **Now folded into the broader enterprise-grade UI/UX polish pass in §1i**; keep them together rather than doing two passes.

---

## Open questions needing your decision

~~1. Proactive Insights Feed Pro/Max~~ — confirmed intentional, env-configurable later.
~~2. Annual-discount badge scope~~ — confirmed, all three paid plans.
~~3. Document-summary timing~~ — originally decided as an upload-time background pass (still true for how it was *built*); **superseded 2026-07-25, see #9 below** — summaries are moving to the nightly batch alongside graph extraction.
~~4. LLM-keeps-running bug~~ — confirmed (silent wasted compute) and fixed, see §2.
~~5. Podcast audio storage~~ — decided 2026-07-25: never server-side; stored **on the user's device**, generation completes in the background, previous file deleted when a new podcast starts. See §1b.
~~6. Pools tab scope~~ — decided 2026-07-25: a **new dedicated Pools tab replaces** the in-place pool UI; Knowledge Base becomes upload-only. See §1i.
~~7. Graph processing timing~~ — decided 2026-07-25: **nightly 3am batch cron** instead of per-upload. See §1a.
~~8. "No pretemplates in mobile"~~ — clarified: refers to chat suggestion chips ("summarise the pool", "pros and cons"). Web keeps them, mobile deliberately has none. See §1i.

~~9. Document-summary batch timing~~ — decided 2026-07-25: summaries move to the same nightly 3am batch as graph extraction (not immediate anymore — see §1a and §1d).
~~10. Web Pools-tab scope~~ — decided 2026-07-25: **web does NOT get a separate Pools tab.** The Pools-tab restructure (§1i) is mobile-only; web keeps its current single-page Knowledge Base with inline pool management as-is.
~~11. TTS engine for Podcast Mode~~ — resolved 2026-07-25: use the **Audio Studio API** (`localhost:8888` — `/synthesize`, `/voices`, `/engines`, Edge + Piper engines), not `xtts-api-server`. See §1b.

Still open:

1. **Team/Org plan** — final name, and the rest of its feature row (storage/AI-quota/webhooks/priority-processing). Deliberately deferred — not blocking other work.
2. **"Remove API text from MCP"** — exact intent unconfirmed. **Explicitly deferred by the user ("will think of it at last")** — not blocking anything, revisit at the end. See §1i.
