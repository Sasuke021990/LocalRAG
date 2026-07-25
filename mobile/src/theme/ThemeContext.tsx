import React, { createContext, useContext, useMemo } from 'react'
import { useColorScheme } from 'react-native'
import { lightColors, darkColors, type ColorTokens } from './tokens'

type Scheme = 'light' | 'dark'

interface ThemeValue {
  colors: ColorTokens
  scheme: Scheme
  isDark: boolean
}

const ThemeContext = createContext<ThemeValue>({ colors: lightColors, scheme: 'light', isDark: false })

// Follows the OS appearance setting live (useColorScheme re-renders on
// change, no restart needed) -- no in-app override for v1, matching what
// task.md's P1 #14 actually asked for ("no dark mode" / "widely expected").
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const system = useColorScheme()
  const scheme: Scheme = system === 'dark' ? 'dark' : 'light'

  const value = useMemo<ThemeValue>(() => ({
    colors: scheme === 'dark' ? darkColors : lightColors,
    scheme,
    isDark: scheme === 'dark',
  }), [scheme])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useAppTheme() {
  return useContext(ThemeContext)
}
