import React from 'react'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import LoginScreen from '../screens/auth/LoginScreen'
import SignupScreen from '../screens/auth/SignupScreen'
import ForgotPasswordScreen from '../screens/auth/ForgotPasswordScreen'

export type AuthStackParams = {
  Login: undefined
  Signup: undefined
  ForgotPassword: undefined
}

const Stack = createNativeStackNavigator<AuthStackParams>()

export default function AuthStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Login" component={LoginScreen} />
      <Stack.Screen name="Signup" component={SignupScreen} />
      <Stack.Screen name="ForgotPassword" component={ForgotPasswordScreen} />
    </Stack.Navigator>
  )
}
