import React, { useCallback, useEffect, useState } from 'react'
import { View, Text, StyleSheet, Pressable, ScrollView, RefreshControl, Modal, Switch, Alert } from 'react-native'
import { Users, ShieldCheck, HardDrive, FileText, Trash2, HardDriveUpload, Check, X } from 'lucide-react-native'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Input from '../components/ui/Input'
import { useAuthStore } from '../stores/authStore'
import * as admin from '../api/admin'
import { formatBytes, bytesToGb, gbToBytes } from '../utils/format'
import { colors, fonts, radius } from '../theme/tokens'

export default function AdminScreen() {
  const currentUser = useAuthStore((s) => s.user)
  const [stats, setStats] = useState<admin.AdminStats | null>(null)
  const [settings, setSettings] = useState<admin.AdminSettings>({ signups_enabled: true, default_storage_quota_bytes: 0 })
  const [users, setUsers] = useState<admin.AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [defaultGb, setDefaultGb] = useState('')

  const [quotaUser, setQuotaUser] = useState<admin.AdminUser | null>(null)
  const [quotaGb, setQuotaGb] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<admin.AdminUser | null>(null)
  const [busyId, setBusyId] = useState('')

  const load = useCallback(async () => {
    try {
      const [s, cfg, u] = await Promise.all([admin.fetchStats(), admin.fetchSettings(), admin.fetchUsers()])
      setStats(s)
      setSettings(cfg.settings)
      setDefaultGb(String(bytesToGb(cfg.settings.default_storage_quota_bytes)))
      setUsers(u.users || [])
    } catch (e: any) {
      Alert.alert('Could not load admin data', e.message || 'Please try again.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  function onRefresh() {
    setRefreshing(true)
    load()
  }

  const isSelf = (u: admin.AdminUser) => u.user_id === currentUser?.user_id

  async function toggleSignups(v: boolean) {
    const prev = settings.signups_enabled
    setSettings((s) => ({ ...s, signups_enabled: v }))
    try { await admin.updateSetting('signups_enabled', v) }
    catch (e: any) { setSettings((s) => ({ ...s, signups_enabled: prev })); Alert.alert('Could not update', e.message || 'Please try again.') }
  }

  async function saveDefaultQuota() {
    const gb = Number(defaultGb)
    if (!Number.isFinite(gb) || gb < 0) return
    try {
      const bytes = gbToBytes(gb)
      await admin.updateSetting('default_storage_quota_bytes', bytes)
      setSettings((s) => ({ ...s, default_storage_quota_bytes: bytes }))
    } catch (e: any) { Alert.alert('Could not update', e.message || 'Please try again.') }
  }

  async function toggleActive(u: admin.AdminUser) {
    setBusyId(u.user_id)
    try {
      const r = await admin.setActive(u.user_id, !u.is_active)
      setUsers((list) => list.map((x) => (x.user_id === u.user_id ? r : x)))
    } catch (e: any) { Alert.alert('Could not update', e.message || 'Please try again.') }
    finally { setBusyId('') }
  }

  async function toggleAdmin(u: admin.AdminUser) {
    setBusyId(u.user_id)
    try {
      const r = await admin.setAdmin(u.user_id, !u.is_admin)
      setUsers((list) => list.map((x) => (x.user_id === u.user_id ? r : x)))
    } catch (e: any) { Alert.alert('Could not update', e.message || 'Please try again.') }
    finally { setBusyId('') }
  }

  function openQuota(u: admin.AdminUser) {
    setQuotaUser(u)
    setQuotaGb(String(bytesToGb(u.storage_quota_bytes)))
  }

  async function saveQuota() {
    if (!quotaUser) return
    const gb = Number(quotaGb)
    if (!Number.isFinite(gb) || gb < 0) return
    try {
      const r = await admin.setQuota(quotaUser.user_id, gbToBytes(gb))
      setUsers((list) => list.map((x) => (x.user_id === r.user_id ? r : x)))
      setQuotaUser(null)
    } catch (e: any) { Alert.alert('Could not update quota', e.message || 'Please try again.') }
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    try {
      await admin.deleteUser(deleteTarget.user_id)
      setDeleteTarget(null)
      load()
    } catch (e: any) { Alert.alert('Could not delete', e.message || 'Please try again.') }
  }

  const statCards = stats ? [
    { label: 'Users', value: String(stats.total_users), sub: `${stats.active_users} active`, Icon: Users, color: 'indigo' as const },
    { label: 'Admins', value: String(stats.admin_users), Icon: ShieldCheck, color: 'pink' as const },
    { label: 'Storage used', value: formatBytes(stats.total_storage_used_bytes), Icon: HardDrive, color: 'emerald' as const },
    { label: 'Documents', value: String(stats.total_documents), sub: `${stats.total_tokens} tokens · ${stats.total_webhooks} webhooks`, Icon: FileText, color: 'amber' as const },
  ] : []

  return (
    <Screen scroll={false}>
      <ScrollView
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        contentContainerStyle={{ gap: 16, paddingBottom: 24 }}
      >
        <View>
          <Text style={styles.title}>Admin</Text>
          <Text style={styles.subtitle}>Metadata only — document contents are never accessible here.</Text>
        </View>

        {loading ? (
          <Text style={styles.hint}>Loading…</Text>
        ) : (
          <>
            <View style={styles.statGrid}>
              {statCards.map((c) => (
                <Card key={c.label} style={styles.statCard}>
                  <c.Icon color={colorFor(c.color)} size={18} />
                  <Text style={styles.statValue}>{c.value}</Text>
                  <Text style={styles.statLabel}>{c.label}</Text>
                  {c.sub ? <Text style={styles.statSub}>{c.sub}</Text> : null}
                </Card>
              ))}
            </View>

            <Card style={{ gap: 14 }}>
              <Text style={styles.section}>System settings</Text>
              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingLabel}>Public signups</Text>
                  <Text style={styles.settingHint}>Allow new accounts to register.</Text>
                </View>
                <Switch
                  value={settings.signups_enabled}
                  onValueChange={toggleSignups}
                  trackColor={{ true: colors.indigo, false: colors.border }}
                  thumbColor="#fff"
                />
              </View>
              <View style={styles.quotaRow}>
                <View style={{ flex: 1 }}>
                  <Input label="Default quota for new users (GB)" value={defaultGb} onChangeText={setDefaultGb} keyboardType="numeric" />
                </View>
                <Button title="Save" variant="secondary" onPress={saveDefaultQuota} style={styles.saveBtn} />
              </View>
              <Text style={styles.settingHint}>current: {formatBytes(settings.default_storage_quota_bytes)}</Text>
            </Card>

            <Card style={{ gap: 10 }} >
              <Text style={styles.section}>Users</Text>
              {users.map((u) => (
                <View key={u.user_id} style={styles.userRow}>
                  <View style={{ flex: 1, gap: 2 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <Text style={styles.userName} numberOfLines={1}>{u.username || u.email}</Text>
                      {u.is_admin ? <Badge label="admin" color="pink" /> : null}
                      {isSelf(u) ? <Badge label="you" color="slate" /> : null}
                    </View>
                    <Text style={styles.userMeta} numberOfLines={1}>{u.email}</Text>
                    <Text style={styles.userMeta}>
                      {formatBytes(u.storage_used_bytes)} / {formatBytes(u.storage_quota_bytes)} · {u.document_count} doc{u.document_count === 1 ? '' : 's'}
                    </Text>
                    <Badge label={u.is_active ? 'active' : 'disabled'} color={u.is_active ? 'emerald' : 'rose'} />
                  </View>
                  <View style={styles.userActions}>
                    <Pressable onPress={() => openQuota(u)} hitSlop={8} disabled={busyId === u.user_id}>
                      <HardDriveUpload color={colors.inkSoft} size={17} />
                    </Pressable>
                    <Pressable onPress={() => toggleAdmin(u)} hitSlop={8} disabled={isSelf(u) || busyId === u.user_id}>
                      <Text style={[styles.actionText, { color: u.is_admin ? colors.pink : colors.inkSoft, opacity: isSelf(u) ? 0.3 : 1 }]}>admin</Text>
                    </Pressable>
                    <Pressable onPress={() => toggleActive(u)} hitSlop={8} disabled={isSelf(u) || busyId === u.user_id}>
                      <Text style={[styles.actionText, { color: u.is_active ? colors.amber : colors.emerald, opacity: isSelf(u) ? 0.3 : 1 }]}>{u.is_active ? 'disable' : 'enable'}</Text>
                    </Pressable>
                    <Pressable onPress={() => setDeleteTarget(u)} hitSlop={8} disabled={isSelf(u)}>
                      <Trash2 color={colors.rose} size={17} style={{ opacity: isSelf(u) ? 0.3 : 1 }} />
                    </Pressable>
                  </View>
                </View>
              ))}
            </Card>
          </>
        )}
      </ScrollView>

      {/* Quota modal */}
      <Modal visible={!!quotaUser} transparent animationType="fade" onRequestClose={() => setQuotaUser(null)}>
        <Pressable style={styles.backdrop} onPress={() => setQuotaUser(null)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.sheetTitle}>Set storage quota</Text>
            <Text style={styles.settingHint} numberOfLines={1}>{quotaUser?.email}</Text>
            <Input label="Quota (GB)" value={quotaGb} onChangeText={setQuotaGb} keyboardType="numeric" style={{ marginTop: 10 }} />
            <View style={styles.sheetActions}>
              <Button title="Cancel" variant="secondary" onPress={() => setQuotaUser(null)} style={{ flex: 1 }} />
              <Button title="Save" onPress={saveQuota} style={{ flex: 1 }} />
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      {/* Delete confirm */}
      <Modal visible={!!deleteTarget} transparent animationType="fade" onRequestClose={() => setDeleteTarget(null)}>
        <Pressable style={styles.backdrop} onPress={() => setDeleteTarget(null)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.sheetTitle}>Delete user?</Text>
            <Text style={styles.settingHint}>
              Permanently delete <Text style={{ fontFamily: fonts.bodySemi, color: colors.ink }}>{deleteTarget?.email}</Text> and all their documents, pools, tokens, and webhooks. This can't be undone.
            </Text>
            <View style={styles.sheetActions}>
              <Button title="Cancel" variant="secondary" onPress={() => setDeleteTarget(null)} style={{ flex: 1 }} />
              <Button title="Delete" variant="danger" onPress={confirmDelete} style={{ flex: 1 }} />
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </Screen>
  )
}

function colorFor(c: 'indigo' | 'pink' | 'emerald' | 'amber') {
  return { indigo: colors.indigo, pink: colors.pink, emerald: colors.emerald, amber: colors.amber }[c]
}

const styles = StyleSheet.create({
  title: { fontFamily: fonts.display, fontSize: 24, color: colors.ink },
  subtitle: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft, marginTop: 2 },
  hint: { fontFamily: fonts.body, fontSize: 13, color: colors.inkMuted, textAlign: 'center', marginTop: 20 },
  statGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  statCard: { width: '47%', gap: 4 },
  statValue: { fontFamily: fonts.mono, fontSize: 20, color: colors.ink, marginTop: 6 },
  statLabel: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft },
  statSub: { fontFamily: fonts.body, fontSize: 11, color: colors.inkMuted },
  section: { fontFamily: fonts.displaySemi, fontSize: 16, color: colors.ink },
  settingRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  settingLabel: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.ink },
  settingHint: { fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft },
  quotaRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 8 },
  saveBtn: { marginBottom: 4 },
  userRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 10,
  },
  userName: { fontFamily: fonts.bodySemi, fontSize: 14, color: colors.ink, flexShrink: 1 },
  userMeta: { fontFamily: fonts.body, fontSize: 11, color: colors.inkMuted },
  userActions: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingTop: 2 },
  actionText: { fontFamily: fonts.bodySemi, fontSize: 12 },
  backdrop: { flex: 1, backgroundColor: 'rgba(30,27,46,0.4)', alignItems: 'center', justifyContent: 'center', padding: 20 },
  sheet: { width: '100%', maxWidth: 420, backgroundColor: colors.surface, borderRadius: radius.lg, padding: 20, gap: 4 },
  sheetTitle: { fontFamily: fonts.displaySemi, fontSize: 17, color: colors.ink, marginBottom: 4 },
  sheetActions: { flexDirection: 'row', gap: 10, marginTop: 16 },
})
