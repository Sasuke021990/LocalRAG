import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import Svg, { Circle, Defs, LinearGradient, Stop } from 'react-native-svg'
import { useUsageStore } from '../stores/usageStore'
import { useAppTheme } from '../theme/ThemeContext'
import { fonts } from '../theme/tokens'
import { formatBytes } from '../utils/format'

export default function UsageRing({ size = 140, stroke = 12 }: { size?: number; stroke?: number }) {
  const usage = useUsageStore()
  const { colors } = useAppTheme()
  const pct = usage.percentUsed()
  const r = (size - stroke) / 2
  const circumference = 2 * Math.PI * r
  const offset = circumference * (1 - Math.min(100, pct) / 100)

  return (
    <View style={{ alignItems: 'center' }}>
      <View style={{ width: size, height: size }}>
        <Svg width={size} height={size}>
          <Defs>
            <LinearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
              <Stop offset="0" stopColor={colors.indigo} />
              <Stop offset="1" stopColor={colors.pink} />
            </LinearGradient>
          </Defs>
          <Circle cx={size / 2} cy={size / 2} r={r} stroke={colors.border} strokeWidth={stroke} fill="none" />
          <Circle
            cx={size / 2} cy={size / 2} r={r}
            stroke="url(#ring)" strokeWidth={stroke} fill="none" strokeLinecap="round"
            strokeDasharray={circumference} strokeDashoffset={offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        </Svg>
        <View style={styles.center}>
          <Text style={[styles.pct, { color: colors.indigo }]}>{Math.round(pct)}%</Text>
          <Text style={[styles.used, { color: colors.inkMuted }]}>used</Text>
        </View>
      </View>
      <Text style={[styles.caption, { color: colors.inkSoft }]}>
        <Text style={{ fontFamily: fonts.bodySemi, color: colors.ink }}>{formatBytes(usage.storageUsedBytes)}</Text>
        {'  of '}{formatBytes(usage.storageQuotaBytes)}
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  center: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center' },
  pct: { fontFamily: fonts.mono, fontSize: 24 },
  used: { fontFamily: fonts.body, fontSize: 12 },
  caption: { fontFamily: fonts.body, fontSize: 13, marginTop: 12 },
})
