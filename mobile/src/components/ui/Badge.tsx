import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import { useAppTheme } from '../../theme/ThemeContext'
import { fonts, radius, type ColorTokens } from '../../theme/tokens'

type Color = 'indigo' | 'pink' | 'emerald' | 'amber' | 'rose' | 'slate'

function tone(colors: ColorTokens, c: Color): { bg: string; fg: string } {
  switch (c) {
    case 'pink': return { bg: colors.pinkSoft, fg: colors.pink }
    case 'emerald': return { bg: colors.emeraldSoft, fg: colors.emerald }
    case 'amber': return { bg: colors.amberSoft, fg: colors.amber }
    case 'rose': return { bg: colors.roseSoft, fg: colors.rose }
    case 'slate': return { bg: colors.slateSoft, fg: colors.inkSoft }
    default: return { bg: colors.indigoSoft, fg: colors.indigo }
  }
}

export default function Badge({ label, color = 'indigo', icon }: { label: string; color?: Color; icon?: React.ReactNode }) {
  const { colors } = useAppTheme()
  const c = tone(colors, color)
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
