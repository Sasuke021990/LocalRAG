import 'react-native-gesture-handler'
import React, { useCallback } from 'react'
import { View } from 'react-native'
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

SplashScreen.preventAutoHideAsync().catch(() => {})

const queryClient = new QueryClient()

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
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider>
        <NavigationContainer theme={navTheme as any} onReady={onReady}>
          <StatusBar style="dark" />
          <RootNavigator />
        </NavigationContainer>
      </SafeAreaProvider>
    </QueryClientProvider>
  )
}
