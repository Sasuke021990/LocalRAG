import React, { useRef, useState } from 'react'
import { View, TextInput, StyleSheet, FlatList, Pressable, Text, KeyboardAvoidingView, Platform } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Send, Sparkles } from 'lucide-react-native'
import ChatBubble, { ChatMsg } from '../components/ChatBubble'
import { streamQuery } from '../api/query'
import { colors, fonts, radius } from '../theme/tokens'

export default function ChatScreen() {
  const [history, setHistory] = useState<ChatMsg[]>([])
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const listRef = useRef<FlatList>(null)

  function update(idx: number, patch: Partial<ChatMsg>) {
    setHistory((h) => h.map((m, i) => (i === idx ? { ...m, ...patch } : m)))
  }

  function submit() {
    const q = text.trim()
    if (!q || loading) return
    setLoading(true); setText('')
    const idx = history.length
    setHistory((h) => [...h, { query: q, answer: '', reasoning: '', sources: [], streaming: true }])

    streamQuery(q, 10, 5, {
      onSources: (s) => update(idx, { sources: s }),
      onThinking: (t) => setHistory((h) => h.map((m, i) => (i === idx ? { ...m, reasoning: (m.reasoning || '') + t } : m))),
      onToken: (t) => setHistory((h) => h.map((m, i) => (i === idx ? { ...m, answer: m.answer + t } : m))),
      onRefusal: (mm) => update(idx, { answer: mm, refused: true }),
      onDone: (d) => update(idx, { answer: d.answer ?? undefined, reasoning: d.reasoning, refused: d.refused, streaming: false }),
      onError: () => { update(idx, { streaming: false }); },
    }).finally(() => setLoading(false))
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {history.length === 0 ? (
          <View style={styles.emptyWrap}>
            <View style={styles.emptyChip}><Sparkles color={colors.pink} size={26} /></View>
            <Text style={styles.emptyTitle}>Ask anything about your documents</Text>
            <Text style={styles.emptyBody}>Answers come only from your knowledge base, with citations.</Text>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={history}
            keyExtractor={(_, i) => String(i)}
            renderItem={({ item }) => <ChatBubble msg={item} />}
            contentContainerStyle={{ padding: 16 }}
            onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
          />
        )}

        <View style={styles.composer}>
          <TextInput
            style={styles.input}
            value={text}
            onChangeText={setText}
            placeholder="Ask a question…"
            placeholderTextColor={colors.inkMuted}
            multiline
          />
          <Pressable style={styles.send} onPress={submit} disabled={loading || !text.trim()}>
            <Send color="#fff" size={18} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.canvas },
  emptyWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 10 },
  emptyChip: { width: 56, height: 56, borderRadius: 18, backgroundColor: colors.pinkSoft, alignItems: 'center', justifyContent: 'center' },
  emptyTitle: { fontFamily: fonts.displaySemi, fontSize: 17, color: colors.ink, textAlign: 'center' },
  emptyBody: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft, textAlign: 'center' },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, padding: 12, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.surface },
  input: { flex: 1, maxHeight: 120, backgroundColor: colors.surfaceAlt, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14, paddingTop: 12, paddingBottom: 12, fontFamily: fonts.body, fontSize: 15, color: colors.ink },
  send: { width: 48, height: 48, borderRadius: radius.md, backgroundColor: colors.indigo, alignItems: 'center', justifyContent: 'center' },
})
