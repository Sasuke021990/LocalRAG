import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import { colors, fonts, radius } from '../../theme/tokens'

type Color = 'indigo' | 'pink' | 'emerald' | 'amber' | 'rose' | 'slate'

const map: Record<Color, { bg: string; fg: string }> = {
  indigo: { bg: colors.indigoSoft, fg: colors.indigo },
  pink: { bg: colors.pinkSoft, fg: colors.pink },
  emerald: { bg: colors.emeraldSoft, fg: colors.emerald },
  amber: { bg: colors.amberSoft, fg: colors.amber },
  rose: { bg: colors.roseSoft, fg: colors.rose },
  slate: { bg: 'rgba(107,104,128,0.12)', fg: colors.inkSoft },
}

export default function Badge({ label, color = 'indigo', icon }: { label: string; color?: Color; icon?: React.ReactNode }) {
  const c = map[color]
  return (
    <View style={[styles.pill, { backgroundColor: c.bg }, icon ? styles.pillWithIcon : null]}>
      {icon}
      <Text style={[styles.text, { color: c.fg }]}>{label}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  pill: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: radius.pill, alignSelf: 'flex-start' },
  pillWithIcon: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  text: { fontFamily: fonts.bodySemi, fontSize: 11 },
})
