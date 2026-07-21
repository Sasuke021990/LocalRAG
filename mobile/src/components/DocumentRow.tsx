import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import { FileText } from 'lucide-react-native'
import { colors, fonts, radius } from '../theme/tokens'
import type { Doc } from '../api/documents'

export default function DocumentRow({ doc }: { doc: Doc }) {
  return (
    <View style={styles.row}>
      <View style={styles.chip}><FileText color={colors.indigo} size={18} /></View>
      <View style={{ flex: 1 }}>
        <Text style={styles.name} numberOfLines={1}>{doc.file_name}</Text>
        <Text style={styles.meta}>{doc.chunk_count} chunks · pool: {doc.pool}</Text>
      </View>
      {doc.pool_assigned === false ? <Text style={styles.needs}>needs a pool</Text> : null}
    </View>
  )
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10 },
  chip: { width: 36, height: 36, borderRadius: radius.sm, backgroundColor: colors.indigoSoft, alignItems: 'center', justifyContent: 'center' },
  name: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.ink },
  meta: { fontFamily: fonts.body, fontSize: 12, color: colors.inkSoft },
  needs: { fontFamily: fonts.bodySemi, fontSize: 11, color: colors.amber },
})
