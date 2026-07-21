import React, { useState } from 'react'
import { View, Text, StyleSheet } from 'react-native'
import type { NativeStackScreenProps } from '@react-navigation/native-stack'
import * as WebBrowser from 'expo-web-browser'
import * as Linking from 'expo-linking'
import Constants from 'expo-constants'
import { useAuthStore } from '../../stores/authStore'
import Screen from '../../components/Screen'
import Wordmark from '../../components/Wordmark'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import { colors, fonts } from '../../theme/tokens'
import type { AuthStackParams } from '../../navigation/AuthStack'

type Props = NativeStackScreenProps<AuthStackParams, 'Login'>

export default function LoginScreen({ navigation }: Props) {
  const login = useAuthStore((s) => s.login)
  const loginWithGoogleCode = useAuthStore((s) => s.loginWithGoogleCode)
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

  // Opens Google consent in the system browser and returns the auth `code`
  // via the vaultly:// deep link, which the backend exchanges for a token.
  // Requires the Google OAuth app + backend redirect to include the native URI.
  async function google() {
    setError('')
    try {
      const apiBase = (Constants.expoConfig?.extra as any)?.apiBaseUrl
      const redirect = Linking.createURL('auth/callback') // vaultly://auth/callback
      const authUrl = `${apiBase}/auth/google/login?redirect_uri=${encodeURIComponent(redirect)}`
      const result = await WebBrowser.openAuthSessionAsync(authUrl, redirect)
      if (result.type === 'success' && result.url) {
        const code = Linking.parse(result.url).queryParams?.code as string | undefined
        if (code) { await loginWithGoogleCode(code); return }
      }
    } catch (e: any) {
      setError('Google sign-in is not available yet — use email and password.')
    }
  }

  return (
    <Screen contentStyle={{ paddingTop: 48 }}>
      <View style={{ alignItems: 'center', marginBottom: 12 }}><Wordmark size={28} /></View>
      <Text style={styles.title}>Welcome back</Text>
      <Text style={styles.subtitle}>Sign in to your knowledge base.</Text>

      <Card style={{ gap: 12 }}>
        <Input label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" placeholder="you@example.com" />
        <Input label="Password" value={password} onChangeText={setPassword} secureTextEntry placeholder="••••••••" />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Button title="Sign in" onPress={submit} loading={loading} />
        <Button title="Continue with Google" variant="secondary" onPress={google} />
      </Card>

      <View style={styles.footer}>
        <Text style={styles.muted}>New here? </Text>
        <Text style={styles.link} onPress={() => navigation.navigate('Signup')}>Create an account</Text>
      </View>
      <Text style={[styles.link, { textAlign: 'center' }]} onPress={() => navigation.navigate('ForgotPassword')}>
        Forgot your password?
      </Text>
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
