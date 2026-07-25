import React from 'react'
import { View, Text, StyleSheet, Pressable } from 'react-native'
import { FileText, FolderInput } from 'lucide-react-native'
import { useAppTheme } from '../theme/ThemeContext'
import { fonts, radius } from '../theme/tokens'
import type { Doc } from '../api/documents'

interface Props {
  doc: Doc
  // Omit for read-only contexts (e.g. Home's "recent documents" list).
  onMove?: (doc: Doc) => void
}

export default function DocumentRow({ doc, onMove }: Props) {
  const { colors } = useAppTheme()
  return (
    <View style={styles.row}>
      <View style={[styles.chip, { backgroundColor: colors.indigoSoft }]}><FileText color={colors.indigo} size={18} /></View>
      <View style={{ flex: 1 }}>
        <Text style={[styles.name, { color: colors.ink }]} numberOfLines={1}>{doc.file_name}</Text>
        <Text style={[styles.meta, { color: colors.inkSoft }]}>{doc.chunk_count} chunks · pool: {doc.pool}</Text>
        {doc.summary ? <Text style={[styles.summary, { color: colors.inkSoft }]} numberOfLines={2}>{doc.summary}</Text> : null}
      </View>
      {doc.pool_assigned === false ? <Text style={[styles.needs, { color: colors.amber }]}>needs a pool</Text> : null}
      {onMove ? (
        // A real 40x40 tap target (not just hitSlop) -- at 18px-icon-plus-hitSlop
        // this sat right next to the destructive delete button with only a
        // few px between them, an easy mis-tap (task.md P1 #15).
        <Pressable onPress={() => onMove(doc)} style={styles.actionBtn} hitSlop={4}>
          <FolderInput color={colors.inkMuted} size={18} />
        </Pressable>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10 },
  chip: { width: 36, height: 36, borderRadius: radius.sm, alignItems: 'center', justifyContent: 'center' },
  name: { fontFamily: fonts.bodyMedium, fontSize: 14 },
  meta: { fontFamily: fonts.body, fontSize: 12 },
  summary: { fontFamily: fonts.body, fontSize: 12, marginTop: 2 },
  needs: { fontFamily: fonts.bodySemi, fontSize: 11 },
  actionBtn: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
})
