import React from 'react'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import AppTabs from './AppTabs'
import BillingScreen from '../screens/BillingScreen'
import ConversationsScreen from '../screens/ConversationsScreen'
import AdminScreen from '../screens/AdminScreen'
import { colors, fonts } from '../theme/tokens'

const Stack = createNativeStackNavigator()

export default function AppStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="Tabs" component={AppTabs} options={{ headerShown: false }} />
      <Stack.Screen
        name="Billing"
        component={BillingScreen}
        options={{
          title: 'Billing & Plans',
          headerStyle: { backgroundColor: colors.canvas },
          headerTitleStyle: { fontFamily: fonts.displaySemi, color: colors.ink },
          headerTintColor: colors.indigo,
        }}
      />
      <Stack.Screen
        name="Conversations"
        component={ConversationsScreen}
        options={{
          title: 'Conversations',
          headerStyle: { backgroundColor: colors.canvas },
          headerTitleStyle: { fontFamily: fonts.displaySemi, color: colors.ink },
          headerTintColor: colors.indigo,
        }}
      />
      <Stack.Screen
        name="Admin"
        component={AdminScreen}
        options={{
          title: 'Admin',
          headerStyle: { backgroundColor: colors.canvas },
          headerTitleStyle: { fontFamily: fonts.displaySemi, color: colors.ink },
          headerTintColor: colors.indigo,
        }}
      />
    </Stack.Navigator>
  )
}
