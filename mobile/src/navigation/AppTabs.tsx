import React from 'react'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { Home, MessageSquare, FolderOpen, Settings } from 'lucide-react-native'
import { colors, fonts } from '../theme/tokens'
import HomeScreen from '../screens/HomeScreen'
import ChatScreen from '../screens/ChatScreen'
import KnowledgeScreen from '../screens/KnowledgeScreen'
import SettingsScreen from '../screens/SettingsScreen'

const Tab = createBottomTabNavigator()

export default function AppTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.indigo,
        tabBarInactiveTintColor: colors.inkMuted,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border, height: 88, paddingTop: 8 },
        tabBarLabelStyle: { fontFamily: fonts.bodyMedium, fontSize: 11 },
      }}
    >
      <Tab.Screen name="Home" component={HomeScreen} options={{ tabBarIcon: ({ color, size }) => <Home color={color} size={size} /> }} />
      <Tab.Screen name="Chat" component={ChatScreen} options={{ tabBarIcon: ({ color, size }) => <MessageSquare color={color} size={size} /> }} />
      <Tab.Screen name="Knowledge" component={KnowledgeScreen} options={{ tabBarIcon: ({ color, size }) => <FolderOpen color={color} size={size} /> }} />
      <Tab.Screen name="Settings" component={SettingsScreen} options={{ tabBarIcon: ({ color, size }) => <Settings color={color} size={size} /> }} />
    </Tab.Navigator>
  )
}
