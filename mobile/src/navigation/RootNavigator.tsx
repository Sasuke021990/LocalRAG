import React, { useEffect } from 'react'
import { View, ActivityIndicator } from 'react-native'
import { useAuthStore } from '../stores/authStore'
import { colors } from '../theme/tokens'
import AuthStack from './AuthStack'
import AppStack from './AppStack'

export default function RootNavigator() {
  const { checked, user, hydrate } = useAuthStore()

  useEffect(() => {
    hydrate()
  }, [hydrate])

  if (!checked) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={colors.indigo} />
      </View>
    )
  }

  return user ? <AppStack /> : <AuthStack />
}
