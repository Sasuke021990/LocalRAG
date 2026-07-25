import React, { useCallback, useState } from 'react'
import { View, Text, StyleSheet, Pressable } from 'react-native'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigation, useFocusEffect } from '@react-navigation/native'
import { FileText, Boxes } from 'lucide-react-native'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import UsageRing from '../components/UsageRing'
import DocumentRow from '../components/DocumentRow'
import { fetchDocuments, fetchPools } from '../api/documents'
import { useAuthStore } from '../stores/authStore'
import { useAppTheme } from '../theme/ThemeContext'
import { fonts } from '../theme/tokens'

export default function HomeScreen() {
  const nav = useNavigation<any>()
  const qc = useQueryClient()
  const { colors } = useAppTheme()
  const email = useAuthStore((s) => s.user?.email || '')
  const docsQ = useQuery({ queryKey: ['documents'], queryFn: fetchDocuments })
  const poolsQ = useQuery({ queryKey: ['pools'], queryFn: fetchPools })
  const [refreshing, setRefreshing] = useState(false)

  const docs = docsQ.data?.documents ?? []
  const recent = [...docs].sort((a, b) => (b.processed_at || '').localeCompare(a.processed_at || '')).slice(0, 5)

  function goToKnowledge() {
    nav.navigate('Knowledge')
  }

  async function onRefresh() {
    setRefreshing(true)
    await Promise.all([qc.invalidateQueries({ queryKey: ['documents'] }), qc.invalidateQueries({ queryKey: ['pools'] })])
    setRefreshing(false)
  }

  // Documents/summaries can finish their background pass (task.md §1a/§1d)
  // while the user is elsewhere in the app -- refetch whenever Home regains
  // focus so a just-completed summary shows up without a manual pull.
  useFocusEffect(useCallback(() => { docsQ.refetch(); poolsQ.refetch() }, []))

  return (
    <Screen refreshing={refreshing} onRefresh={onRefresh}>
      <Text style={[styles.hi, { color: colors.inkSoft }]}>Welcome back,</Text>
      <Text style={[styles.name, { color: colors.ink }]}>{email.split('@')[0]}</Text>

      <Card style={{ alignItems: 'center' }}><UsageRing /></Card>

      <View style={{ flexDirection: 'row', gap: 12 }}>
        <Pressable style={styles.stat} onPress={goToKnowledge}>
          <Card>
            <View style={[styles.chip, { backgroundColor: colors.indigoSoft }]}><FileText color={colors.indigo} size={18} /></View>
            <Text style={[styles.statNum, { color: colors.ink }]}>{docs.length}</Text>
            <Text style={[styles.statLabel, { color: colors.inkSoft }]}>Documents</Text>
          </Card>
        </Pressable>
        <Pressable style={styles.stat} onPress={goToKnowledge}>
          <Card>
            <View style={[styles.chip, { backgroundColor: colors.pinkSoft }]}><Boxes color={colors.pink} size={18} /></View>
            <Text style={[styles.statNum, { color: colors.ink }]}>{poolsQ.data?.pools.length ?? 0}</Text>
            <Text style={[styles.statLabel, { color: colors.inkSoft }]}>Pools</Text>
          </Card>
        </Pressable>
      </View>

      <Card>
        <Text style={[styles.section, { color: colors.ink }]}>Recent documents</Text>
        {recent.length === 0 ? (
          <Text style={[styles.empty, { color: colors.inkSoft }]}>Your knowledge base is empty — upload a document to get started.</Text>
        ) : recent.map((d) => <DocumentRow key={d.key} doc={d} />)}
      </Card>
    </Screen>
  )
}

const styles = StyleSheet.create({
  hi: { fontFamily: fonts.body, fontSize: 15 },
  name: { fontFamily: fonts.display, fontSize: 26, marginBottom: 4, textTransform: 'capitalize' },
  stat: { flex: 1 },
  chip: { width: 36, height: 36, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  statNum: { fontFamily: fonts.mono, fontSize: 26 },
  statLabel: { fontFamily: fonts.body, fontSize: 13 },
  section: { fontFamily: fonts.displaySemi, fontSize: 16, marginBottom: 6 },
  empty: { fontFamily: fonts.body, fontSize: 13, paddingVertical: 8 },
})
