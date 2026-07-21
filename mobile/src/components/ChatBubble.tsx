import React, { useState } from 'react'
import { View, Text, StyleSheet, Pressable } from 'react-native'
import { Sparkles, SearchX, ChevronDown } from 'lucide-react-native'
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
}

export default function ChatBubble({ msg }: { msg: ChatMsg }) {
  const [showSources, setShowSources] = useState(false)
  const [showThinking, setShowThinking] = useState(false)

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

          <View style={[styles.answerBubble, msg.refused && { backgroundColor: colors.amberSoft, borderColor: colors.amber }]}>
            <Text style={[styles.answerText, msg.refused && { color: colors.inkSoft }]}>
              {msg.answer}{msg.streaming ? ' ▍' : ''}
            </Text>

            {!msg.refused && msg.sources.length > 0 ? (
              <View style={{ marginTop: 10, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 }}>
                <Pressable style={styles.toggle} onPress={() => setShowSources((v) => !v)}>
                  <ChevronDown color={colors.inkSoft} size={14} />
                  <Text style={styles.toggleText}>{msg.sources.length} source{msg.sources.length > 1 ? 's' : ''}</Text>
                </Pressable>
                {showSources ? msg.sources.map((s, i) => (
                  <View key={i} style={styles.source}>
                    <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center', marginBottom: 2, flexWrap: 'wrap' }}>
                      <Text style={styles.sourceName} numberOfLines={1}>{s.file_name}</Text>
                      <Badge label={`pool: ${s.pool}`} color="pink" />
                    </View>
                    <Text style={styles.sourceSnippet} numberOfLines={3}>{s.content}</Text>
                  </View>
                )) : null}
              </View>
            ) : null}
          </View>
        </View>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  queryWrap: { alignItems: 'flex-end' },
  queryBubble: { backgroundColor: colors.indigoSoft, borderRadius: radius.lg, borderTopRightRadius: 4, paddingHorizontal: 14, paddingVertical: 9, maxWidth: '85%' },
  queryText: { fontFamily: fonts.body, fontSize: 14, color: colors.ink },
  avatar: { width: 30, height: 30, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  answerBubble: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, borderTopLeftRadius: 4, padding: 12 },
  answerText: { fontFamily: fonts.body, fontSize: 14, color: colors.ink, lineHeight: 21 },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  toggleText: { fontFamily: fonts.bodySemi, fontSize: 12, color: colors.inkSoft },
  thinking: { fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft, backgroundColor: colors.surfaceAlt, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, padding: 10, marginTop: 6, marginBottom: 6 },
  source: { backgroundColor: colors.surfaceAlt, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.border, padding: 10, marginTop: 8 },
  sourceName: { fontFamily: fonts.bodySemi, fontSize: 12, color: colors.ink, flexShrink: 1 },
  sourceSnippet: { fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft },
})
