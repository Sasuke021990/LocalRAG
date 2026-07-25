import React from 'react'
import { render, screen } from '@testing-library/react-native'
import { SafeAreaProvider } from 'react-native-safe-area-context'

jest.mock('lucide-react-native', () => ({ WifiOff: 'WifiOff' }))

const mockUseNetInfo = jest.fn()
jest.mock('@react-native-community/netinfo', () => ({
  useNetInfo: () => mockUseNetInfo(),
}))

import OfflineBanner from './OfflineBanner'

function renderBanner() {
  return render(
    <SafeAreaProvider initialMetrics={{ frame: { x: 0, y: 0, width: 0, height: 0 }, insets: { top: 0, left: 0, right: 0, bottom: 0 } }}>
      <OfflineBanner />
    </SafeAreaProvider>,
  )
}

test('renders nothing while connectivity is unknown (initial null state)', () => {
  mockUseNetInfo.mockReturnValue({ isConnected: null })
  renderBanner()
  expect(screen.queryByText(/offline/i)).toBeNull()
})

test('renders nothing while online', () => {
  mockUseNetInfo.mockReturnValue({ isConnected: true })
  renderBanner()
  expect(screen.queryByText(/offline/i)).toBeNull()
})

test('shows the offline banner when disconnected', () => {
  mockUseNetInfo.mockReturnValue({ isConnected: false })
  renderBanner()
  expect(screen.getByText(/offline/i)).toBeTruthy()
})
