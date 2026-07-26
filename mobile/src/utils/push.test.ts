/**
 * Push registration guards.
 *
 * The behavior that matters most here is *not registering* — push is
 * genuinely unavailable in Expo Go ("You must use a development build to use
 * push notifications since the capability is not built into Expo Go") and on
 * simulators. Calling into expo-notifications in those environments throws,
 * so these guards are what keep the Expo Go dev loop working.
 */

const mockGetPermissions = jest.fn()
const mockRequestPermissions = jest.fn()
const mockGetToken = jest.fn()
const mockSetChannel = jest.fn().mockResolvedValue(undefined)

jest.mock('expo-notifications', () => ({
  setNotificationHandler: jest.fn(),
  setNotificationChannelAsync: (...a: any[]) => mockSetChannel(...a),
  getPermissionsAsync: () => mockGetPermissions(),
  requestPermissionsAsync: () => mockRequestPermissions(),
  getExpoPushTokenAsync: (...a: any[]) => mockGetToken(...a),
  AndroidImportance: { DEFAULT: 3 },
}))

const deviceState = { isDevice: true }
jest.mock('expo-device', () => ({ get isDevice() { return deviceState.isDevice } }))

const constantsState: any = {
  executionEnvironment: 'standalone',
  expoConfig: { extra: { eas: { projectId: 'proj-123' } } },
}
jest.mock('expo-constants', () => ({
  __esModule: true,
  default: constantsState,
  ExecutionEnvironment: { StoreClient: 'storeClient', Standalone: 'standalone', Bare: 'bare' },
}))

jest.mock('../api/notifications', () => ({
  registerDevice: jest.fn().mockResolvedValue({ status: 'registered' }),
  unregisterDevice: jest.fn().mockResolvedValue({ status: 'unregistered' }),
}))

// In-memory stand-in for the on-device preference store.
const prefStore: Record<string, string> = {}
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(async (k: string) => (k in prefStore ? prefStore[k] : null)),
  setItemAsync: jest.fn(async (k: string, v: string) => { prefStore[k] = v }),
  deleteItemAsync: jest.fn(async (k: string) => { delete prefStore[k] }),
}))

import {
  registerForPush, unregisterFromPush, pushUnavailableReason,
  isPushEnabled, setPushEnabled,
} from './push'
import * as notificationsApi from '../api/notifications'

beforeEach(() => {
  jest.clearAllMocks()
  // clearAllMocks() resets call history but NOT implementations, so a
  // mockRejectedValue set by one test would otherwise leak into every test
  // after it. Re-establish the happy path explicitly.
  ;(notificationsApi.registerDevice as jest.Mock).mockResolvedValue({ status: 'registered' })
  ;(notificationsApi.unregisterDevice as jest.Mock).mockResolvedValue({ status: 'unregistered' })
  for (const k of Object.keys(prefStore)) delete prefStore[k]
  deviceState.isDevice = true
  constantsState.executionEnvironment = 'standalone'
  constantsState.expoConfig = { extra: { eas: { projectId: 'proj-123' } } }
  mockGetPermissions.mockResolvedValue({ status: 'granted', canAskAgain: true })
  mockRequestPermissions.mockResolvedValue({ status: 'granted' })
  mockGetToken.mockResolvedValue({ data: 'ExponentPushToken[abc123]' })
})

describe('availability guards', () => {
  test('reports unavailable in Expo Go', () => {
    constantsState.executionEnvironment = 'storeClient'
    expect(pushUnavailableReason()).toMatch(/development build/i)
  })

  test('reports unavailable on a simulator', () => {
    deviceState.isDevice = false
    expect(pushUnavailableReason()).toMatch(/physical device/i)
  })

  test('reports available in a real build on a real device', () => {
    expect(pushUnavailableReason()).toBeNull()
  })

  test('Expo Go registers nothing and never touches expo-notifications', async () => {
    constantsState.executionEnvironment = 'storeClient'
    expect(await registerForPush()).toBeNull()
    expect(mockGetToken).not.toHaveBeenCalled()
    expect(mockGetPermissions).not.toHaveBeenCalled()
    expect(notificationsApi.registerDevice).not.toHaveBeenCalled()
  })

  test('a simulator registers nothing', async () => {
    deviceState.isDevice = false
    expect(await registerForPush()).toBeNull()
    expect(notificationsApi.registerDevice).not.toHaveBeenCalled()
  })
})

describe('registration', () => {
  test('returns the token and sends it to the backend', async () => {
    expect(await registerForPush()).toBe('ExponentPushToken[abc123]')
    expect(notificationsApi.registerDevice).toHaveBeenCalledWith('ExponentPushToken[abc123]')
  })

  test('passes the EAS projectId, which Expo requires to mint a token', async () => {
    await registerForPush()
    expect(mockGetToken).toHaveBeenCalledWith({ projectId: 'proj-123' })
  })

  test('bails out when no projectId is configured', async () => {
    constantsState.expoConfig = { extra: {} }
    expect(await registerForPush()).toBeNull()
    expect(mockGetToken).not.toHaveBeenCalled()
  })

  test('does not prompt when permission is already granted', async () => {
    await registerForPush()
    expect(mockRequestPermissions).not.toHaveBeenCalled()
  })

  test('prompts when undetermined, then registers on grant', async () => {
    mockGetPermissions.mockResolvedValue({ status: 'undetermined', canAskAgain: true })
    expect(await registerForPush()).toBe('ExponentPushToken[abc123]')
    expect(mockRequestPermissions).toHaveBeenCalled()
  })

  test('a denied prompt registers nothing', async () => {
    mockGetPermissions.mockResolvedValue({ status: 'undetermined', canAskAgain: true })
    mockRequestPermissions.mockResolvedValue({ status: 'denied' })
    expect(await registerForPush()).toBeNull()
    expect(notificationsApi.registerDevice).not.toHaveBeenCalled()
  })

  test('does not re-prompt after a permanent denial', async () => {
    mockGetPermissions.mockResolvedValue({ status: 'denied', canAskAgain: false })
    expect(await registerForPush()).toBeNull()
    expect(mockRequestPermissions).not.toHaveBeenCalled()
  })

  test('a backend failure never throws — login must not break', async () => {
    ;(notificationsApi.registerDevice as jest.Mock).mockRejectedValue(new Error('500'))
    expect(await registerForPush()).toBeNull()
  })

  test('an expo-notifications failure never throws', async () => {
    mockGetToken.mockRejectedValue(new Error('no push capability'))
    expect(await registerForPush()).toBeNull()
  })
})

describe('user on/off preference', () => {
  test('defaults to on for a fresh install (opt-out, not opt-in)', async () => {
    expect(await isPushEnabled()).toBe(true)
  })

  test('turning it off detaches the device and persists the choice', async () => {
    const result = await setPushEnabled(false, 'ExponentPushToken[abc123]')
    expect(result).toEqual({ ok: true, token: null })
    expect(notificationsApi.unregisterDevice).toHaveBeenCalledWith('ExponentPushToken[abc123]')
    expect(await isPushEnabled()).toBe(false)
  })

  test('turning it back on re-registers', async () => {
    await setPushEnabled(false, 'ExponentPushToken[abc123]')
    const result = await setPushEnabled(true, null)
    expect(result).toEqual({ ok: true, token: 'ExponentPushToken[abc123]' })
    expect(notificationsApi.registerDevice).toHaveBeenCalled()
    expect(await isPushEnabled()).toBe(true)
  })

  test('auto-registration respects "off" — the relaunch case', async () => {
    // The bug this guards: authStore re-registers on every launch of a
    // restored session, which would silently undo the user's choice.
    await setPushEnabled(false, 'ExponentPushToken[abc123]')
    ;(notificationsApi.registerDevice as jest.Mock).mockClear()

    expect(await registerForPush()).toBeNull()
    expect(notificationsApi.registerDevice).not.toHaveBeenCalled()
    expect(mockGetToken).not.toHaveBeenCalled()
  })

  test('a permanent OS denial reports blockedBySystem so the UI can offer settings', async () => {
    mockGetPermissions.mockResolvedValue({ status: 'denied', canAskAgain: false })
    const result = await setPushEnabled(true, null)
    expect(result).toEqual({
      ok: false,
      blockedBySystem: true,
      reason: expect.stringMatching(/system settings/i),
    })
    expect(notificationsApi.registerDevice).not.toHaveBeenCalled()
  })

  test('an OS-blocked attempt preserves the user\'s intent for when they re-allow it', async () => {
    // "Wants notifications" and "notifications are currently possible" are
    // separate axes. Storing false here would mean that after re-allowing the
    // permission in system settings, they'd have to come back and toggle
    // again — the app would stay silent for no visible reason.
    mockGetPermissions.mockResolvedValue({ status: 'denied', canAskAgain: false })
    await setPushEnabled(true, null)
    expect(await isPushEnabled()).toBe(true)

    // Permission restored out-of-band: registration now succeeds unprompted.
    mockGetPermissions.mockResolvedValue({ status: 'granted', canAskAgain: true })
    expect(await registerForPush()).toBe('ExponentPushToken[abc123]')
  })

  test('failing to enable rolls the preference back so the switch matches reality', async () => {
    mockGetToken.mockRejectedValue(new Error('no push capability'))
    const result = await setPushEnabled(true, null)
    expect(result.ok).toBe(false)
    expect(await isPushEnabled()).toBe(false)
  })

  test('cannot be switched on in Expo Go, and says why', async () => {
    constantsState.executionEnvironment = 'storeClient'
    const result = await setPushEnabled(true, null)
    expect(result).toEqual({
      ok: false,
      blockedBySystem: false,
      reason: expect.stringMatching(/development build/i),
    })
    expect(notificationsApi.registerDevice).not.toHaveBeenCalled()
    // Same intent-preservation as the OS-denial case above: installing a dev
    // build later should just work without re-toggling.
    expect(await isPushEnabled()).toBe(true)
  })

  test('turning it off still works when the backend is unreachable', async () => {
    ;(notificationsApi.unregisterDevice as jest.Mock).mockRejectedValue(new Error('offline'))
    const result = await setPushEnabled(false, 'ExponentPushToken[abc123]')
    expect(result).toEqual({ ok: true, token: null })
    // The local preference is what stops future registration, so the user's
    // choice sticks even though the server still holds the token.
    expect(await isPushEnabled()).toBe(false)
  })
})

describe('unregistration', () => {
  test('detaches the token server-side', async () => {
    await unregisterFromPush('ExponentPushToken[abc123]')
    expect(notificationsApi.unregisterDevice).toHaveBeenCalledWith('ExponentPushToken[abc123]')
  })

  test('a null token is a no-op', async () => {
    await unregisterFromPush(null)
    expect(notificationsApi.unregisterDevice).not.toHaveBeenCalled()
  })

  test('a backend failure never throws — logout must always succeed', async () => {
    ;(notificationsApi.unregisterDevice as jest.Mock).mockRejectedValue(new Error('offline'))
    await expect(unregisterFromPush('ExponentPushToken[abc123]')).resolves.toBeUndefined()
  })
})
