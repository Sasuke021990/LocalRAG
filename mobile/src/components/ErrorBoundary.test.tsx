import React from 'react'
import { Text } from 'react-native'
import { render, fireEvent, screen } from '@testing-library/react-native'

jest.mock('lucide-react-native', () => ({ AlertTriangle: 'AlertTriangle' }))

import ErrorBoundary from './ErrorBoundary'

let shouldBlow = true
function Bomb() {
  if (shouldBlow) throw new Error('boom')
  return <Text>all good</Text>
}

beforeEach(() => {
  shouldBlow = true
  jest.spyOn(console, 'error').mockImplementation(() => {})
})
afterEach(() => {
  ;(console.error as jest.Mock).mockRestore()
})

test('renders children when nothing throws', () => {
  shouldBlow = false
  render(
    <ErrorBoundary>
      <Bomb />
    </ErrorBoundary>,
  )
  expect(screen.getByText('all good')).toBeTruthy()
})

test('catches a render error and shows a fallback instead of crashing', () => {
  render(
    <ErrorBoundary>
      <Bomb />
    </ErrorBoundary>,
  )
  expect(screen.getByText('Something went wrong')).toBeTruthy()
  expect(screen.queryByText('all good')).toBeNull()
})

test('"Try again" re-renders children, recovering once the underlying error is fixed', () => {
  render(
    <ErrorBoundary>
      <Bomb />
    </ErrorBoundary>,
  )
  expect(screen.getByText('Something went wrong')).toBeTruthy()
  shouldBlow = false
  fireEvent.press(screen.getByText('Try again'))
  expect(screen.getByText('all good')).toBeTruthy()
})
