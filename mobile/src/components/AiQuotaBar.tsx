import React from 'react'
import { View, Text, StyleSheet } from 'react-native'
import { useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react-native'
import { fetchSubscription } from '../api/billing'
import Card from './ui/Card'
import { useAppTheme } from '../theme/ThemeContext'
import { fonts, radius } from '../theme/tokens'

/**
 * Daily AI-question quota (task.md P2 #21: it was visible only on the Billing
 * screen, so users hit the limit with no warning).
 *
 * Shares the ``['subscription']`` query key with the Graph and Billing
 * screens, so a plan change invalidated in one place refreshes it everywhere,
 * and chatStore's post-answer invalidation keeps the count honest as
 * questions are spent.
 */

// Warn while there's still time to act on it: half the allowance left, or
// three questions, whichever is larger. The floor matters for small plans
// where 50% of 5 still rounds down close to the limit itself — it keeps a
// firm floor of 3 rather than trusting the percentage alone on tiny plans.
function isRunningLow(remaining: number, limit: number): boolean {
  return remaining > 0 && remaining <= Math.max(3, Math.floor(limit * 0.5))
}

export default function AiQuotaBar({ compact = false }: { compact?: boolean }) {
  const { colors } = useAppTheme()
  const { data } = useQuery({ queryKey: ['subscription'], queryFn: fetchSubscription })

  // Render nothing until the real numbers are known. This is a supplementary
  // indicator, so a failed fetch stays quiet rather than pushing an error
  // banner onto Home — the screens that own this data surface their own
  // errors, and a wrong count here would be worse than none.
  if (!data || !data.ai_questions_per_day) return null

  const limit = data.ai_questions_per_day
  const used = Math.min(data.ai_questions_used_today ?? 0, limit)
  const remaining = Math.max(0, limit - used)
  const pct = Math.min(100, (used / limit) * 100)

  const exhausted = remaining === 0
  // Free plan skips the amber "running low" stage entirely — normal all the
  // way to exhausted. Its allowance is small enough (and the upgrade nudge
  // pointed enough) that an early warning reads as nagging rather than
  // useful notice; paid plans keep it.
  const low = data.plan !== 'free' && isRunningLow(remaining, limit)
  const accent = exhausted ? colors.rose : low ? colors.amber : colors.indigo

  const label = exhausted
    ? "You've used today's AI answers"
    : `${remaining} of ${limit} AI answers left today`

  if (compact) {
    return (
      <View style={styles.compactRow} accessibilityRole="text" accessibilityLabel={label}>
        <View style={[styles.compactTrack, { backgroundColor: colors.border }]}>
          <View style={[styles.compactFill, { width: `${pct}%`, backgroundColor: accent }]} />
        </View>
        <Text style={[styles.compactText, { color: exhausted || low ? accent : colors.inkSoft }]}>
          {exhausted ? 'Limit reached' : `${remaining} left`}
        </Text>
      </View>
    )
  }

  // The full variant owns its Card so that returning null above removes the
  // container too — a caller wrapping this in its own Card would render an
  // empty box before the data arrives.
  return (
    <Card style={{ gap: 8 }}>
      <View style={styles.headerRow} accessibilityRole="text" accessibilityLabel={label}>
        <View style={[styles.chip, { backgroundColor: colors.indigoSoft }]}>
          <Sparkles color={colors.indigo} size={16} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[styles.title, { color: colors.ink }]}>AI answers today</Text>
          <Text style={[styles.sub, { color: colors.inkSoft }]}>
            {used} of {limit} used
            {data.ai_unlimited_plan_wide ? ' · per user' : ''}
          </Text>
        </View>
        <Text style={[styles.remaining, { color: accent }]}>{remaining}</Text>
      </View>
      <View style={[styles.track, { backgroundColor: colors.border }]}>
        <View style={[styles.fill, { width: `${pct}%`, backgroundColor: accent }]} />
      </View>
      {exhausted ? (
        <Text style={[styles.note, { color: colors.rose }]}>
          Your daily limit resets tomorrow. Upgrade for more.
        </Text>
      ) : low ? (
        <Text style={[styles.note, { color: colors.amber }]}>Running low for today.</Text>
      ) : null}
    </Card>
  )
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  chip: { width: 32, height: 32, borderRadius: radius.sm, alignItems: 'center', justifyContent: 'center' },
  title: { fontFamily: fonts.bodySemi, fontSize: 14 },
  sub: { fontFamily: fonts.body, fontSize: 12 },
  remaining: { fontFamily: fonts.mono, fontSize: 20 },
  track: { height: 6, borderRadius: 3, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 3 },
  note: { fontFamily: fonts.body, fontSize: 12 },
  compactRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  compactTrack: { flex: 1, height: 4, borderRadius: 2, overflow: 'hidden' },
  compactFill: { height: '100%', borderRadius: 2 },
  compactText: { fontFamily: fonts.bodyMedium, fontSize: 11 },
})
