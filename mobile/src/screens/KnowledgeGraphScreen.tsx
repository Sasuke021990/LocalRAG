import React, { useCallback, useMemo, useState } from 'react'
import { View, Text, StyleSheet, Pressable, ScrollView, Modal } from 'react-native'
import { WebView } from 'react-native-webview'
import { useQuery } from '@tanstack/react-query'
import { useNavigation, useFocusEffect } from '@react-navigation/native'
import { Share2, Lock, ChevronDown, Check, Locate, RefreshCw } from 'lucide-react-native'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { fetchPools, fetchPoolGraph } from '../api/documents'
import { fetchSubscription } from '../api/billing'
import { graphHtml } from '../components/graphHtml'
import { useAppTheme } from '../theme/ThemeContext'
import { fonts, radius } from '../theme/tokens'

const REPULSION_PRESETS: { label: string; value: number }[] = [
  { label: 'Loose', value: 4 },
  { label: 'Medium', value: 9 },
  { label: 'Tight', value: 16 },
]

export default function KnowledgeGraphScreen() {
  const nav = useNavigation<any>()
  const { colors, scheme } = useAppTheme()
  const [selectedPool, setSelectedPool] = useState('')
  const [repulsion, setRepulsion] = useState(9)
  const [highlightId, setHighlightId] = useState('')
  const [highlightSheetOpen, setHighlightSheetOpen] = useState(false)
  // Bumped by the Recenter button -- included in the WebView's key so
  // pressing it remounts the graph fresh (pan/zoom reset to identity, same
  // trick already used for repulsion/pool/highlight changes).
  const [resetToken, setResetToken] = useState(0)
  const [refreshing, setRefreshing] = useState(false)

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
  const html = useMemo(() => graphHtml(graph, repulsion, highlightId, colors), [graph, repulsion, highlightId, colors])

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

  // scroll={false} below (the graph needs a fixed, non-scrolling layout for
  // its WebView) rules out RefreshControl, which requires a ScrollView --
  // use a manual button instead.
  async function onRefresh() {
    setRefreshing(true)
    await Promise.all([subQ.refetch(), poolsQ.refetch(), activePool ? graphQ.refetch() : Promise.resolve()])
    setRefreshing(false)
  }

  if (subQ.data && !allowed) {
    return (
      <Screen>
        <Header onRefresh={onRefresh} refreshing={refreshing} />
        <Card style={{ alignItems: 'center', gap: 12, paddingVertical: 32 }}>
          <View style={[styles.lockChip, { backgroundColor: colors.amberSoft }]}><Lock color={colors.amber} size={26} /></View>
          <Text style={[styles.lockTitle, { color: colors.ink }]}>The Knowledge Graph is a Pro feature</Text>
          <Text style={[styles.lockBody, { color: colors.inkSoft }]}>
            Upgrade to Pro to see how the concepts across your documents connect, as an interactive graph.
          </Text>
          <Button title="See plans" onPress={() => nav.navigate('Billing')} style={{ alignSelf: 'stretch' }} />
        </Card>
      </Screen>
    )
  }

  return (
    <Screen scroll={false} contentStyle={{ gap: 12 }}>
      <Header onRefresh={onRefresh} refreshing={refreshing} />

      {pools.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false}
          style={styles.chipsScroll} contentContainerStyle={styles.chips}>
          {pools.map((p) => {
            const on = p.name === activePool
            return (
              <Pressable key={p.name} onPress={() => selectPool(p.name)}
                style={[
                  styles.chip,
                  { borderColor: colors.border, backgroundColor: colors.surface },
                  on && { backgroundColor: colors.indigo, borderColor: colors.indigo },
                ]}>
                <Text style={[styles.chipText, { color: on ? '#fff' : colors.inkSoft }]}>{p.name}</Text>
              </Pressable>
            )
          })}
        </ScrollView>
      )}

      <View style={styles.repRow}>
        <Text style={[styles.repLabel, { color: colors.inkSoft }]}>Repulsion</Text>
        {REPULSION_PRESETS.map((r) => {
          const on = r.value === repulsion
          return (
            <Pressable key={r.label} onPress={() => setRepulsion(r.value)}
              style={[
                styles.repBtn,
                { borderColor: colors.border },
                on && { backgroundColor: colors.indigoSoft, borderColor: colors.indigo },
              ]}>
              <Text style={[styles.repText, { color: on ? colors.indigo : colors.inkSoft }]}>{r.label}</Text>
            </Pressable>
          )
        })}
      </View>

      <Pressable
        style={[styles.highlightRow, { borderColor: colors.border, backgroundColor: colors.surfaceAlt }]}
        onPress={() => hasGraph && setHighlightSheetOpen(true)}
        disabled={!hasGraph}
      >
        <Text style={[styles.repLabel, { color: colors.inkSoft }]}>Highlight concept</Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
          <Text style={[styles.highlightValue, { color: colors.ink }]} numberOfLines={1}>{highlightedNode?.label || '— none —'}</Text>
          <ChevronDown color={colors.inkMuted} size={14} />
        </View>
      </Pressable>

      <Card style={{ flex: 1, padding: 0, overflow: 'hidden' }}>
        {hasGraph ? (
          <>
            <WebView
              key={`${activePool}-${repulsion}-${highlightId}-${resetToken}-${scheme}`}
              originWhitelist={['*']}
              source={{ html }}
              style={{ flex: 1, backgroundColor: colors.surface }}
              scrollEnabled={false}
            />
            <Pressable
              style={[styles.recenterBtn, { backgroundColor: colors.surface, borderColor: colors.border }]}
              onPress={() => setResetToken((t) => t + 1)}
              hitSlop={8}
            >
              <Locate color={colors.indigo} size={18} />
            </Pressable>
          </>
        ) : (
          <View style={styles.empty}>
            <Share2 color={colors.inkMuted} size={30} />
            <Text style={[styles.emptyTitle, { color: colors.ink }]}>
              {graphQ.isLoading ? 'Loading graph…' : 'No graph for this pool yet'}
            </Text>
            {!graphQ.isLoading && (
              <Text style={[styles.emptyBody, { color: colors.inkSoft }]}>
                Graphs are built automatically when you upload documents. Only files added after this feature
                launched are included.
              </Text>
            )}
          </View>
        )}
      </Card>

      {hasGraph && (
        <Text style={[styles.hint, { color: colors.inkMuted }]}>
          {graph.nodes.length} concept(s) · {graph.edges.length} link(s) · drag a node or pinch to zoom, tap to focus its links.
        </Text>
      )}

      <Modal visible={highlightSheetOpen} transparent animationType="fade" onRequestClose={() => setHighlightSheetOpen(false)}>
        <Pressable style={[styles.backdrop, { backgroundColor: colors.backdrop }]} onPress={() => setHighlightSheetOpen(false)}>
          <Pressable style={[styles.sheet, { backgroundColor: colors.surface }]} onPress={(e) => e.stopPropagation()}>
            <Text style={[styles.sheetTitle, { color: colors.ink }]}>Highlight a concept</Text>
            <ScrollView style={{ maxHeight: 360 }} contentContainerStyle={{ gap: 8 }}>
              <Pressable
                style={[
                  styles.option,
                  { borderColor: colors.border },
                  highlightId === '' && { borderColor: colors.indigo, backgroundColor: colors.indigoSoft },
                ]}
                onPress={() => { setHighlightId(''); setHighlightSheetOpen(false) }}
              >
                <Text style={[styles.optionLabel, { color: colors.ink }]}>— none —</Text>
                {highlightId === '' ? <Check color={colors.indigo} size={16} /> : null}
              </Pressable>
              {graph.nodes.map((n) => (
                <Pressable
                  key={n.id}
                  style={[
                    styles.option,
                    { borderColor: colors.border },
                    highlightId === n.id && { borderColor: colors.indigo, backgroundColor: colors.indigoSoft },
                  ]}
                  onPress={() => { setHighlightId(n.id); setHighlightSheetOpen(false) }}
                >
                  <Text style={[styles.optionLabel, { color: colors.ink }]} numberOfLines={1}>{n.label}</Text>
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

function Header({ onRefresh, refreshing }: { onRefresh: () => void; refreshing: boolean }) {
  const { colors } = useAppTheme()
  return (
    <View style={styles.header}>
      <View style={[styles.headerChip, { backgroundColor: colors.indigoSoft }]}><Share2 color={colors.indigo} size={20} /></View>
      <View style={{ flex: 1 }}>
        <Text style={[styles.title, { color: colors.ink }]}>Knowledge Graph</Text>
        <Text style={[styles.subtitle, { color: colors.inkSoft }]}>Concepts and relationships across a pool.</Text>
      </View>
      <Pressable onPress={onRefresh} disabled={refreshing} hitSlop={10} style={styles.refreshBtn}>
        <RefreshCw color={colors.inkSoft} size={18} style={refreshing ? { opacity: 0.4 } : undefined} />
      </Pressable>
    </View>
  )
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  headerChip: { width: 40, height: 40, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  title: { fontFamily: fonts.display, fontSize: 22 },
  subtitle: { fontFamily: fonts.body, fontSize: 12 },
  refreshBtn: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  // A horizontal ScrollView in a flex column otherwise grows to fill the
  // vertical space (stealing it from the graph) and stretches its chip into a
  // giant pill — pin it to its content height and center the chips.
  chipsScroll: { flexGrow: 0, flexShrink: 0 },
  chips: { gap: 8, paddingVertical: 2, alignItems: 'center' },
  chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 999, borderWidth: 1 },
  chipText: { fontFamily: fonts.bodyMedium, fontSize: 13 },
  repRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  repLabel: { fontFamily: fonts.bodyMedium, fontSize: 12, marginRight: 4 },
  repBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 10, borderWidth: 1 },
  repText: { fontFamily: fonts.bodyMedium, fontSize: 12 },
  highlightRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 1, borderRadius: radius.md, paddingHorizontal: 12, paddingVertical: 10 },
  highlightValue: { fontFamily: fonts.bodyMedium, fontSize: 13, maxWidth: 180 },
  backdrop: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  sheet: { width: '100%', maxWidth: 420, borderRadius: radius.lg, padding: 20, gap: 4 },
  sheetTitle: { fontFamily: fonts.displaySemi, fontSize: 17, marginBottom: 10 },
  option: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 1, borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 12 },
  optionLabel: { fontFamily: fonts.bodyMedium, fontSize: 14, flexShrink: 1 },
  recenterBtn: { position: 'absolute', right: 12, bottom: 12, width: 38, height: 38, borderRadius: 19, borderWidth: 1, alignItems: 'center', justifyContent: 'center', shadowColor: '#000', shadowOpacity: 0.12, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 3 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8, padding: 24, minHeight: 320 },
  emptyTitle: { fontFamily: fonts.bodyMedium, fontSize: 14 },
  emptyBody: { fontFamily: fonts.body, fontSize: 12, textAlign: 'center' },
  hint: { fontFamily: fonts.body, fontSize: 11, textAlign: 'center' },
  lockChip: { width: 48, height: 48, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  lockTitle: { fontFamily: fonts.displaySemi, fontSize: 16, textAlign: 'center' },
  lockBody: { fontFamily: fonts.body, fontSize: 13, textAlign: 'center' },
})
