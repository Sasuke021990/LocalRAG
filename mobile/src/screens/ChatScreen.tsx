import React, { useEffect, useRef, useState } from 'react'
import { View, TextInput, StyleSheet, FlatList, Pressable, Text, KeyboardAvoidingView, Platform } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useNavigation } from '@react-navigation/native'
import { useQuery } from '@tanstack/react-query'
import { Send, Sparkles, History, FolderOpen, ChevronDown } from 'lucide-react-native'
import ChatBubble from '../components/ChatBubble'
import PoolPickerModal from '../components/PoolPickerModal'
import { useChatStore } from '../stores/chatStore'
import { fetchPools } from '../api/documents'
import { colors, fonts, radius } from '../theme/tokens'

export default function ChatScreen() {
  const navigation = useNavigation<any>()
  const history = useChatStore((s) => s.history)
  const loading = useChatStore((s) => s.loading)
  const pool = useChatStore((s) => s.pool)
  const poolChosen = useChatStore((s) => s.poolChosen)
  const choosePool = useChatStore((s) => s.choosePool)
  const submit = useChatStore((s) => s.submit)

  const [text, setText] = useState('')
  const [pickerOpen, setPickerOpen] = useState(false)
  const listRef = useRef<FlatList>(null)

  const poolsQ = useQuery({ queryKey: ['pools'], queryFn: fetchPools })
  const pools = poolsQ.data?.pools ?? []

  // Prompt for a pool as soon as the user lands in Chat (or starts a new
  // one) without having picked yet — mirrors web's auto-open behavior.
  useEffect(() => {
    if (!poolChosen) setPickerOpen(true)
  }, [poolChosen])

  function send() {
    const q = text.trim()
    if (!q || loading) return
    setText('')
    submit(q)
  }

  function choose(p: string) {
    choosePool(p)
    setPickerOpen(false)
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.header}>
          <Pressable style={styles.poolPill} onPress={() => setPickerOpen(true)}>
            <FolderOpen color={colors.indigo} size={14} />
            <Text style={styles.poolPillText} numberOfLines={1}>{pool || 'All pools'}</Text>
            <ChevronDown color={colors.indigo} size={14} />
          </Pressable>
          <Pressable style={styles.historyBtn} onPress={() => navigation.navigate('Conversations')} hitSlop={8}>
            <History color={colors.inkSoft} size={20} />
          </Pressable>
        </View>

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
          <Pressable style={styles.send} onPress={send} disabled={loading || !text.trim()}>
            <Send color="#fff" size={18} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>

      <PoolPickerModal
        visible={pickerOpen}
        pools={pools}
        selected={pool}
        onChoose={choose}
        onDismiss={() => setPickerOpen(false)}
      />
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.canvas },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border,
    backgroundColor: colors.surface,
  },
  poolPill: {
    flexDirection: 'row', alignItems: 'center', gap: 6, flexShrink: 1,
    borderWidth: 1, borderColor: colors.border, borderRadius: radius.md,
    paddingHorizontal: 12, paddingVertical: 7, backgroundColor: colors.indigoSoft,
  },
  poolPillText: { fontFamily: fonts.bodySemi, fontSize: 13, color: colors.indigo, flexShrink: 1 },
  historyBtn: { padding: 4 },
  emptyWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 10 },
  emptyChip: { width: 56, height: 56, borderRadius: 18, backgroundColor: colors.pinkSoft, alignItems: 'center', justifyContent: 'center' },
  emptyTitle: { fontFamily: fonts.displaySemi, fontSize: 17, color: colors.ink, textAlign: 'center' },
  emptyBody: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft, textAlign: 'center' },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, padding: 12, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.surface },
  input: { flex: 1, maxHeight: 120, backgroundColor: colors.surfaceAlt, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14, paddingTop: 12, paddingBottom: 12, fontFamily: fonts.body, fontSize: 15, color: colors.ink },
  send: { width: 48, height: 48, borderRadius: radius.md, backgroundColor: colors.indigo, alignItems: 'center', justifyContent: 'center' },
})
