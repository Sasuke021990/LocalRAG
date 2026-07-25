import React, { useCallback, useMemo, useState } from 'react'
import { View, Text, StyleSheet, Pressable, ScrollView, Modal } from 'react-native'
import { WebView } from 'react-native-webview'
import { useQuery } from '@tanstack/react-query'
import { useNavigation, useFocusEffect } from '@react-navigation/native'
import { Share2, Lock, ChevronDown, Check, Locate } from 'lucide-react-native'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
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
  const [highlightId, setHighlightId] = useState('')
  const [highlightSheetOpen, setHighlightSheetOpen] = useState(false)
  // Bumped by the Recenter button -- included in the WebView's key so
  // pressing it remounts the graph fresh (pan/zoom reset to identity, same
  // trick already used for repulsion/pool/highlight changes).
  const [resetToken, setResetToken] = useState(0)

  function selectPool(name: string) {
    setSelectedPool(name)
    setHighlightId('') // node ids are pool-scoped — a stale id from another pool would silently do nothing
  }

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
  const highlightedNode = graph.nodes.find((n) => n.id === highlightId)
  const html = useMemo(() => graphHtml(graph, repulsion, highlightId), [graph, repulsion, highlightId])

  // Bottom-tab screens stay mounted, so navigating back here won't refetch on
  // its own. Re-check the plan (a Billing upgrade in another tab must unlock
  // the graph) and the pool graph (a fresh upload adds nodes) every time this
  // tab regains focus.
  useFocusEffect(
    useCallback(() => {
      subQ.refetch()
      poolsQ.refetch()
      if (activePool) graphQ.refetch()
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activePool]),
  )

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
        <ScrollView horizontal showsHorizontalScrollIndicator={false}
          style={styles.chipsScroll} contentContainerStyle={styles.chips}>
          {pools.map((p) => {
            const on = p.name === activePool
            return (
              <Pressable key={p.name} onPress={() => selectPool(p.name)}
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

      <Pressable style={styles.highlightRow} onPress={() => hasGraph && setHighlightSheetOpen(true)} disabled={!hasGraph}>
        <Text style={styles.repLabel}>Highlight concept</Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
          <Text style={styles.highlightValue} numberOfLines={1}>{highlightedNode?.label || '— none —'}</Text>
          <ChevronDown color={colors.inkMuted} size={14} />
        </View>
      </Pressable>

      <Card style={{ flex: 1, padding: 0, overflow: 'hidden' }}>
        {hasGraph ? (
          <>
            <WebView
              key={`${activePool}-${repulsion}-${highlightId}-${resetToken}`}
              originWhitelist={['*']}
              source={{ html }}
              style={{ flex: 1, backgroundColor: colors.surface }}
              scrollEnabled={false}
            />
            <Pressable style={styles.recenterBtn} onPress={() => setResetToken((t) => t + 1)} hitSlop={8}>
              <Locate color={colors.indigo} size={18} />
            </Pressable>
          </>
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
          {graph.nodes.length} concept(s) · {graph.edges.length} link(s) · drag a node or pinch to zoom, tap to focus its links.
        </Text>
      )}

      <Modal visible={highlightSheetOpen} transparent animationType="fade" onRequestClose={() => setHighlightSheetOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setHighlightSheetOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.sheetTitle}>Highlight a concept</Text>
            <ScrollView style={{ maxHeight: 360 }} contentContainerStyle={{ gap: 8 }}>
              <Pressable
                style={[styles.option, highlightId === '' && styles.optionSelected]}
                onPress={() => { setHighlightId(''); setHighlightSheetOpen(false) }}
              >
                <Text style={styles.optionLabel}>— none —</Text>
                {highlightId === '' ? <Check color={colors.indigo} size={16} /> : null}
              </Pressable>
              {graph.nodes.map((n) => (
                <Pressable
                  key={n.id}
                  style={[styles.option, highlightId === n.id && styles.optionSelected]}
                  onPress={() => { setHighlightId(n.id); setHighlightSheetOpen(false) }}
                >
                  <Text style={styles.optionLabel} numberOfLines={1}>{n.label}</Text>
                  {highlightId === n.id ? <Check color={colors.indigo} size={16} /> : null}
                </Pressable>
              ))}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
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
  // A horizontal ScrollView in a flex column otherwise grows to fill the
  // vertical space (stealing it from the graph) and stretches its chip into a
  // giant pill — pin it to its content height and center the chips.
  chipsScroll: { flexGrow: 0, flexShrink: 0 },
  chips: { gap: 8, paddingVertical: 2, alignItems: 'center' },
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
  highlightRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: 12, paddingVertical: 10, backgroundColor: colors.surfaceAlt },
  highlightValue: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.ink, maxWidth: 180 },
  backdrop: { flex: 1, backgroundColor: 'rgba(30,27,46,0.4)', alignItems: 'center', justifyContent: 'center', padding: 20 },
  sheet: { width: '100%', maxWidth: 420, backgroundColor: colors.surface, borderRadius: radius.lg, padding: 20, gap: 4 },
  sheetTitle: { fontFamily: fonts.displaySemi, fontSize: 17, color: colors.ink, marginBottom: 10 },
  option: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 12 },
  optionSelected: { borderColor: colors.indigo, backgroundColor: colors.indigoSoft },
  optionLabel: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.ink, flexShrink: 1 },
  recenterBtn: { position: 'absolute', right: 12, bottom: 12, width: 38, height: 38, borderRadius: 19, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', shadowColor: '#000', shadowOpacity: 0.12, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 3 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8, padding: 24, minHeight: 320 },
  emptyTitle: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.ink },
  emptyBody: { fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft, textAlign: 'center' },
  hint: { fontFamily: fonts.body, fontSize: 11, color: colors.inkMuted, textAlign: 'center' },
  lockChip: { width: 48, height: 48, borderRadius: 16, backgroundColor: 'rgba(245,158,11,0.10)', alignItems: 'center', justifyContent: 'center' },
  lockTitle: { fontFamily: fonts.displaySemi, fontSize: 16, color: colors.ink, textAlign: 'center' },
  lockBody: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft, textAlign: 'center' },
})
