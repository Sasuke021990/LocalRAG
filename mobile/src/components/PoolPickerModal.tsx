import React from 'react'
import { Modal, View, Text, StyleSheet, Pressable, ScrollView } from 'react-native'
import { Check } from 'lucide-react-native'
import { useAppTheme } from '../theme/ThemeContext'
import { fonts, radius } from '../theme/tokens'
import type { Pool } from '../api/documents'

interface Props {
  visible: boolean
  pools: Pool[]
  selected: string
  onChoose: (pool: string) => void
  onDismiss: () => void
}

// Pool-selection popup — shown on entering Chat / starting a new chat, and
// again via the header pill to switch pools mid-conversation. Dismissing
// without an explicit pick (backdrop tap) defaults to "All pools" rather
// than trapping the user, mirroring the web behavior.
export default function PoolPickerModal({ visible, pools, selected, onChoose, onDismiss }: Props) {
  const { colors } = useAppTheme()
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={() => onChoose(selected)}>
      <Pressable style={[styles.backdrop, { backgroundColor: colors.backdrop }]} onPress={() => onChoose(selected)}>
        <Pressable style={[styles.sheet, { backgroundColor: colors.surface }]} onPress={(e) => e.stopPropagation()}>
          <Text style={[styles.title, { color: colors.ink }]}>Choose a knowledge pool</Text>
          <Text style={[styles.subtitle, { color: colors.inkSoft }]}>Vaultly will search only this pool while you chat. You can switch anytime.</Text>

          <ScrollView style={{ maxHeight: 360 }} contentContainerStyle={{ gap: 8 }}>
            <Pressable
              style={[
                styles.option,
                { borderColor: colors.border },
                selected === '' && { borderColor: colors.indigo, backgroundColor: colors.indigoSoft },
              ]}
              onPress={() => onChoose('')}
            >
              <Text style={[styles.optionLabel, { color: colors.ink }]}>All pools</Text>
              {selected === '' ? <Check color={colors.indigo} size={16} /> : null}
            </Pressable>
            {pools.map((p) => (
              <Pressable
                key={p.name}
                style={[
                  styles.option,
                  { borderColor: colors.border },
                  selected === p.name && { borderColor: colors.indigo, backgroundColor: colors.indigoSoft },
                ]}
                onPress={() => onChoose(p.name)}
              >
                <Text style={[styles.optionLabel, { color: colors.ink }]} numberOfLines={1}>{p.name}</Text>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Text style={[styles.optionMeta, { color: colors.inkMuted }]}>{p.document_count} doc{p.document_count === 1 ? '' : 's'}</Text>
                  {selected === p.name ? <Check color={colors.indigo} size={16} /> : null}
                </View>
              </Pressable>
            ))}
            {pools.length === 0 ? (
              <Text style={[styles.empty, { color: colors.inkMuted }]}>No pools yet — "All pools" works fine until you create one.</Text>
            ) : null}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  )
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  sheet: { width: '100%', maxWidth: 420, borderRadius: radius.lg, padding: 20, gap: 4 },
  title: { fontFamily: fonts.displaySemi, fontSize: 17 },
  subtitle: { fontFamily: fonts.body, fontSize: 13, marginBottom: 14 },
  option: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 1, borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 12 },
  optionLabel: { fontFamily: fonts.bodyMedium, fontSize: 14, flexShrink: 1 },
  optionMeta: { fontFamily: fonts.body, fontSize: 12 },
  empty: { fontFamily: fonts.body, fontSize: 13, textAlign: 'center', paddingVertical: 12 },
})
