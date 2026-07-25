import 'react-native-gesture-handler'
import React, { useCallback } from 'react'
import { View, Alert } from 'react-native'
import { StatusBar } from 'expo-status-bar'
import * as SplashScreen from 'expo-splash-screen'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { NavigationContainer } from '@react-navigation/native'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useFonts } from 'expo-font'
import { Sora_600SemiBold, Sora_700Bold } from '@expo-google-fonts/sora'
import { Inter_400Regular, Inter_500Medium, Inter_600SemiBold } from '@expo-google-fonts/inter'
import { JetBrainsMono_600SemiBold } from '@expo-google-fonts/jetbrains-mono'

import { colors } from './src/theme/tokens'
import RootNavigator from './src/navigation/RootNavigator'
import ErrorBoundary from './src/components/ErrorBoundary'
import OfflineBanner from './src/components/OfflineBanner'
import { setUnauthorizedHandler } from './src/api/client'
import { useAuthStore } from './src/stores/authStore'

SplashScreen.preventAutoHideAsync().catch(() => {})

const queryClient = new QueryClient()

// Global 401 handling: an expired/revoked session token used to leave the
// user stuck on a broken screen indefinitely, with no auto-logout or
// re-login prompt anywhere. Registered once here (not inside client.ts
// itself, to avoid a circular import with authStore.ts) so every API call
// app-wide gets this for free. The "was there actually a session to lose"
// check keeps a plain failed login attempt (also a 401) from popping an
// unnecessary "session expired" alert.
setUnauthorizedHandler(() => {
  const hadUser = !!useAuthStore.getState().user
  useAuthStore.getState().logout()
  queryClient.clear() // don't leave another user's cached documents/chat visible after a forced logout
  if (hadUser) Alert.alert('Session expired', 'Please sign in again.')
})

const navTheme = {
  dark: false,
  colors: {
    primary: colors.indigo,
    background: colors.canvas,
    card: colors.surface,
    text: colors.ink,
    border: colors.border,
    notification: colors.pink,
  },
}

export default function App() {
  const [fontsLoaded] = useFonts({
    Sora_600SemiBold,
    Sora_700Bold,
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    JetBrainsMono_600SemiBold,
  })

  const onReady = useCallback(async () => {
    if (fontsLoaded) await SplashScreen.hideAsync().catch(() => {})
  }, [fontsLoaded])

  if (!fontsLoaded) return <View style={{ flex: 1, backgroundColor: colors.canvas }} />

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <SafeAreaProvider>
          <NavigationContainer theme={navTheme as any} onReady={onReady}>
            <StatusBar style="dark" />
            <RootNavigator />
          </NavigationContainer>
          <OfflineBanner />
        </SafeAreaProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
