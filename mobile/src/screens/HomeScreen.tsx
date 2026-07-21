import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import { useQuery } from '@tanstack/react-query'
import { FileText, Boxes } from 'lucide-react-native'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import UsageRing from '../components/UsageRing'
import DocumentRow from '../components/DocumentRow'
import { fetchDocuments, fetchPools } from '../api/documents'
import { useAuthStore } from '../stores/authStore'
import { colors, fonts } from '../theme/tokens'

export default function HomeScreen() {
  const email = useAuthStore((s) => s.user?.email || '')
  const docsQ = useQuery({ queryKey: ['documents'], queryFn: fetchDocuments })
  const poolsQ = useQuery({ queryKey: ['pools'], queryFn: fetchPools })

  const docs = docsQ.data?.documents ?? []
  const recent = [...docs].sort((a, b) => (b.processed_at || '').localeCompare(a.processed_at || '')).slice(0, 5)

  return (
    <Screen>
      <Text style={styles.hi}>Welcome back,</Text>
      <Text style={styles.name}>{email.split('@')[0]}</Text>

      <Card style={{ alignItems: 'center' }}><UsageRing /></Card>

      <View style={{ flexDirection: 'row', gap: 12 }}>
        <Card style={styles.stat}>
          <View style={[styles.chip, { backgroundColor: colors.indigoSoft }]}><FileText color={colors.indigo} size={18} /></View>
          <Text style={styles.statNum}>{docs.length}</Text>
          <Text style={styles.statLabel}>Documents</Text>
        </Card>
        <Card style={styles.stat}>
          <View style={[styles.chip, { backgroundColor: colors.pinkSoft }]}><Boxes color={colors.pink} size={18} /></View>
          <Text style={styles.statNum}>{poolsQ.data?.pools.length ?? 0}</Text>
          <Text style={styles.statLabel}>Pools</Text>
        </Card>
      </View>

      <Card>
        <Text style={styles.section}>Recent documents</Text>
        {recent.length === 0 ? (
          <Text style={styles.empty}>Your knowledge base is empty — upload a document to get started.</Text>
        ) : recent.map((d) => <DocumentRow key={d.key} doc={d} />)}
      </Card>
    </Screen>
  )
}

const styles = StyleSheet.create({
  hi: { fontFamily: fonts.body, fontSize: 15, color: colors.inkSoft },
  name: { fontFamily: fonts.display, fontSize: 26, color: colors.ink, marginBottom: 4, textTransform: 'capitalize' },
  stat: { flex: 1 },
  chip: { width: 36, height: 36, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  statNum: { fontFamily: fonts.mono, fontSize: 26, color: colors.ink },
  statLabel: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft },
  section: { fontFamily: fonts.displaySemi, fontSize: 16, color: colors.ink, marginBottom: 6 },
  empty: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft, paddingVertical: 8 },
})
