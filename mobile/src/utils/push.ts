import { Platform } from 'react-native'
import Constants, { ExecutionEnvironment } from 'expo-constants'
import * as Device from 'expo-device'
import * as Notifications from 'expo-notifications'
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
