import React, { useEffect } from 'react'
import { StyleSheet } from 'react-native'
import Animated, { useSharedValue, useAnimatedStyle, withRepeat, withTiming, Easing } from 'react-native-reanimated'
import { useAppTheme } from '../theme/ThemeContext'

/**
 * The blinking caret shown while an answer streams (task.md P2 #16).
 *
 * Previously a static "▍" that looked like a cursor but never blinked, so a
 * stalled stream and a live one were visually identical. The blink is the
 * signal that something is still happening.
 */
export default function StreamingCursor() {
  const opacity = useSharedValue(1)
  const { colors } = useAppTheme()

  useEffect(() => {
    opacity.value = withRepeat(
      withTiming(0.15, { duration: 520, easing: Easing.inOut(Easing.ease) }),
      -1,
      true, // reverse: fade down, then back up
    )
  }, [opacity])

  const animatedStyle = useAnimatedStyle(() => ({ opacity: opacity.value }))

  return <Animated.Text style={[styles.cursor, { color: colors.pink }, animatedStyle]}> ▍</Animated.Text>
}

const styles = StyleSheet.create({
  cursor: { fontSize: 16 },
})
