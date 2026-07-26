import { Platform } from 'react-native'
import Constants, { ExecutionEnvironment } from 'expo-constants'
import * as Device from 'expo-device'
import * as Notifications from 'expo-notifications'
import * as SecureStore from 'expo-secure-store'
import * as notificationsApi from '../api/notifications'

/**
 * Expo push registration.
 *
 * IMPORTANT — this is a no-op in Expo Go. Expo's docs are explicit: "You must
 * use a development build to use push notifications since the capability is
 * not built into Expo Go." Calling getExpoPushTokenAsync() there throws, so
 * every entry point below bails out early instead, keeping the Expo Go dev
 * loop working while the real thing waits on a dev build. Same for
 * simulators/emulators, which have no push capability at all.
 */

// Show an alert + play a sound even when a notification lands while the app
// is in the foreground. Without this, a notification arriving while the user
// is looking at the app is silently swallowed.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
})

// The user's own on/off choice, persisted on-device. Distinct from the OS
// permission: someone can grant the system prompt and still switch
// notifications off in Settings, and that choice has to survive relaunches —
// otherwise the auto-registration on every app launch would silently
// re-enable what they just turned off.
//
// Stored in SecureStore purely because it's already a dependency (used for
// the session token); a boolean preference isn't a secret, this just avoids
// pulling in AsyncStorage for one key.
const PREF_KEY = 'push_enabled'

/** Whether the user wants push. Defaults to true (opt-out, not opt-in). */
export async function isPushEnabled(): Promise<boolean> {
  try {
    const raw = await SecureStore.getItemAsync(PREF_KEY)
    return raw === null ? true : raw === 'true'
  } catch {
    return true
  }
}

async function setPreference(enabled: boolean): Promise<void> {
  try {
    await SecureStore.setItemAsync(PREF_KEY, String(enabled))
  } catch {
    /* preference is best-effort; the register/unregister below is what counts */
  }
}

/** True when push genuinely can't work here, so callers can skip silently. */
export function pushUnavailableReason(): string | null {
  if (Constants.executionEnvironment === ExecutionEnvironment.StoreClient) {
    return 'Push notifications require a development build (not supported in Expo Go).'
  }
  if (!Device.isDevice) {
    return 'Push notifications require a physical device.'
  }
  return null
}

function projectId(): string | undefined {
  // EAS injects this at build time; app.json's extra.eas.projectId is the
  // fallback for a locally-run build. getExpoPushTokenAsync() cannot issue a
  // token without it.
  return (
    Constants.expoConfig?.extra?.eas?.projectId ??
    (Constants as any)?.easConfig?.projectId
  )
}

/**
 * Ask for permission (if not already decided), fetch this device's Expo push
 * token, and register it against the signed-in account.
 *
 * Returns the token on success, or null when push is unavailable, permission
 * was denied, or registration failed — never throws, since a failure here
 * must not block sign-in.
 */
export async function registerForPush(): Promise<string | null> {
  if (!(await isPushEnabled())) {
    if (__DEV__) console.log('[push] skipped — user has notifications turned off')
    return null
  }

  const unavailable = pushUnavailableReason()
  if (unavailable) {
    if (__DEV__) console.log(`[push] skipped — ${unavailable}`)
    return null
  }

  try {
    // Android needs an explicit channel or notifications arrive silently with
    // no heads-up display. Must exist before the first notification lands.
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'Default',
        importance: Notifications.AndroidImportance.DEFAULT,
        vibrationPattern: [0, 250, 250, 250],
      })
    }

    const existing = await Notifications.getPermissionsAsync()
    let status = existing.status
    // Only prompt if the user hasn't already decided — re-asking after an
    // explicit denial does nothing on iOS and is a poor experience anyway.
    if (status !== 'granted' && existing.canAskAgain) {
      status = (await Notifications.requestPermissionsAsync()).status
    }
    if (status !== 'granted') {
      if (__DEV__) console.log('[push] permission not granted')
      return null
    }

    const id = projectId()
    if (!id) {
      if (__DEV__) console.log('[push] no EAS projectId configured — run `eas init`')
      return null
    }

    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId: id })
    await notificationsApi.registerDevice(token)
    if (__DEV__) console.log('[push] registered')
    return token
  } catch (err: any) {
    // Best-effort: a push failure must never break login or app startup.
    if (__DEV__) console.log(`[push] registration failed: ${err?.message ?? err}`)
    return null
  }
}

/**
 * Detach this device from the account being signed out of, so the next person
 * to sign in on this device doesn't receive the previous user's
 * notifications. Best-effort — logout must succeed regardless.
 */
export async function unregisterFromPush(token: string | null): Promise<void> {
  if (!token) return
  try {
    await notificationsApi.unregisterDevice(token)
  } catch {
    /* offline, or the token was already detached server-side — both fine */
  }
}

export type PushToggleOutcome =
  | { ok: true; token: string | null }
  /**
   * Turning it on didn't work. ``blockedBySystem`` means the OS permission is
   * denied and can't be re-prompted — the only way back is the system
   * settings app, so the UI should offer to open it rather than silently
   * flipping the switch back and leaving the user confused.
   */
  | { ok: false; reason: string; blockedBySystem: boolean }

/**
 * Apply the user's notification on/off choice from Settings.
 *
 * Persists the preference either way, so a relaunch doesn't undo it, then
 * makes it real: registering this device, or detaching it server-side so the
 * backend has nothing to send to. There's no separate "muted" flag on the
 * backend — no token *is* the off switch.
 */
export async function setPushEnabled(
  enabled: boolean,
  currentToken: string | null,
): Promise<PushToggleOutcome> {
  if (!enabled) {
    await setPreference(false)
    await unregisterFromPush(currentToken)
    return { ok: true, token: null }
  }

  // The two environmental blocks below deliberately leave the stored
  // preference untouched. "Does the user want notifications" and "are
  // notifications currently possible" are separate axes: someone who taps the
  // switch in Expo Go, or with the OS permission revoked, still *wants* them.
  // Preserving that intent means it starts working once they install a dev
  // build or re-allow the permission, with no need to come back and re-toggle.
  // The switch itself already renders off in both cases (see
  // SettingsScreen's `pushOn && !pushBlocked`).
  const unavailable = pushUnavailableReason()
  if (unavailable) {
    return { ok: false, reason: unavailable, blockedBySystem: false }
  }

  const permission = await Notifications.getPermissionsAsync()
  if (permission.status !== 'granted' && !permission.canAskAgain) {
    return {
      ok: false,
      blockedBySystem: true,
      reason: 'Notifications are turned off for Vaultly in your system settings.',
    }
  }

  await setPreference(true)
  const token = await registerForPush()
  if (!token) {
    // Permission prompt declined just now, no EAS projectId, or the backend
    // call failed. Roll the preference back so the switch reflects reality.
    await setPreference(false)
    return {
      ok: false,
      blockedBySystem: false,
      reason: 'Could not enable notifications. Please try again.',
    }
  }
  return { ok: true, token }
}
