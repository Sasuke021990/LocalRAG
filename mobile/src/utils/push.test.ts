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

import { registerForPush, unregisterFromPush, pushUnavailableReason } from './push'
import * as notificationsApi from '../api/notifications'

beforeEach(() => {
  jest.clearAllMocks()
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
