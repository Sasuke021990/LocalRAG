import React from 'react'
import { Pressable, Text, StyleSheet, ActivityIndicator, View, ViewStyle } from 'react-native'
import { LinearGradient } from 'expo-linear-gradient'
import { colors, fonts, gradient, radius } from '../../theme/tokens'

interface Props {
  title: string
  onPress?: () => void
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  disabled?: boolean
  loading?: boolean
  style?: ViewStyle
}

export default function Button({ title, onPress, variant = 'primary', disabled, loading, style }: Props) {
  const inner = (
    <Text style={[styles.label, variant === 'primary' ? styles.labelOnGradient : { color: variantColor(variant) }]}>
      {loading ? '…' : title}
    </Text>
  )

  if (variant === 'primary') {
    return (
      <Pressable onPress={onPress} disabled={disabled || loading} style={[{ opacity: disabled ? 0.5 : 1 }, style]}>
        <LinearGradient colors={gradient.brand} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.base}>
          {loading ? <ActivityIndicator color="#fff" /> : inner}
        </LinearGradient>
      </Pressable>
    )
  }

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={[styles.base, outlineStyle(variant), { opacity: disabled ? 0.5 : 1 }, style]}
    >
      {loading ? <ActivityIndicator color={variantColor(variant)} /> : inner}
    </Pressable>
  )
}

function variantColor(v: string) {
  if (v === 'danger') return colors.rose
  if (v === 'ghost') return colors.inkSoft
  return colors.indigo
}
function outlineStyle(v: string): ViewStyle {
  if (v === 'ghost') return { backgroundColor: 'transparent' }
  return { backgroundColor: colors.surface, borderWidth: 1, borderColor: v === 'danger' ? colors.rose : colors.indigo }
}

const styles = StyleSheet.create({
  base: { height: 48, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 20 },
  label: { fontFamily: fonts.bodySemi, fontSize: 15 },
  labelOnGradient: { color: '#fff' },
})
