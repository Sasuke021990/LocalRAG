import React from 'react'
import { View, StyleSheet, ViewStyle } from 'react-native'
import { colors, radius, cardShadow } from '../../theme/tokens'

export default function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 20,
    ...cardShadow,
  },
})
