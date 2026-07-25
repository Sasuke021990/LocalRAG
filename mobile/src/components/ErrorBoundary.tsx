import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { AlertTriangle } from 'lucide-react-native'
import Button from './ui/Button'
import { colors, fonts } from '../theme/tokens'

interface Props {
  children: React.ReactNode
}

interface State {
  error: Error | null
}

// Catches render-time errors anywhere below it in the tree so a single bad
// render doesn't brick the whole app with a permanent white screen (task.md
// P1 #12). Class component because getDerivedStateFromError/componentDidCatch
// have no hook equivalent.
export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    if (__DEV__) console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  reset = () => this.setState({ error: null })

  render() {
    if (this.state.error) {
      return (
        <SafeAreaView style={styles.safe}>
          <View style={styles.wrap}>
            <View style={styles.chip}><AlertTriangle color={colors.rose} size={26} /></View>
            <Text style={styles.title}>Something went wrong</Text>
            <Text style={styles.body}>
              An unexpected error occurred. You can try again — if it keeps happening, restarting the app usually helps.
            </Text>
            <Button title="Try again" onPress={this.reset} style={{ alignSelf: 'stretch' }} />
          </View>
        </SafeAreaView>
      )
    }
    return this.props.children
  }
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.canvas },
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 32 },
  chip: {
    width: 56, height: 56, borderRadius: 18, backgroundColor: 'rgba(244,63,94,0.10)',
    alignItems: 'center', justifyContent: 'center', marginBottom: 4,
  },
  title: { fontFamily: fonts.displaySemi, fontSize: 18, color: colors.ink },
  body: { fontFamily: fonts.body, fontSize: 14, color: colors.inkSoft, textAlign: 'center', lineHeight: 20 },
})
