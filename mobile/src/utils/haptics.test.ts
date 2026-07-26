/**
 * Haptics wrapper (task.md P2 #17).
 *
 * The behavior worth pinning down isn't "it vibrates" — it's that a device
 * which *can't* vibrate never turns that into an unhandled rejection on an
 * otherwise-successful action.
 */

const mockImpact = jest.fn()
const mockNotification = jest.fn()
const mockSelection = jest.fn()

jest.mock('expo-haptics', () => ({
  impactAsync: (...a: any[]) => mockImpact(...a),
  notificationAsync: (...a: any[]) => mockNotification(...a),
  selectionAsync: (...a: any[]) => mockSelection(...a),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' },
  NotificationFeedbackType: { Success: 'success', Error: 'error' },
}))

const platform = { OS: 'ios' }
jest.mock('react-native', () => ({ Platform: { get OS() { return platform.OS } } }))

import { tapLight, tapMedium, notifySuccess, notifyError, selectionChanged } from './haptics'

beforeEach(() => {
  jest.clearAllMocks()
  platform.OS = 'ios'
  mockImpact.mockResolvedValue(undefined)
  mockNotification.mockResolvedValue(undefined)
  mockSelection.mockResolvedValue(undefined)
})

describe('feedback styles map to the right primitive', () => {
  test('tapLight is a light impact', () => {
    tapLight()
    expect(mockImpact).toHaveBeenCalledWith('light')
  })

  test('tapMedium is a medium impact — used for interrupting/destructive actions', () => {
    tapMedium()
    expect(mockImpact).toHaveBeenCalledWith('medium')
  })

  test('notifySuccess and notifyError use notification feedback, not impact', () => {
    notifySuccess()
    expect(mockNotification).toHaveBeenCalledWith('success')
    notifyError()
    expect(mockNotification).toHaveBeenCalledWith('error')
    expect(mockImpact).not.toHaveBeenCalled()
  })

  test('selectionChanged uses the selection primitive', () => {
    selectionChanged()
    expect(mockSelection).toHaveBeenCalled()
  })
})

describe('failure tolerance', () => {
  test('a rejected haptic never surfaces as an unhandled rejection', async () => {
    // A device with no taptic engine, or with system haptics turned off.
    mockImpact.mockRejectedValue(new Error('Haptics not available'))
    const unhandled = jest.fn()
    process.on('unhandledRejection', unhandled)

    expect(() => tapLight()).not.toThrow()
    // Let the rejected promise settle before checking.
    await new Promise((r) => setTimeout(r, 0))

    process.off('unhandledRejection', unhandled)
    expect(unhandled).not.toHaveBeenCalled()
  })

  test('a rejected notification is swallowed too', async () => {
    mockNotification.mockRejectedValue(new Error('nope'))
    expect(() => notifySuccess()).not.toThrow()
    await new Promise((r) => setTimeout(r, 0))
  })
})

describe('platform guard', () => {
  test('android is supported', () => {
    platform.OS = 'android'
    tapLight()
    expect(mockImpact).toHaveBeenCalled()
  })

  test('web is skipped entirely — expo-haptics is a no-op there anyway', () => {
    platform.OS = 'web'
    tapLight()
    notifySuccess()
    selectionChanged()
    expect(mockImpact).not.toHaveBeenCalled()
    expect(mockNotification).not.toHaveBeenCalled()
    expect(mockSelection).not.toHaveBeenCalled()
  })
})
