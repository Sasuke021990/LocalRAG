import React, { forwardRef, useState } from 'react'
import { View, Text, TextInput, Pressable, StyleSheet, TextInputProps } from 'react-native'
import { Eye, EyeOff } from 'lucide-react-native'
import { useAppTheme } from '../../theme/ThemeContext'
import { fonts, radius } from '../../theme/tokens'

interface Props extends TextInputProps { label?: string }

// Ref-forwarding so screens can chain focus between fields via
// onSubmitEditing (task.md P2 #23) — every TextInput on the auth screens is
// wrapped in this component, so this is the one place that needs to expose
// the underlying node.
const Input = forwardRef<TextInput, Props>(function Input({ label, style, secureTextEntry, ...props }, ref) {
  const { colors } = useAppTheme()
  // Only a secureTextEntry field gets a reveal toggle; it starts hidden
  // exactly like a plain `secureTextEntry` field always did.
  const [hidden, setHidden] = useState(true)

  return (
    <View style={{ marginBottom: 4 }}>
      {label ? <Text style={[styles.label, { color: colors.inkSoft }]}>{label}</Text> : null}
      <View style={styles.fieldWrap}>
        <TextInput
          ref={ref}
          placeholderTextColor={colors.inkMuted}
          style={[
            styles.input,
            { backgroundColor: colors.surfaceAlt, borderColor: colors.border, color: colors.ink },
            secureTextEntry ? styles.inputWithToggle : null,
            style,
          ]}
          autoCapitalize="none"
          secureTextEntry={secureTextEntry ? hidden : undefined}
          {...props}
        />
        {secureTextEntry ? (
          <Pressable
            style={styles.toggle}
            onPress={() => setHidden((v) => !v)}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel={hidden ? 'Show password' : 'Hide password'}
          >
            {hidden ? <Eye color={colors.inkMuted} size={18} /> : <EyeOff color={colors.inkMuted} size={18} />}
          </Pressable>
        ) : null}
      </View>
    </View>
  )
})

export default Input

const styles = StyleSheet.create({
  label: { fontFamily: fonts.bodyMedium, fontSize: 13, marginBottom: 6 },
  fieldWrap: { justifyContent: 'center' },
  input: {
    height: 48,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    fontFamily: fonts.body,
    fontSize: 15,
  },
  inputWithToggle: { paddingRight: 44 },
  toggle: { position: 'absolute', right: 12, height: 48, justifyContent: 'center' },
})
