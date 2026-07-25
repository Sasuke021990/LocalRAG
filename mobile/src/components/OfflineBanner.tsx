import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useNetInfo } from '@react-native-community/netinfo'
import { WifiOff } from 'lucide-react-native'
import { colors, fonts } from '../theme/tokens'

// Renders a thin persistent strip whenever the device has no network
// connection, so airplane mode / a dead connection reads as "you're
// offline" instead of looking identical to every other silent failure
// (task.md P1 #13). isConnected is `null` until the first check resolves,
// so treat only an explicit `false` as offline -- never flash on startup.
export default function OfflineBanner() {
  const { isConnected } = useNetInfo()
  const insets = useSafeAreaInsets()

  if (isConnected !== false) return null

  return (
    <View style={[styles.bar, { paddingTop: insets.top + 6 }]} pointerEvents="none">
      <WifiOff color="#fff" size={14} />
      <Text style={styles.text}>You're offline — some things won't load</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  // Absolutely positioned overlay (not a layout sibling) so it never
  // double-applies the top safe-area inset that each screen's own
  // SafeAreaView (Screen.tsx, edges=['top']) already accounts for.
  bar: {
    position: 'absolute', top: 0, left: 0, right: 0, zIndex: 1000,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: colors.rose, paddingBottom: 8,
  },
  text: { fontFamily: fonts.bodyMedium, fontSize: 12, color: '#fff' },
})
