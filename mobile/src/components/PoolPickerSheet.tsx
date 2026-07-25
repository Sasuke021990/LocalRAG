import React, { useEffect, useState } from 'react'
import { Modal, View, Text, StyleSheet, Pressable, ScrollView, TextInput, Alert } from 'react-native'
import { Check, Plus } from 'lucide-react-native'
import { useAppTheme } from '../theme/ThemeContext'
import { fonts, radius } from '../theme/tokens'
import { createPool } from '../api/documents'
import type { Pool } from '../api/documents'

interface Props {
  visible: boolean
  pools: Pool[]
  selected: string
  allowEmpty?: boolean
  startInCreate?: boolean
  title?: string
  onChoose: (pool: string) => void
  onDismiss: () => void
  onCreated?: (pool: string) => void
}

/**
 * Select-an-existing-pool-or-create-a-new-one sheet — the mobile equivalent
 * of web's PoolPicker.vue, used by the Knowledge screen's upload flow and
 * move-to-pool flow. Distinct from PoolPickerModal (select-only, used by
 * Chat's "which pool to search" picker) since those two flows genuinely
 * don't need pool creation.
 */
export default function PoolPickerSheet({
  visible, pools, selected, allowEmpty = true, startInCreate = false, title = 'Choose a pool',
  onChoose, onDismiss, onCreated,
}: Props) {
  const { colors } = useAppTheme()
  const [creating, setCreating] = useState(startInCreate)
  const [newName, setNewName] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (visible) { setCreating(startInCreate); setNewName('') }
  }, [visible, startInCreate])

  async function confirmCreate() {
    const name = newName.trim()
    if (!name || busy) return
    setBusy(true)
    try {
      const res = await createPool(name)
      onCreated?.(res.pool)
      onChoose(res.pool)
      setNewName('')
      setCreating(false)
    } catch (e: any) {
      Alert.alert('Could not create pool', e?.message ?? 'Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const optionStyle = (on: boolean) => [
    styles.option,
    { borderColor: colors.border },
    on && { borderColor: colors.indigo, backgroundColor: colors.indigoSoft },
  ]

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onDismiss}>
      <Pressable style={[styles.backdrop, { backgroundColor: colors.backdrop }]} onPress={onDismiss}>
        <Pressable style={[styles.sheet, { backgroundColor: colors.surface }]} onPress={(e) => e.stopPropagation()}>
          <Text style={[styles.title, { color: colors.ink }]}>{title}</Text>

          <ScrollView style={{ maxHeight: 320 }} contentContainerStyle={{ gap: 8 }}>
            {allowEmpty && (
              <Pressable style={optionStyle(selected === '')} onPress={() => onChoose('')}>
                <Text style={[styles.optionLabel, { color: colors.ink }]}>— choose later (General) —</Text>
                {selected === '' ? <Check color={colors.indigo} size={16} /> : null}
              </Pressable>
            )}
            {pools.map((p) => (
              <Pressable key={p.name} style={optionStyle(selected === p.name)} onPress={() => onChoose(p.name)}>
                <Text style={[styles.optionLabel, { color: colors.ink }]} numberOfLines={1}>{p.name}</Text>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Text style={[styles.optionMeta, { color: colors.inkMuted }]}>{p.document_count} doc{p.document_count === 1 ? '' : 's'}</Text>
                  {selected === p.name ? <Check color={colors.indigo} size={16} /> : null}
                </View>
              </Pressable>
            ))}
          </ScrollView>

          {creating ? (
            <View style={styles.createRow}>
              <TextInput
                value={newName} onChangeText={setNewName} placeholder="New pool name"
                placeholderTextColor={colors.inkMuted}
                style={[styles.createInput, { borderColor: colors.border, color: colors.ink, backgroundColor: colors.surfaceAlt }]}
                autoFocus onSubmitEditing={confirmCreate}
              />
              <Pressable
                style={[styles.createConfirm, { backgroundColor: colors.indigo }]}
                onPress={confirmCreate}
                disabled={busy || !newName.trim()}
              >
                <Check color="#fff" size={18} />
              </Pressable>
            </View>
          ) : (
            <Pressable style={[styles.newPoolBtn, { borderColor: colors.indigo }]} onPress={() => setCreating(true)}>
              <Plus color={colors.indigo} size={16} />
              <Text style={[styles.newPoolText, { color: colors.indigo }]}>New pool</Text>
            </Pressable>
          )}
        </Pressable>
      </Pressable>
    </Modal>
  )
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  sheet: { width: '100%', maxWidth: 420, borderRadius: radius.lg, padding: 20, gap: 12 },
  title: { fontFamily: fonts.displaySemi, fontSize: 17, marginBottom: 4 },
  option: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 1, borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 12 },
  optionLabel: { fontFamily: fonts.bodyMedium, fontSize: 14, flexShrink: 1 },
  optionMeta: { fontFamily: fonts.body, fontSize: 12 },
  newPoolBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1, borderRadius: radius.md, paddingVertical: 10 },
  newPoolText: { fontFamily: fonts.bodyMedium, fontSize: 14 },
  createRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  createInput: { flex: 1, height: 44, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: 12, fontFamily: fonts.body, fontSize: 14 },
  createConfirm: { width: 44, height: 44, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
})
