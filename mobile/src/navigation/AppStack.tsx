import React from 'react'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import AppTabs from './AppTabs'
import BillingScreen from '../screens/BillingScreen'
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
    </Stack.Navigator>
  )
}
