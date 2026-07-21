import React, { useState } from 'react'
import { View, Text, StyleSheet } from 'react-native'
import type { NativeStackScreenProps } from '@react-navigation/native-stack'
import { useAuthStore } from '../../stores/authStore'
import Screen from '../../components/Screen'
import Wordmark from '../../components/Wordmark'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import { colors, fonts } from '../../theme/tokens'
import type { AuthStackParams } from '../../navigation/AuthStack'

type Props = NativeStackScreenProps<AuthStackParams, 'Signup'>

export default function SignupScreen({ navigation }: Props) {
  const signup = useAuthStore((s) => s.signup)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit() {
    setError('')
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (password !== confirm) { setError('Passwords do not match.'); return }
    setLoading(true)
    try { await signup(email.trim(), password) }
    catch (e: any) { setError(e.message || 'Signup failed') }
    finally { setLoading(false) }
  }

  return (
    <Screen contentStyle={{ paddingTop: 48 }}>
      <View style={{ alignItems: 'center', marginBottom: 12 }}><Wordmark size={28} /></View>
      <Text style={styles.title}>Create your vault</Text>
      <Text style={styles.subtitle}>1 GB free — your documents, always yours.</Text>

      <Card style={{ gap: 12 }}>
        <Input label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" placeholder="you@example.com" />
        <Input label="Password" value={password} onChangeText={setPassword} secureTextEntry placeholder="At least 8 characters" />
        <Input label="Confirm password" value={confirm} onChangeText={setConfirm} secureTextEntry placeholder="••••••••" />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Button title="Create account" onPress={submit} loading={loading} />
      </Card>

      <View style={styles.footer}>
        <Text style={styles.muted}>Already have an account? </Text>
        <Text style={styles.link} onPress={() => navigation.navigate('Login')}>Sign in</Text>
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  title: { fontFamily: fonts.display, fontSize: 22, color: colors.ink, textAlign: 'center' },
  subtitle: { fontFamily: fonts.body, fontSize: 14, color: colors.inkSoft, textAlign: 'center', marginBottom: 8 },
  error: { fontFamily: fonts.body, fontSize: 13, color: colors.rose },
  footer: { flexDirection: 'row', justifyContent: 'center', marginTop: 8 },
  muted: { fontFamily: fonts.body, color: colors.inkSoft },
  link: { fontFamily: fonts.bodySemi, color: colors.indigo },
})
