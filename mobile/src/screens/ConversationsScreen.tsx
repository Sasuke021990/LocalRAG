import React, { useEffect, useState } from 'react'
import { View, Text, StyleSheet, FlatList, Pressable, TextInput, Alert } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import { Plus, Pencil, Trash2, Check, X, MessageSquare } from 'lucide-react-native'
import Screen from '../components/Screen'
import { useChatStore } from '../stores/chatStore'
import { colors, fonts, radius } from '../theme/tokens'
import { timeAgo } from '../utils/format'
import type { ConversationSummary } from '../api/chat'

export default function ConversationsScreen() {
  const navigation = useNavigation<any>()
  const conversations = useChatStore((s) => s.conversations)
  const conversationsLoading = useChatStore((s) => s.conversationsLoading)
  const loadConversations = useChatStore((s) => s.loadConversations)
  const openConversation = useChatStore((s) => s.openConversation)
  const renameConversation = useChatStore((s) => s.renameConversation)
  const deleteConversation = useChatStore((s) => s.deleteConversation)
  const newChat = useChatStore((s) => s.newChat)

  const [editingId, setEditingId] = useState('')
  const [draft, setDraft] = useState('')

  useEffect(() => { loadConversations() }, [])

  async function open(c: ConversationSummary) {
    if (editingId) return
    try {
      await openConversation(c.id)
      navigation.goBack()
    } catch (e: any) {
      Alert.alert('Could not open conversation', e.message || 'Please try again.')
    }
  }

  function startEdit(c: ConversationSummary) {
    setEditingId(c.id)
    setDraft(c.title)
  }

  async function commitEdit(c: ConversationSummary) {
    const title = draft.trim()
    setEditingId('')
    if (title && title !== c.title) {
      try { await renameConversation(c.id, title) }
      catch (e: any) { Alert.alert('Could not rename', e.message || 'Please try again.') }
    }
  }

  function confirmDelete(c: ConversationSummary) {
    Alert.alert('Delete conversation?', `"${c.title}" and its messages will be removed permanently.`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive', onPress: async () => {
          try { await deleteConversation(c.id) }
          catch (e: any) { Alert.alert('Could not delete', e.message || 'Please try again.') }
        },
      },
    ])
  }

  function startNewChat() {
    newChat()
    navigation.goBack()
  }

  return (
    <Screen scroll={false}>
      <Pressable style={styles.newChat} onPress={startNewChat}>
        <Plus color="#fff" size={18} />
        <Text style={styles.newChatText}>New chat</Text>
      </Pressable>

      {conversationsLoading ? (
        <Text style={styles.hint}>Loading…</Text>
      ) : conversations.length === 0 ? (
        <View style={styles.emptyWrap}>
          <MessageSquare color={colors.inkMuted} size={22} />
          <Text style={styles.hint}>No conversations yet — send a message to start one.</Text>
        </View>
      ) : (
        <FlatList
          data={conversations}
          keyExtractor={(c) => c.id}
          contentContainerStyle={{ gap: 4, paddingBottom: 20 }}
          renderItem={({ item }) => (
            <View style={styles.row}>
              {editingId === item.id ? (
                <View style={styles.editRow}>
                  <TextInput
                    value={draft}
                    onChangeText={setDraft}
                    autoFocus
                    style={styles.editInput}
                    onSubmitEditing={() => commitEdit(item)}
                  />
                  <Pressable onPress={() => commitEdit(item)} hitSlop={8}><Check color={colors.emerald} size={18} /></Pressable>
                  <Pressable onPress={() => setEditingId('')} hitSlop={8}><X color={colors.inkMuted} size={18} /></Pressable>
                </View>
              ) : (
                <>
                  <Pressable style={styles.rowMain} onPress={() => open(item)}>
                    <Text style={styles.rowTitle} numberOfLines={1}>{item.title}</Text>
                    <Text style={styles.rowPreview} numberOfLines={1}>{item.preview || 'No messages yet'}</Text>
                    <Text style={styles.rowMeta}>{timeAgo(item.updated_at)}{item.pool ? ` · ${item.pool}` : ''}</Text>
                  </Pressable>
                  <View style={styles.actions}>
                    <Pressable onPress={() => startEdit(item)} hitSlop={8}><Pencil color={colors.inkMuted} size={16} /></Pressable>
                    <Pressable onPress={() => confirmDelete(item)} hitSlop={8}><Trash2 color={colors.inkMuted} size={16} /></Pressable>
                  </View>
                </>
              )}
            </View>
          )}
        />
      )}
    </Screen>
  )
}

const styles = StyleSheet.create({
  newChat: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: colors.indigo, borderRadius: radius.md, paddingVertical: 13, marginBottom: 16,
  },
  newChatText: { fontFamily: fonts.bodySemi, fontSize: 14, color: '#fff' },
  hint: { fontFamily: fonts.body, fontSize: 13, color: colors.inkMuted, textAlign: 'center', marginTop: 12 },
  emptyWrap: { alignItems: 'center', gap: 8, marginTop: 40 },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderWidth: 1, borderColor: colors.border, borderRadius: radius.md,
    paddingHorizontal: 14, paddingVertical: 12, backgroundColor: colors.surface,
  },
  rowMain: { flex: 1, gap: 2 },
  rowTitle: { fontFamily: fonts.bodySemi, fontSize: 14, color: colors.ink },
  rowPreview: { fontFamily: fonts.body, fontSize: 12, color: colors.inkMuted },
  rowMeta: { fontFamily: fonts.body, fontSize: 11, color: colors.inkMuted },
  actions: { flexDirection: 'row', gap: 12, paddingLeft: 8 },
  editRow: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 },
  editInput: {
    flex: 1, fontFamily: fonts.body, fontSize: 14, color: colors.ink,
    borderWidth: 1, borderColor: colors.indigo, borderRadius: radius.sm, paddingHorizontal: 10, paddingVertical: 6,
  },
})
