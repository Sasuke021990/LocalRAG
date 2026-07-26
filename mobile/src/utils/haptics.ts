import { Platform } from 'react-native'
import * as Haptics from 'expo-haptics'

/**
 * Thin wrapper over expo-haptics (task.md P2 #17).
 *
 * Every call is fire-and-forget and swallows failures: haptics are a garnish,
 * and a device without a taptic engine (or with system haptics disabled)
 * rejects these calls. Letting that bubble up would turn "no vibration" into
 * an unhandled rejection on an otherwise-successful action.
 *
 * Web is excluded outright — expo-haptics is a no-op there, but calling it
 * still costs a promise per interaction.
 */

// Read per call rather than cached at module load. Platform.OS doesn't change
// at runtime, so caching would work by luck — but it makes the guard
// untestable and silently wrong if this module is ever imported before the
// platform is resolved. A property read is free.
const supported = () => Platform.OS === 'ios' || Platform.OS === 'android'

function run(fn: () => Promise<void>): void {
  if (!supported()) return
  fn().catch(() => { /* no taptic engine, or haptics disabled system-wide */ })
}

/** A committed action: sending a message, starting an upload. */
export const tapLight = () => run(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light))

/** A weightier action: stopping generation, confirming a destructive step. */
export const tapMedium = () => run(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium))

/** Something finished cleanly — an answer landed, a document processed. */
export const notifySuccess = () =>
  run(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success))

/** Something went wrong the user should feel, not just read. */
export const notifyError = () =>
  run(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error))

/** A discrete state change: toggling a switch, picking from a list. */
export const selectionChanged = () => run(() => Haptics.selectionAsync())
