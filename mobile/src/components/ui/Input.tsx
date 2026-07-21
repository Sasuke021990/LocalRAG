import React from 'react'
import { View, Text, TextInput, StyleSheet, TextInputProps } from 'react-native'
import { colors, fonts, radius } from '../../theme/tokens'

interface Props extends TextInputProps { label?: string }

export default function Input({ label, style, ...props }: Props) {
  return (
    <View style={{ marginBottom: 4 }}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <TextInput
        placeholderTextColor={colors.inkMuted}
        style={[styles.input, style]}
        autoCapitalize="none"
        {...props}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  label: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.inkSoft, marginBottom: 6 },
  input: {
    height: 48,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    fontFamily: fonts.body,
    fontSize: 15,
    color: colors.ink,
  },
})
