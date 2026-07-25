import React from 'react'
import { View, Text, TextInput, StyleSheet, TextInputProps } from 'react-native'
import { useAppTheme } from '../../theme/ThemeContext'
import { fonts, radius } from '../../theme/tokens'

interface Props extends TextInputProps { label?: string }

export default function Input({ label, style, ...props }: Props) {
  const { colors } = useAppTheme()
  return (
    <View style={{ marginBottom: 4 }}>
      {label ? <Text style={[styles.label, { color: colors.inkSoft }]}>{label}</Text> : null}
      <TextInput
        placeholderTextColor={colors.inkMuted}
        style={[
          styles.input,
          { backgroundColor: colors.surfaceAlt, borderColor: colors.border, color: colors.ink },
          style,
        ]}
        autoCapitalize="none"
        {...props}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  label: { fontFamily: fonts.bodyMedium, fontSize: 13, marginBottom: 6 },
  input: {
    height: 48,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    fontFamily: fonts.body,
    fontSize: 15,
  },
})
