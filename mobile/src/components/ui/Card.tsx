import React from 'react'
import { View, ViewStyle, StyleProp } from 'react-native'
import { useAppTheme } from '../../theme/ThemeContext'
import { radius, cardShadow } from '../../theme/tokens'

export default function Card({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  const { colors } = useAppTheme()
  return (
    <View
      style={[
        { backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: 20, ...cardShadow },
        style,
      ]}
    >
      {children}
    </View>
  )
}
