import React, { useMemo, useState } from 'react'
import { View, Text, StyleSheet, Pressable, ActivityIndicator } from 'react-native'
import * as Clipboard from 'expo-clipboard'
import Markdown from 'react-native-markdown-display'
import { Sparkles, SearchX, TriangleAlert, ChevronDown, FileText, FolderOpen, Copy, Check, RotateCw } from 'lucide-react-native'
import Badge from './ui/Badge'
import { useAppTheme } from '../theme/ThemeContext'
import { fonts, radius, type ColorTokens } from '../theme/tokens'
import type { Source } from '../api/query'

export interface ChatMsg {
  query: string
  answer: string
  reasoning?: string
  sources: Source[]
  refused?: boolean
  streaming?: boolean
  queryPool?: string
  // Set when the request itself failed — distinct from `refused` (a normal
  // grounded "nothing relevant found" answer). Rendered as an explicit
  // error state instead of an empty bubble.
  error?: string
}

export default function ChatBubble({ msg, onRetry }: { msg: ChatMsg; onRetry?: () => void }) {
  const [showThinking, setShowThinking] = useState(false)
  const [copied, setCopied] = useState(false)
  const { colors } = useAppTheme()

  async function copyAnswer() {
    await Clipboard.setStringAsync(msg.answer)
    // Inline confirmation instead of a toast/alert — copying is a low-stakes
    // action and an interrupting dialog would be heavier than the action.
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

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

  const mdStyle = useMemo(() => markdownStyle(colors, msg.refused), [colors, msg.refused])

  // Transient status shown before the first answer token arrives.
  const statusText = (() => {
    if (!msg.streaming || msg.answer || msg.refused || msg.error) return ''
    const scope = msg.queryPool ? `the "${msg.queryPool}" pool` : 'your documents'
    return msg.sources.length ? `Analysing ${scope}…` : `Searching ${scope}…`
  })()

  return (
    <View style={{ gap: 10, marginBottom: 16 }}>
      {/* Query */}
      <View style={styles.queryWrap}>
        <View style={[styles.queryBubble, { backgroundColor: colors.indigoSoft }]}>
          <Text style={[styles.queryText, { color: colors.ink }]}>{msg.query}</Text>
        </View>
      </View>

      {/* Answer */}
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <View style={[styles.avatar, { backgroundColor: msg.error ? colors.roseSoft : msg.refused ? colors.amberSoft : colors.pinkSoft }]}>
          {msg.error
            ? <TriangleAlert color={colors.rose} size={16} />
            : msg.refused ? <SearchX color={colors.amber} size={16} /> : <Sparkles color={colors.pink} size={16} />}
        </View>
        <View style={{ flex: 1 }}>
          {msg.reasoning ? (
            <>
              <Pressable style={styles.toggle} onPress={() => setShowThinking((v) => !v)}>
                <Text style={[styles.toggleText, { color: colors.inkSoft }]}>{msg.streaming ? 'Thinking…' : 'Thinking'}</Text>
              </Pressable>
              {showThinking ? (
                <Text style={[styles.thinking, { color: colors.inkSoft, backgroundColor: colors.surfaceAlt, borderColor: colors.border }]}>
                  {msg.reasoning}
                </Text>
              ) : null}
            </>
          ) : null}

          {/* Which knowledge pool(s) this answer is grounded in */}
          {!msg.refused && !msg.error && sourcePools.length > 0 ? (
            <View style={styles.poolRow}>
              {sourcePools.map((p) => (
                <Badge key={p} label={p} color="indigo" icon={<FolderOpen color={colors.indigo} size={11} />} />
              ))}
            </View>
          ) : null}

          <View style={[
            styles.answerBubble,
            { backgroundColor: colors.surface, borderColor: colors.border },
            msg.refused && { backgroundColor: colors.amberSoft, borderColor: colors.amber },
            msg.error ? { backgroundColor: colors.roseSoft, borderColor: colors.rose } : null,
          ]}>
            {msg.error ? (
              <Text style={[styles.errorText, { color: colors.rose }]}>{msg.error}</Text>
            ) : statusText ? (
              <View style={styles.statusRow}>
                <ActivityIndicator size="small" color={colors.inkSoft} />
                <Text style={[styles.statusText, { color: colors.inkSoft }]}>{statusText}</Text>
              </View>
            ) : (
              <>
                <Markdown style={mdStyle}>{msg.answer || ''}</Markdown>
                {msg.streaming ? <Text style={[styles.cursor, { color: colors.pink }]}> ▍</Text> : null}
              </>
            )}

            {!msg.refused && !msg.error && sourceDocs.length > 0 ? (
              <View style={[styles.sourcesRow, { borderTopColor: colors.border }]}>
                <FileText color={colors.inkMuted} size={13} />
                {sourceDocs.map((doc) => (
                  <Badge key={doc} label={doc} color="slate" />
                ))}
              </View>
            ) : null}
          </View>

          {/* Message actions (task.md P2 #22). Hidden while streaming —
              copying a half-written answer or retrying mid-flight are both
              nonsense; the composer's Stop button covers that window. */}
          {!msg.streaming && (msg.answer || msg.error) ? (
            <View style={styles.actionsRow}>
              {msg.answer ? (
                <Pressable
                  style={styles.actionBtn}
                  onPress={copyAnswer}
                  hitSlop={8}
                  accessibilityRole="button"
                  accessibilityLabel="Copy answer"
                >
                  {copied
                    ? <Check color={colors.emerald} size={14} />
                    : <Copy color={colors.inkMuted} size={14} />}
                  <Text style={[styles.actionText, { color: copied ? colors.emerald : colors.inkMuted }]}>
                    {copied ? 'Copied' : 'Copy'}
                  </Text>
                </Pressable>
              ) : null}
              {/* Retry is offered only on a turn that failed or was stopped.
                  A completed answer was already persisted server-side, so
                  re-running it would append a duplicate turn to the stored
                  conversation rather than replace it. */}
              {onRetry && (msg.error || !msg.answer) ? (
                <Pressable
                  style={styles.actionBtn}
                  onPress={onRetry}
                  hitSlop={8}
                  accessibilityRole="button"
                  accessibilityLabel="Retry this question"
                >
                  <RotateCw color={colors.indigo} size={14} />
                  <Text style={[styles.actionText, { color: colors.indigo }]}>Retry</Text>
                </Pressable>
              ) : null}
            </View>
          ) : null}
        </View>
      </View>
    </View>
  )
}

function markdownStyle(colors: ColorTokens, refused?: boolean) {
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
      fontFamily: fonts.mono, fontSize: 13, color: colors.ink, backgroundColor: colors.surfaceAlt,
      borderWidth: 1, borderColor: colors.border, borderRadius: 4, paddingHorizontal: 4,
    },
    code_block: {
      fontFamily: fonts.mono, fontSize: 12, color: colors.ink, backgroundColor: colors.surfaceAlt,
      borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, padding: 10,
    },
    fence: {
      fontFamily: fonts.mono, fontSize: 12, color: colors.ink, backgroundColor: colors.surfaceAlt,
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
  queryBubble: { borderRadius: radius.lg, borderTopRightRadius: 4, paddingHorizontal: 14, paddingVertical: 9, maxWidth: '85%' },
  queryText: { fontFamily: fonts.body, fontSize: 14 },
  avatar: { width: 30, height: 30, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  answerBubble: { borderWidth: 1, borderRadius: radius.lg, borderTopLeftRadius: 4, padding: 12 },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  toggleText: { fontFamily: fonts.bodySemi, fontSize: 12 },
  thinking: { fontFamily: fonts.body, fontSize: 12, borderWidth: 1, borderRadius: radius.sm, padding: 10, marginTop: 6, marginBottom: 6 },
  poolRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 6 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  statusText: { fontFamily: fonts.body, fontSize: 13, fontStyle: 'italic' },
  errorText: { fontFamily: fonts.body, fontSize: 14, lineHeight: 20 },
  cursor: { fontSize: 16 },
  sourcesRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginTop: 10, paddingTop: 10, borderTopWidth: 1 },
  actionsRow: { flexDirection: 'row', alignItems: 'center', gap: 14, marginTop: 6, paddingLeft: 2 },
  // Roomy tap target without visually enlarging the control (task.md P1 #15
  // called out the same problem on the document rows).
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingVertical: 6, paddingRight: 4 },
  actionText: { fontFamily: fonts.bodyMedium, fontSize: 12 },
})
