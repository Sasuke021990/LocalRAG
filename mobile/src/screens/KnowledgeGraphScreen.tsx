import React, { useMemo, useState } from 'react'
import { View, Text, StyleSheet, Pressable, ScrollView } from 'react-native'
import { WebView } from 'react-native-webview'
import { useQuery } from '@tanstack/react-query'
import { useNavigation } from '@react-navigation/native'
import { Share2, Lock } from 'lucide-react-native'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { fetchPools, fetchPoolGraph } from '../api/documents'
import { fetchSubscription } from '../api/billing'
import { graphHtml } from '../components/graphHtml'
import { colors, fonts, radius } from '../theme/tokens'

const REPULSION_PRESETS: { label: string; value: number }[] = [
  { label: 'Loose', value: 4 },
  { label: 'Medium', value: 9 },
  { label: 'Tight', value: 16 },
]

export default function KnowledgeGraphScreen() {
  const nav = useNavigation<any>()
  const [selectedPool, setSelectedPool] = useState('')
  const [repulsion, setRepulsion] = useState(9)

  const subQ = useQuery({ queryKey: ['subscription'], queryFn: fetchSubscription })
  const poolsQ = useQuery({ queryKey: ['pools'], queryFn: fetchPools })

  const allowed = subQ.data ? subQ.data.features?.knowledge_graph !== false : true
  const pools = poolsQ.data?.pools ?? []
  const activePool = selectedPool || pools[0]?.name || ''

  const graphQ = useQuery({
    queryKey: ['graph', activePool],
    queryFn: () => fetchPoolGraph(activePool),
    enabled: allowed && !!activePool,
  })

  const graph = graphQ.data ?? { nodes: [], edges: [] }
  const hasGraph = graph.nodes.length > 0
  const html = useMemo(() => graphHtml(graph, repulsion), [graph, repulsion])

  if (subQ.data && !allowed) {
    return (
      <Screen>
        <Header />
        <Card style={{ alignItems: 'center', gap: 12, paddingVertical: 32 }}>
          <View style={styles.lockChip}><Lock color={colors.amber} size={26} /></View>
          <Text style={styles.lockTitle}>The Knowledge Graph is a Pro feature</Text>
          <Text style={styles.lockBody}>
            Upgrade to Pro to see how the concepts across your documents connect, as an interactive graph.
          </Text>
          <Button title="See plans" onPress={() => nav.navigate('Billing')} style={{ alignSelf: 'stretch' }} />
        </Card>
      </Screen>
    )
  }

  return (
    <Screen scroll={false} contentStyle={{ gap: 12 }}>
      <Header />

      {pools.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
          {pools.map((p) => {
            const on = p.name === activePool
            return (
              <Pressable key={p.name} onPress={() => setSelectedPool(p.name)}
                style={[styles.chip, on && styles.chipOn]}>
                <Text style={[styles.chipText, on && styles.chipTextOn]}>{p.name}</Text>
              </Pressable>
            )
          })}
        </ScrollView>
      )}

      <View style={styles.repRow}>
        <Text style={styles.repLabel}>Repulsion</Text>
        {REPULSION_PRESETS.map((r) => {
          const on = r.value === repulsion
          return (
            <Pressable key={r.label} onPress={() => setRepulsion(r.value)}
              style={[styles.repBtn, on && styles.repBtnOn]}>
              <Text style={[styles.repText, on && styles.repTextOn]}>{r.label}</Text>
            </Pressable>
          )
        })}
      </View>

      <Card style={{ flex: 1, padding: 0, overflow: 'hidden' }}>
        {hasGraph ? (
          <WebView
            key={`${activePool}-${repulsion}`}
            originWhitelist={['*']}
            source={{ html }}
            style={{ flex: 1, backgroundColor: colors.surface }}
            scrollEnabled={false}
          />
        ) : (
          <View style={styles.empty}>
            <Share2 color={colors.inkMuted} size={30} />
            <Text style={styles.emptyTitle}>
              {graphQ.isLoading ? 'Loading graph…' : 'No graph for this pool yet'}
            </Text>
            {!graphQ.isLoading && (
              <Text style={styles.emptyBody}>
                Graphs are built automatically when you upload documents. Only files added after this feature
                launched are included.
              </Text>
            )}
          </View>
        )}
      </Card>

      {hasGraph && (
        <Text style={styles.hint}>
          {graph.nodes.length} concept(s) · {graph.edges.length} link(s) · drag a node, tap to focus its links.
        </Text>
      )}
    </Screen>
  )
}

function Header() {
  return (
    <View style={styles.header}>
      <View style={styles.headerChip}><Share2 color={colors.indigo} size={20} /></View>
      <View>
        <Text style={styles.title}>Knowledge Graph</Text>
        <Text style={styles.subtitle}>Concepts and relationships across a pool.</Text>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  headerChip: { width: 40, height: 40, borderRadius: radius.md, backgroundColor: colors.indigoSoft, alignItems: 'center', justifyContent: 'center' },
  title: { fontFamily: fonts.display, fontSize: 22, color: colors.ink },
  subtitle: { fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft },
  chips: { gap: 8, paddingVertical: 2 },
  chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 999, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface },
  chipOn: { backgroundColor: colors.indigo, borderColor: colors.indigo },
  chipText: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.inkSoft },
  chipTextOn: { color: '#fff' },
  repRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  repLabel: { fontFamily: fonts.bodyMedium, fontSize: 12, color: colors.inkSoft, marginRight: 4 },
  repBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 10, borderWidth: 1, borderColor: colors.border },
  repBtnOn: { backgroundColor: colors.indigoSoft, borderColor: colors.indigo },
  repText: { fontFamily: fonts.bodyMedium, fontSize: 12, color: colors.inkSoft },
  repTextOn: { color: colors.indigo },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8, padding: 24, minHeight: 320 },
  emptyTitle: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.ink },
  emptyBody: { fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft, textAlign: 'center' },
  hint: { fontFamily: fonts.body, fontSize: 11, color: colors.inkMuted, textAlign: 'center' },
  lockChip: { width: 48, height: 48, borderRadius: 16, backgroundColor: 'rgba(245,158,11,0.10)', alignItems: 'center', justifyContent: 'center' },
  lockTitle: { fontFamily: fonts.displaySemi, fontSize: 16, color: colors.ink, textAlign: 'center' },
  lockBody: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft, textAlign: 'center' },
})
