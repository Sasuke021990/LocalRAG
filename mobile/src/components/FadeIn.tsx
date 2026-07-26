import React, { useEffect } from 'react'
import { ViewStyle, StyleProp } from 'react-native'
import Animated, { useSharedValue, useAnimatedStyle, withTiming, withDelay, Easing } from 'react-native-reanimated'

/**
 * Fade + rise entrance (task.md P2 #16 — `react-native-reanimated` was an
 * installed dependency with genuinely zero usage in the codebase).
 *
 * Deliberately subtle and short: this wraps content that appears constantly
 * (chat bubbles, cards), so anything longer or bouncier becomes irritating by
 * the tenth repetition. Runs once on mount and never re-animates.
 */
export default function FadeIn({
  children,
  delay = 0,
  duration = 220,
  offsetY = 8,
  style,
}: {
  children: React.ReactNode
  delay?: number
  duration?: number
  offsetY?: number
  style?: StyleProp<ViewStyle>
}) {
  const progress = useSharedValue(0)

  useEffect(() => {
    progress.value = withDelay(
      delay,
      // ease-out: quick to start, settling at the end — reads as responsive
      // rather than sluggish.
      withTiming(1, { duration, easing: Easing.out(Easing.cubic) }),
    )
  }, [delay, duration, progress])

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ translateY: (1 - progress.value) * offsetY }],
  }))

  return <Animated.View style={[style, animatedStyle]}>{children}</Animated.View>
}
