import React from 'react'
import { StyleSheet, ScrollView, View, ViewStyle, RefreshControl } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { colors } from '../theme/tokens'

interface Props {
  children: React.ReactNode
  scroll?: boolean
  contentStyle?: ViewStyle
  // Pull-to-refresh -- only meaningful when scroll (the default) is true,
  // since RefreshControl needs a ScrollView to attach to. Pass both to get
  // the standard gesture for free; omit either to skip it (e.g. a screen
  // with its own non-scrolling layout, like KnowledgeGraphScreen's fixed
  // WebView, uses a manual refresh button instead).
  refreshing?: boolean
  onRefresh?: () => void
}

export default function Screen({ children, scroll = true, contentStyle, refreshing, onRefresh }: Props) {
  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      {scroll ? (
        <ScrollView
          contentContainerStyle={[styles.content, contentStyle]}
          keyboardShouldPersistTaps="handled"
          refreshControl={
            onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={colors.indigo} /> : undefined
          }
        >
          {children}
        </ScrollView>
      ) : (
        <View style={[styles.content, { flex: 1 }, contentStyle]}>{children}</View>
      )}
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.canvas },
  content: { padding: 20, gap: 16 },
})
