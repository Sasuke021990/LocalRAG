import React, { useEffect } from 'react'
import { StyleProp, ViewStyle } from 'react-native'
import Animated, {
  useSharedValue, useAnimatedStyle, withRepeat, withTiming, withSequence, Easing,
} from 'react-native-reanimated'
import { useAppTheme } from '../theme/ThemeContext'
import { radius } from '../theme/tokens'

/**
 * Pulsing placeholder block for content that's still loading (task.md P2 #16).
 *
 * A gentle opacity pulse rather than the usual sliding shimmer: shimmer needs
 * a gradient overlay per block, and at this size the extra machinery isn't
 * worth it — the pulse reads as "loading" just as clearly.
 */
export default function Skeleton({
  width = '100%',
  height = 14,
  style,
}: {
  width?: number | `${number}%`
  height?: number
  style?: StyleProp<ViewStyle>
}) {
  const pulse = useSharedValue(0.4)
  const { colors } = useAppTheme()

  useEffect(() => {
    pulse.value = withRepeat(
      withSequence(
        withTiming(0.8, { duration: 650, easing: Easing.inOut(Easing.ease) }),
        withTiming(0.4, { duration: 650, easing: Easing.inOut(Easing.ease) }),
      ),
      -1, // forever, until unmounted
      false,
    )
  }, [pulse])

  const animatedStyle = useAnimatedStyle(() => ({ opacity: pulse.value }))

  return (
    <Animated.View
      accessibilityLabel="Loading"
      style={[
        { width, height, borderRadius: radius.sm, backgroundColor: colors.border },
        animatedStyle,
        style,
      ]}
    />
  )
}
