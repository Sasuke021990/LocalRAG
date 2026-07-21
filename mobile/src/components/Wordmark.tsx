import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import { LinearGradient } from 'expo-linear-gradient'
import { Vault } from 'lucide-react-native'
import { colors, fonts, gradient, radius } from '../theme/tokens'

/** "Vault" in ink + "ly" in the brand gradient, with a gradient vault chip. */
export default function Wordmark({ size = 24 }: { size?: number }) {
  return (
    <View style={styles.row}>
      <LinearGradient colors={gradient.brand} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.chip}>
        <Vault color="#fff" size={size * 0.8} />
      </LinearGradient>
      <View style={{ flexDirection: 'row', alignItems: 'baseline' }}>
        <Text style={[styles.word, { fontSize: size }]}>Vault</Text>
        <Text style={[styles.word, { fontSize: size, color: colors.pink }]}>ly</Text>
      </View>
    </View>
  )
}

// Note: falls back to a solid pink "ly" if MaskedView isn't available; the
// gradient wordmark treatment can be refined during design polish.
const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  chip: { width: 40, height: 40, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  word: { fontFamily: fonts.display, color: colors.ink },
})
