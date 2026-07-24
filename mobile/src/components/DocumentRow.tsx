import React from 'react'
import { View, Text, StyleSheet, Pressable } from 'react-native'
import { FileText, FolderInput } from 'lucide-react-native'
import { colors, fonts, radius } from '../theme/tokens'
import type { Doc } from '../api/documents'

interface Props {
  doc: Doc
  // Omit for read-only contexts (e.g. Home's "recent documents" list).
  onMove?: (doc: Doc) => void
}

export default function DocumentRow({ doc, onMove }: Props) {
  return (
    <View style={styles.row}>
      <View style={styles.chip}><FileText color={colors.indigo} size={18} /></View>
      <View style={{ flex: 1 }}>
        <Text style={styles.name} numberOfLines={1}>{doc.file_name}</Text>
        <Text style={styles.meta}>{doc.chunk_count} chunks · pool: {doc.pool}</Text>
        {doc.summary ? <Text style={styles.summary} numberOfLines={2}>{doc.summary}</Text> : null}
      </View>
      {doc.pool_assigned === false ? <Text style={styles.needs}>needs a pool</Text> : null}
      {onMove ? (
        <Pressable onPress={() => onMove(doc)} hitSlop={10}>
          <FolderInput color={colors.inkMuted} size={18} />
        </Pressable>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10 },
  chip: { width: 36, height: 36, borderRadius: radius.sm, backgroundColor: colors.indigoSoft, alignItems: 'center', justifyContent: 'center' },
  name: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.ink },
  meta: { fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft },
  summary: { fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft, marginTop: 2 },
  needs: { fontFamily: fonts.bodySemi, fontSize: 11, color: colors.amber },
})
