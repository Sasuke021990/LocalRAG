import React, { useMemo, useState } from 'react'
import { View, Text, StyleSheet, Pressable, ActivityIndicator } from 'react-native'
import Markdown from 'react-native-markdown-display'
import { Sparkles, SearchX, ChevronDown, FileText, FolderOpen } from 'lucide-react-native'
import Badge from './ui/Badge'
import { colors, fonts, radius } from '../theme/tokens'
import type { Source } from '../api/query'

export interface ChatMsg {
  query: string
  answer: string
  reasoning?: string
  sources: Source[]
  refused?: boolean
  streaming?: boolean
  queryPool?: string
}

export default function ChatBubble({ msg }: { msg: ChatMsg }) {
  const [showThinking, setShowThinking] = useState(false)

  // Unique source document names — a compact row instead of a full passage
  // list; multiple chunks commonly come from the same document.
  const sourceDocs = useMemo(
    () => [...new Set((msg.sources || []).map((s) => s.file_name).filter(Boolean))],
    [msg.sources],
  )
  const sourcePools = useMemo(
    () => [...new Set((msg.sources || []).map((s) => s.pool).filter(Boolean))],
    [msg.sources],
  )

  // Transient status shown before the first answer token arrives.
  const statusText = (() => {
    if (!msg.streaming || msg.answer || msg.refused) return ''
    const scope = msg.queryPool ? `the "${msg.queryPool}" pool` : 'your documents'
    return msg.sources.length ? `Analysing ${scope}…` : `Searching ${scope}…`
  })()

  return (
    <View style={{ gap: 10, marginBottom: 16 }}>
      {/* Query */}
      <View style={styles.queryWrap}>
        <View style={styles.queryBubble}><Text style={styles.queryText}>{msg.query}</Text></View>
      </View>

      {/* Answer */}
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <View style={[styles.avatar, { backgroundColor: msg.refused ? colors.amberSoft : colors.pinkSoft }]}>
          {msg.refused ? <SearchX color={colors.amber} size={16} /> : <Sparkles color={colors.pink} size={16} />}
        </View>
        <View style={{ flex: 1 }}>
          {msg.reasoning ? (
            <>
              <Pressable style={styles.toggle} onPress={() => setShowThinking((v) => !v)}>
                <Text style={styles.toggleText}>{msg.streaming ? 'Thinking…' : 'Thinking'}</Text>
              </Pressable>
              {showThinking ? <Text style={styles.thinking}>{msg.reasoning}</Text> : null}
            </>
          ) : null}

          {/* Which knowledge pool(s) this answer is grounded in */}
          {!msg.refused && sourcePools.length > 0 ? (
            <View style={styles.poolRow}>
              {sourcePools.map((p) => (
                <Badge key={p} label={p} color="indigo" icon={<FolderOpen color={colors.indigo} size={11} />} />
              ))}
            </View>
          ) : null}

          <View style={[styles.answerBubble, msg.refused && { backgroundColor: colors.amberSoft, borderColor: colors.amber }]}>
            {statusText ? (
              <View style={styles.statusRow}>
                <ActivityIndicator size="small" color={colors.inkSoft} />
                <Text style={styles.statusText}>{statusText}</Text>
              </View>
            ) : (
              <>
                <Markdown style={markdownStyle(msg.refused)}>{msg.answer || ''}</Markdown>
                {msg.streaming ? <Text style={styles.cursor}> ▍</Text> : null}
              </>
            )}

            {!msg.refused && sourceDocs.length > 0 ? (
              <View style={styles.sourcesRow}>
                <FileText color={colors.inkMuted} size={13} />
                {sourceDocs.map((doc) => (
                  <Badge key={doc} label={doc} color="slate" />
                ))}
              </View>
            ) : null}
          </View>
        </View>
      </View>
    </View>
  )
}

function markdownStyle(refused?: boolean) {
  const textColor = refused ? colors.inkSoft : colors.ink
  return StyleSheet.create({
    body: { fontFamily: fonts.body, fontSize: 14, color: textColor, lineHeight: 21 },
    paragraph: { marginTop: 0, marginBottom: 8 },
    strong: { fontFamily: fonts.bodySemi },
    em: { fontStyle: 'italic' },
    heading1: { fontFamily: fonts.displaySemi, fontSize: 18, color: colors.ink, marginTop: 4, marginBottom: 6 },
    heading2: { fontFamily: fonts.displaySemi, fontSize: 16, color: colors.ink, marginTop: 4, marginBottom: 6 },
    heading3: { fontFamily: fonts.displaySemi, fontSize: 15, color: colors.ink, marginTop: 4, marginBottom: 4 },
    bullet_list: { marginBottom: 8 },
    ordered_list: { marginBottom: 8 },
    list_item: { flexDirection: 'row', marginBottom: 2 },
    code_inline: {
      fontFamily: fonts.mono, fontSize: 13, backgroundColor: colors.surfaceAlt,
      borderWidth: 1, borderColor: colors.border, borderRadius: 4, paddingHorizontal: 4,
    },
    code_block: {
      fontFamily: fonts.mono, fontSize: 12, backgroundColor: colors.surfaceAlt,
      borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, padding: 10,
    },
    fence: {
      fontFamily: fonts.mono, fontSize: 12, backgroundColor: colors.surfaceAlt,
      borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, padding: 10,
    },
    blockquote: {
      borderLeftWidth: 3, borderLeftColor: colors.border, paddingLeft: 10,
      marginVertical: 6, backgroundColor: 'transparent',
    },
    hr: { backgroundColor: colors.border, height: 1, marginVertical: 8 },
  })
}

const styles = StyleSheet.create({
  queryWrap: { alignItems: 'flex-end' },
  queryBubble: { backgroundColor: colors.indigoSoft, borderRadius: radius.lg, borderTopRightRadius: 4, paddingHorizontal: 14, paddingVertical: 9, maxWidth: '85%' },
  queryText: { fontFamily: fonts.body, fontSize: 14, color: colors.ink },
  avatar: { width: 30, height: 30, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  answerBubble: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, borderTopLeftRadius: 4, padding: 12 },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  toggleText: { fontFamily: fonts.bodySemi, fontSize: 12, color: colors.inkSoft },
  thinking: { fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft, backgroundColor: colors.surfaceAlt, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, padding: 10, marginTop: 6, marginBottom: 6 },
  poolRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 6 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  statusText: { fontFamily: fonts.body, fontSize: 13, fontStyle: 'italic', color: colors.inkSoft },
  cursor: { color: colors.pink, fontSize: 16 },
  sourcesRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border },
})
