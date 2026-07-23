import React, { useState } from 'react'
import { View, Text, StyleSheet, Alert } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import { changePassword } from '../api/auth'
import { useAuthStore } from '../stores/authStore'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { colors, fonts } from '../theme/tokens'

export default function SettingsScreen() {
  const nav = useNavigation<any>()
  const { user, logout } = useAuthStore()
  const [cur, setCur] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [err, setErr] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    setErr('')
    if (next.length < 8) { setErr('New password must be at least 8 characters.'); return }
    if (next !== confirm) { setErr('New passwords do not match.'); return }
    setSaving(true)
    try {
      await changePassword(cur, next)
      Alert.alert('Done', 'Password updated.')
      setCur(''); setNext(''); setConfirm('')
    } catch (e: any) { setErr(e.message || 'Could not change password') }
    finally { setSaving(false) }
  }

  return (
    <Screen>
      <Text style={styles.title}>Settings</Text>
      <Text style={styles.email}>{user?.email}</Text>

      <Card style={{ gap: 12 }}>
        <Text style={styles.section}>Change password</Text>
        <Input label="Current password" value={cur} onChangeText={setCur} secureTextEntry />
        <Input label="New password" value={next} onChangeText={setNext} secureTextEntry />
        <Input label="Confirm new password" value={confirm} onChangeText={setConfirm} secureTextEntry />
        {err ? <Text style={styles.err}>{err}</Text> : null}
        <Button title="Update password" onPress={save} loading={saving} />
      </Card>

      {user?.is_admin ? (
        <Card style={{ gap: 12 }}>
          <Text style={styles.section}>Admin</Text>
          <Button title="Open admin panel" variant="secondary" onPress={() => nav.navigate('Admin')} />
        </Card>
      ) : null}

      <Card style={{ gap: 12 }}>
        <Button title="View plans & billing" variant="secondary" onPress={() => nav.navigate('Billing')} />
        <Button title="Log out" variant="danger" onPress={logout} />
      </Card>

      <Text style={styles.version}>Vaultly · v1.0.0</Text>
    </Screen>
  )
}

const styles = StyleSheet.create({
  title: { fontFamily: fonts.display, fontSize: 24, color: colors.ink },
  email: { fontFamily: fonts.body, fontSize: 14, color: colors.inkSoft, marginBottom: 4 },
  section: { fontFamily: fonts.displaySemi, fontSize: 16, color: colors.ink },
  err: { fontFamily: fonts.body, fontSize: 13, color: colors.rose },
  version: { fontFamily: fonts.body, fontSize: 12, color: colors.inkMuted, textAlign: 'center', marginTop: 8 },
})
