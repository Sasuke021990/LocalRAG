import React from 'react'
import { Modal, View, Text, StyleSheet, Pressable, ScrollView } from 'react-native'
import { Check } from 'lucide-react-native'
import { colors, fonts, radius } from '../theme/tokens'
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
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={() => onChoose(selected)}>
      <Pressable style={styles.backdrop} onPress={() => onChoose(selected)}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <Text style={styles.title}>Choose a knowledge pool</Text>
          <Text style={styles.subtitle}>Vaultly will search only this pool while you chat. You can switch anytime.</Text>

          <ScrollView style={{ maxHeight: 360 }} contentContainerStyle={{ gap: 8 }}>
            <Pressable
              style={[styles.option, selected === '' && styles.optionSelected]}
              onPress={() => onChoose('')}
            >
              <Text style={styles.optionLabel}>All pools</Text>
              {selected === '' ? <Check color={colors.indigo} size={16} /> : null}
            </Pressable>
            {pools.map((p) => (
              <Pressable
                key={p.name}
                style={[styles.option, selected === p.name && styles.optionSelected]}
                onPress={() => onChoose(p.name)}
              >
                <Text style={styles.optionLabel} numberOfLines={1}>{p.name}</Text>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Text style={styles.optionMeta}>{p.document_count} doc{p.document_count === 1 ? '' : 's'}</Text>
                  {selected === p.name ? <Check color={colors.indigo} size={16} /> : null}
                </View>
              </Pressable>
            ))}
            {pools.length === 0 ? (
              <Text style={styles.empty}>No pools yet — "All pools" works fine until you create one.</Text>
            ) : null}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  )
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(30,27,46,0.4)', alignItems: 'center', justifyContent: 'center', padding: 20 },
  sheet: { width: '100%', maxWidth: 420, backgroundColor: colors.surface, borderRadius: radius.lg, padding: 20, gap: 4 },
  title: { fontFamily: fonts.displaySemi, fontSize: 17, color: colors.ink },
  subtitle: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft, marginBottom: 14 },
  option: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 12 },
  optionSelected: { borderColor: colors.indigo, backgroundColor: colors.indigoSoft },
  optionLabel: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.ink, flexShrink: 1 },
  optionMeta: { fontFamily: fonts.body, fontSize: 12, color: colors.inkMuted },
  empty: { fontFamily: fonts.body, fontSize: 13, color: colors.inkMuted, textAlign: 'center', paddingVertical: 12 },
})
