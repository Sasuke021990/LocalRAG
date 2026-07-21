import React, { useState } from 'react'
import { Text, StyleSheet } from 'react-native'
import type { NativeStackScreenProps } from '@react-navigation/native-stack'
import { requestPasswordReset } from '../../api/auth'
import Screen from '../../components/Screen'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import { colors, fonts } from '../../theme/tokens'
import type { AuthStackParams } from '../../navigation/AuthStack'

type Props = NativeStackScreenProps<AuthStackParams, 'ForgotPassword'>

export default function ForgotPasswordScreen({ navigation }: Props) {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)

  async function submit() {
    try { await requestPasswordReset(email.trim()) } catch { /* never leak existence */ }
    setSent(true)
  }

  return (
    <Screen contentStyle={{ paddingTop: 64 }}>
      <Text style={styles.title}>Reset your password</Text>
      <Card style={{ gap: 12 }}>
        {sent ? (
          <>
            <Text style={styles.body}>
              If that email exists, a reset link has been sent. Open it on this device to set a new password.
            </Text>
            <Button title="Back to sign in" onPress={() => navigation.navigate('Login')} />
          </>
        ) : (
          <>
            <Input label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" placeholder="you@example.com" />
            <Button title="Send reset link" onPress={submit} />
            <Text style={styles.link} onPress={() => navigation.navigate('Login')}>Back to sign in</Text>
          </>
        )}
      </Card>
    </Screen>
  )
}

const styles = StyleSheet.create({
  title: { fontFamily: fonts.display, fontSize: 22, color: colors.ink, textAlign: 'center', marginBottom: 8 },
  body: { fontFamily: fonts.body, fontSize: 14, color: colors.inkSoft, lineHeight: 20 },
  link: { fontFamily: fonts.bodySemi, color: colors.indigo, textAlign: 'center', marginTop: 4 },
})
