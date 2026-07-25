import React, { useCallback, useMemo, useState } from 'react'
import { View, Text, StyleSheet, Pressable } from 'react-native'
import { WebView } from 'react-native-webview'
import { useQuery } from '@tanstack/react-query'
import { useNavigation, useFocusEffect } from '@react-navigation/native'
import { Share2, Lock, Locate, RefreshCw } from 'lucide-react-native'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { fetchUserGraph } from '../api/documents'
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
  const [repulsion, setRepulsion] = useState(9)
  // Bumped by the Recenter button -- included in the WebView's key so
  // pressing it remounts the graph fresh (pan/zoom reset to identity, same
  // trick already used for repulsion changes).
  const [resetToken, setResetToken] = useState(0)
  const [refreshing, setRefreshing] = useState(false)

  const subQ = useQuery({ queryKey: ['subscription'], queryFn: fetchSubscription })
  const allowed = subQ.data ? subQ.data.features?.knowledge_graph !== false : true

  // One graph across every pool. Concepts aren't pool-specific, and the old
  // per-pool view meant a document uploaded to one pool was invisible while
  // any other pool was selected -- so there's no pool selector here at all.
  const graphQ = useQuery({
    queryKey: ['graph'],
    queryFn: fetchUserGraph,
    enabled: allowed,
  })

  const graph = graphQ.data ?? { nodes: [], edges: [] }
  const hasGraph = graph.nodes.length > 0
  // No initial focus: tapping a node in the WebView still focuses it and its
  // links (that interaction lives in graphHtml.ts) -- the picker that drove
  // it from the outside is gone, not the capability.
  const html = useMemo(() => graphHtml(graph, repulsion, '', colors), [graph, repulsion, colors])

  // Bottom-tab screens stay mounted, so navigating back here won't refetch on
  // its own. Re-check the plan (a Billing upgrade in another tab must unlock
  // the graph) and the graph itself (a fresh upload adds nodes) every time
  // this tab regains focus.
  useFocusEffect(
    useCallback(() => {
      subQ.refetch()
      graphQ.refetch()
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []),
  )

  // scroll={false} below (the graph needs a fixed, non-scrolling layout for
  // its WebView) rules out RefreshControl, which requires a ScrollView --
  // use a manual button instead.
  async function onRefresh() {
    setRefreshing(true)
    await Promise.all([subQ.refetch(), graphQ.refetch()])
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

      <Card style={{ flex: 1, padding: 0, overflow: 'hidden' }}>
        {hasGraph ? (
          <>
            <WebView
              key={`${repulsion}-${resetToken}-${scheme}`}
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
              {graphQ.isLoading ? 'Loading graph…' : 'No graph yet'}
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
        <Text style={[styles.subtitle, { color: colors.inkSoft }]}>Concepts and relationships across your documents.</Text>
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
  repRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  repLabel: { fontFamily: fonts.bodyMedium, fontSize: 12, marginRight: 4 },
  repBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 10, borderWidth: 1 },
  repText: { fontFamily: fonts.bodyMedium, fontSize: 12 },
  recenterBtn: { position: 'absolute', right: 12, bottom: 12, width: 38, height: 38, borderRadius: 19, borderWidth: 1, alignItems: 'center', justifyContent: 'center', shadowColor: '#000', shadowOpacity: 0.12, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 3 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8, padding: 24, minHeight: 320 },
  emptyTitle: { fontFamily: fonts.bodyMedium, fontSize: 14 },
  emptyBody: { fontFamily: fonts.body, fontSize: 12, textAlign: 'center' },
  hint: { fontFamily: fonts.body, fontSize: 11, textAlign: 'center' },
  lockChip: { width: 48, height: 48, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  lockTitle: { fontFamily: fonts.displaySemi, fontSize: 16, textAlign: 'center' },
  lockBody: { fontFamily: fonts.body, fontSize: 13, textAlign: 'center' },
})
