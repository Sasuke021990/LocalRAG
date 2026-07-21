# Vaultly Mobile (Expo / React Native)

The native app for Vaultly — same hosted backend as the web app, in the
"Vivid Pulse" design language. Email/password + Google auth (token-based),
knowledge pools, grounded AI chat (streaming with a reliable typewriter
fallback), document upload, and account/billing screens.

## Stack
Expo (managed) · React Navigation · Zustand · TanStack Query ·
`react-native-svg` (usage ring) · `expo-secure-store` (token) ·
`expo-document-picker` (upload) · `lucide-react-native` · Vivid Pulse tokens
(`src/theme/tokens.ts`, a direct port of the web values).

## Auth model
Native apps don't share a browser cookie jar, so the app uses **bearer
tokens**: `/auth/login`, `/auth/signup`, and `/auth/google/token-exchange`
return `session_token` in the JSON body, which is stored in the OS keychain
(`expo-secure-store`) and sent as `Authorization: Bearer <token>` on every
request. `require_current_user` on the backend already accepts either the
header (mobile) or the cookie (web).

## Run
```bash
cd mobile
npm install
npm start        # then press i (iOS), a (Android), or scan in Expo Go
npm test         # jest (jest-expo)
npm run typecheck
```

## Configuration
- **API base URL**: `app.json` → `expo.extra.apiBaseUrl` (defaults to the
  hosted placeholder `https://api.vaultly.app`). For local dev against a
  backend on your machine, set it to your LAN IP (`http://192.168.x.x:8000`).
- **Google sign-in** needs a Google OAuth client + the backend's
  `GOOGLE_REDIRECT_URI` to include the app's `vaultly://auth/callback` deep
  link. Until that's configured, use email/password.

## Status / not yet done
- **App icon & splash** (`assets/icon.png`, `assets/splash.png`) are
  placeholders — add real Vivid Pulse artwork before building.
- **EAS build profiles** (`eas.json`), store listing, and the Apple/Google
  developer accounts are external setup (see `.plan/05-mobile-app.md` M-7).
- **AI streaming vs. typewriter fallback**: `streamQuery` attempts real SSE
  and falls back automatically; which path is used on-device should be
  confirmed on a real build.
- Not verified on a device/simulator from this environment — needs
  `npm install` + a simulator to launch.
