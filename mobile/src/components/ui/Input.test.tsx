import React, { createRef } from 'react'
import { TextInput } from 'react-native'
import { render, screen, fireEvent } from '@testing-library/react-native'

jest.mock('lucide-react-native', () => ({ Eye: 'Eye', EyeOff: 'EyeOff' }))

import Input from './Input'

describe('password visibility toggle (task.md P2 #23)', () => {
  test('a secureTextEntry field starts hidden and offers a reveal control', () => {
    render(<Input label="Password" secureTextEntry testID="pw" />)
    expect(screen.getByTestId('pw').props.secureTextEntry).toBe(true)
    expect(screen.getByLabelText('Show password')).toBeTruthy()
  })

  test('tapping the toggle reveals the text, tapping again re-hides it', () => {
    render(<Input label="Password" secureTextEntry testID="pw" />)

    fireEvent.press(screen.getByLabelText('Show password'))
    expect(screen.getByTestId('pw').props.secureTextEntry).toBe(false)
    // The control now offers the inverse action.
    expect(screen.getByLabelText('Hide password')).toBeTruthy()

    fireEvent.press(screen.getByLabelText('Hide password'))
    expect(screen.getByTestId('pw').props.secureTextEntry).toBe(true)
  })

  test('a normal field has no toggle and is never obscured', () => {
    render(<Input label="Email" testID="email" />)
    expect(screen.queryByLabelText('Show password')).toBeNull()
    // Must stay undefined rather than false — passing secureTextEntry={false}
    // to a plain field would be a behavior change for every non-password use.
    expect(screen.getByTestId('email').props.secureTextEntry).toBeUndefined()
  })
})

describe('ref forwarding (enables return-key focus chaining)', () => {
  test('exposes the underlying TextInput so screens can call .focus()', () => {
    const ref = createRef<TextInput>()
    render(<Input label="Email" ref={ref} />)
    expect(ref.current).not.toBeNull()
    expect(typeof ref.current?.focus).toBe('function')
  })

  test('forwards a ref for a password field too', () => {
    // The toggle wraps the input in an extra View — the ref must still reach
    // the TextInput, not the wrapper.
    const ref = createRef<TextInput>()
    render(<Input label="Password" secureTextEntry ref={ref} />)
    expect(typeof ref.current?.focus).toBe('function')
  })
})

describe('pass-through props', () => {
  test('keyboard and autofill props reach the TextInput', () => {
    render(
      <Input
        label="Email"
        testID="email"
        keyboardType="email-address"
        autoComplete="email"
        returnKeyType="next"
      />,
    )
    const input = screen.getByTestId('email')
    expect(input.props.keyboardType).toBe('email-address')
    expect(input.props.autoComplete).toBe('email')
    expect(input.props.returnKeyType).toBe('next')
  })

  test('onSubmitEditing fires so screens can chain focus or submit', () => {
    const onSubmitEditing = jest.fn()
    render(<Input label="Email" testID="email" onSubmitEditing={onSubmitEditing} />)
    fireEvent(screen.getByTestId('email'), 'submitEditing')
    expect(onSubmitEditing).toHaveBeenCalled()
  })
})
