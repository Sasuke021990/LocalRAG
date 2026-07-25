import React, { useState } from 'react'
import { View, Text, StyleSheet } from 'react-native'
import type { NativeStackScreenProps } from '@react-navigation/native-stack'
import { useAuthStore } from '../../stores/authStore'
import Screen from '../../components/Screen'
import Wordmark from '../../components/Wordmark'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import { useAppTheme } from '../../theme/ThemeContext'
import { fonts } from '../../theme/tokens'
import type { AuthStackParams } from '../../navigation/AuthStack'

type Props = NativeStackScreenProps<AuthStackParams, 'Login'>

export default function LoginScreen({ navigation }: Props) {
  const login = useAuthStore((s) => s.login)
  const { colors } = useAppTheme()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit() {
    setError(''); setLoading(true)
    try { await login(email.trim(), password) }
    catch (e: any) { setError(e.message || 'Login failed') }
    finally { setLoading(false) }
  }

  // Google Sign-In is intentionally not offered on mobile for v1: the
  // backend's google_login() ignores the redirect_uri a native app must
  // supply to get the auth code back via deep link, so the flow strands the
  // user in the system browser on the web app instead of returning to the
  // app (task.md's mobile launch-readiness audit, P0 #5). Email/password
  // and the deep-link exchange plumbing (authStore.loginWithGoogleCode,
  // api/auth.ts::googleTokenExchange) are left in place, unused, for when
  // the backend is fixed to support this properly.

  return (
    <Screen contentStyle={{ paddingTop: 48 }}>
      <View style={{ alignItems: 'center', marginBottom: 12 }}><Wordmark size={28} /></View>
      <Text style={[styles.title, { color: colors.ink }]}>Welcome back</Text>
      <Text style={[styles.subtitle, { color: colors.inkSoft }]}>Sign in to your knowledge base.</Text>

      <Card style={{ gap: 12 }}>
        <Input label="Email or username" value={email} onChangeText={setEmail} autoCapitalize="none" placeholder="you@example.com" />
        <Input label="Password" value={password} onChangeText={setPassword} secureTextEntry placeholder="••••••••" />
        {error ? <Text style={[styles.error, { color: colors.rose }]}>{error}</Text> : null}
        <Button title="Sign in" onPress={submit} loading={loading} />
      </Card>

      <View style={styles.footer}>
        <Text style={[styles.muted, { color: colors.inkSoft }]}>New here? </Text>
        <Text style={[styles.link, { color: colors.indigo }]} onPress={() => navigation.navigate('Signup')}>Create an account</Text>
      </View>
      <Text style={[styles.link, { color: colors.indigo, textAlign: 'center' }]} onPress={() => navigation.navigate('ForgotPassword')}>
        Forgot your password?
      </Text>
    </Screen>
  )
}

const styles = StyleSheet.create({
  title: { fontFamily: fonts.display, fontSize: 22, textAlign: 'center' },
  subtitle: { fontFamily: fonts.body, fontSize: 14, textAlign: 'center', marginBottom: 8 },
  error: { fontFamily: fonts.body, fontSize: 13 },
  footer: { flexDirection: 'row', justifyContent: 'center', marginTop: 8 },
  muted: { fontFamily: fonts.body },
  link: { fontFamily: fonts.bodySemi },
})
