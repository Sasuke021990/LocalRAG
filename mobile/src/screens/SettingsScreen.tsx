import React, { useState } from 'react'
import { View, Text, StyleSheet, Alert } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import { useQueryClient } from '@tanstack/react-query'
import { changePassword } from '../api/auth'
import { setToken } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { colors, fonts } from '../theme/tokens'

export default function SettingsScreen() {
  const nav = useNavigation<any>()
  const qc = useQueryClient()
  const { user, logout, deleteAccount } = useAuthStore()
  const [cur, setCur] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [err, setErr] = useState('')
  const [saving, setSaving] = useState(false)

  const [showDelete, setShowDelete] = useState(false)
  const [deletePassword, setDeletePassword] = useState('')
  const [deleteErr, setDeleteErr] = useState('')
  const [deleting, setDeleting] = useState(false)

  // Don't leave this account's cached documents/chat/graph data visible to
  // whoever's signed in next on this device.
  async function logoutAndClearCache() {
    await logout()
    qc.clear()
  }

  async function save() {
    setErr('')
    if (next.length < 8) { setErr('New password must be at least 8 characters.'); return }
    if (next !== confirm) { setErr('New passwords do not match.'); return }
    setSaving(true)
    try {
      const res = await changePassword(cur, next)
      // This request just bumped token_version server-side, invalidating the
      // token we called it with — persist the fresh one immediately or every
      // request after this one 401s (see task.md's mobile audit, P0 #2).
      if (res.session_token) await setToken(res.session_token)
      Alert.alert('Done', 'Password updated.')
      setCur(''); setNext(''); setConfirm('')
    } catch (e: any) { setErr(e.message || 'Could not change password') }
    finally { setSaving(false) }
  }

  function confirmDelete() {
    setDeleteErr('')
    if (!deletePassword) { setDeleteErr('Enter your password to confirm.'); return }
    Alert.alert(
      'Delete your account?',
      'This permanently deletes your account and everything in it — documents, pools, conversations, and API tokens. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete permanently', style: 'destructive',
          onPress: async () => {
            setDeleting(true)
            try { await deleteAccount(deletePassword); qc.clear() }
            catch (e: any) { setDeleteErr(e.message || 'Could not delete account'); setDeleting(false) }
          },
        },
      ],
    )
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
        <Button title="Log out" variant="danger" onPress={logoutAndClearCache} />
      </Card>

      <Card style={{ gap: 12, borderColor: colors.rose }}>
        <Text style={[styles.section, { color: colors.rose }]}>Danger zone</Text>
        {!showDelete ? (
          <Button title="Delete account" variant="danger" onPress={() => setShowDelete(true)} />
        ) : (
          <>
            <Text style={styles.deleteWarning}>
              This permanently deletes your account and everything in it — documents, pools, conversations, and
              API tokens. This cannot be undone.
            </Text>
            <Input
              label="Confirm your password"
              value={deletePassword}
              onChangeText={setDeletePassword}
              secureTextEntry
            />
            {deleteErr ? <Text style={styles.err}>{deleteErr}</Text> : null}
            <Button title="Permanently delete my account" variant="danger" onPress={confirmDelete} loading={deleting} />
            <Button title="Cancel" variant="secondary" onPress={() => { setShowDelete(false); setDeletePassword(''); setDeleteErr('') }} />
          </>
        )}
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
  deleteWarning: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft, lineHeight: 19 },
  version: { fontFamily: fonts.body, fontSize: 12, color: colors.inkMuted, textAlign: 'center', marginTop: 8 },
})
