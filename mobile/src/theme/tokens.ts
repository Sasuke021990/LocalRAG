// Vaultly "Vivid Pulse" design tokens — a direct RN port of the web values
// (.plan/04-design-language.md §2/§3). Same hex codes = same product.

export const colors = {
  canvas: '#F6F5FC',
  surface: '#FFFFFF',
  surfaceAlt: '#FBFAFF',
  border: '#EEECF7',

  indigo: '#6366F1',
  pink: '#EC4899',
  emerald: '#10B981',
  amber: '#F59E0B',
  rose: '#F43F5E',

  ink: '#1E1B2E',
  inkSoft: '#6B6880',
  inkMuted: '#A8A5BD',

  // Alpha helpers (RN has no /opacity shorthand)
  indigoSoft: 'rgba(99,102,241,0.10)',
  pinkSoft: 'rgba(236,72,153,0.10)',
  emeraldSoft: 'rgba(16,185,129,0.12)',
  amberSoft: 'rgba(245,158,11,0.12)',
  roseSoft: 'rgba(244,63,94,0.12)',
} as const

export const gradient = {
  brand: ['#6366F1', '#EC4899'] as const, // indigo → pink
}

export const fonts = {
  display: 'Sora_700Bold',
  displaySemi: 'Sora_600SemiBold',
  body: 'Inter_400Regular',
  bodyMedium: 'Inter_500Medium',
  bodySemi: 'Inter_600SemiBold',
  mono: 'JetBrainsMono_600SemiBold',
} as const

export const radius = { sm: 12, md: 16, lg: 22, pill: 999 } as const
export const spacing = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 } as const

// Single indigo-tinted shadow — RN can't do the web's multi-color gradient
// shadow, so this is the closest achievable approximation (deliberate).
export const cardShadow = {
  shadowColor: '#6366F1',
  shadowOffset: { width: 0, height: 8 },
  shadowOpacity: 0.12,
  shadowRadius: 20,
  elevation: 4,
} as const
