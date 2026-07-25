import React from 'react'
import { Text } from 'react-native'
import { render, screen } from '@testing-library/react-native'

const mockUseColorScheme = jest.fn()
jest.mock('react-native/Libraries/Utilities/useColorScheme', () => ({
  __esModule: true,
  default: () => mockUseColorScheme(),
}))

import { ThemeProvider, useAppTheme } from './ThemeContext'
import { lightColors, darkColors } from './tokens'

function Probe() {
  const { colors, scheme, isDark } = useAppTheme()
  return <Text>{`${scheme}|${String(isDark)}|${colors.canvas}`}</Text>
}

function renderProbe() {
  return render(<ThemeProvider><Probe /></ThemeProvider>)
}

test('uses the light palette when the OS is in light mode', () => {
  mockUseColorScheme.mockReturnValue('light')
  renderProbe()
  expect(screen.getByText(`light|false|${lightColors.canvas}`)).toBeTruthy()
})

test('uses the dark palette when the OS is in dark mode', () => {
  mockUseColorScheme.mockReturnValue('dark')
  renderProbe()
  expect(screen.getByText(`dark|true|${darkColors.canvas}`)).toBeTruthy()
})

// useColorScheme returns null before the OS value resolves (and on platforms
// that don't report one) -- that must read as light, not crash or go dark.
test('falls back to light when the OS reports no preference', () => {
  mockUseColorScheme.mockReturnValue(null)
  renderProbe()
  expect(screen.getByText(`light|false|${lightColors.canvas}`)).toBeTruthy()
})

test('light and dark share the brand accents but differ on the neutral scale', () => {
  expect(darkColors.indigo).toBe(lightColors.indigo)
  expect(darkColors.pink).toBe(lightColors.pink)
  expect(darkColors.canvas).not.toBe(lightColors.canvas)
  expect(darkColors.ink).not.toBe(lightColors.ink)
})
