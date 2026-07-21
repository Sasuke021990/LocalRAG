import React, { useState } from 'react'
import { View, Text, StyleSheet, Alert } from 'react-native'
import { Check } from 'lucide-react-native'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import UsageRing from '../components/UsageRing'
import { useUsageStore } from '../stores/usageStore'
import { useAuthStore } from '../stores/authStore'
import * as billingApi from '../api/billing'
import { colors, fonts } from '../theme/tokens'

// Prices mirror backend/billing/plans.py (a Stripe stub — no real charge).
const PLANS = [
  { id: 'free', name: 'Free', price: '$0', storage: '1 GB', features: ['1 GB storage', 'Unlimited pools', 'AI chat', 'API tokens'] },
  { id: 'pro', name: 'Pro', price: '$9', storage: '25 GB', features: ['25 GB storage', 'Everything in Free', 'Webhooks', 'Priority processing'], highlight: true },
  { id: 'business', name: 'Business', price: '$29', storage: '250 GB', features: ['250 GB storage', 'Everything in Pro', 'Team members', 'Audit log'] },
]

export default function BillingScreen() {
  const plan = useUsageStore((s) => s.plan)
  const refresh = useAuthStore((s) => s.refresh)
  const [busy, setBusy] = useState<string>('')

  async function selectPlan(planId: string) {
    if (busy || planId === plan) return
    setBusy(planId)
    try {
      if (planId === 'free') {
        await billingApi.cancelSubscription()
      } else {
        await billingApi.checkout(planId)
      }
      await refresh()  // pull new plan + quota so the ring/badge update
      const name = PLANS.find((p) => p.id === planId)?.name ?? planId
      Alert.alert(planId === 'free' ? 'Switched to Free' : `You're now on ${name}`)
    } catch (err: any) {
      Alert.alert('Could not change plan', err?.message ?? 'Please try again.')
    } finally {
      setBusy('')
    }
  }

  return (
    <Screen>
      <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 16 }}>
        <UsageRing size={110} stroke={10} />
        <View style={{ flex: 1 }}>
          <Text style={styles.currentLabel}>Current plan</Text>
          <Badge label={plan.charAt(0).toUpperCase() + plan.slice(1)} color={plan === 'free' ? 'slate' : 'indigo'} />
        </View>
      </Card>

      {PLANS.map((p) => (
        <Card key={p.id} style={p.highlight ? { borderColor: colors.indigo, borderWidth: 2 } : undefined}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text style={styles.planName}>{p.name}</Text>
            {p.highlight ? <Badge label="Popular" color="pink" /> : null}
          </View>
          <Text style={styles.price}>{p.price}<Text style={styles.per}> / mo</Text></Text>
          <View style={{ gap: 6, marginVertical: 12 }}>
            {p.features.map((f) => (
              <View key={f} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Check color={colors.emerald} size={15} />
                <Text style={styles.feature}>{f}</Text>
              </View>
            ))}
          </View>
          {p.id === plan
            ? <Button title="Current plan" variant="secondary" disabled />
            : <Button
                title={busy === p.id ? 'Switching…' : (p.id === 'free' ? 'Downgrade to Free' : `Upgrade to ${p.name}`)}
                variant={p.highlight ? 'primary' : 'secondary'}
                disabled={!!busy}
                onPress={() => selectPlan(p.id)} />}
        </Card>
      ))}
      <Text style={styles.note}>Billing is a demo stub — plan changes apply instantly, no real payment.</Text>
    </Screen>
  )
}

const styles = StyleSheet.create({
  currentLabel: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft, marginBottom: 6 },
  planName: { fontFamily: fonts.displaySemi, fontSize: 18, color: colors.ink },
  price: { fontFamily: fonts.display, fontSize: 26, color: colors.indigo, marginTop: 6 },
  per: { fontFamily: fonts.body, fontSize: 13, color: colors.inkSoft },
  feature: { fontFamily: fonts.body, fontSize: 14, color: colors.inkSoft },
  note: { fontFamily: fonts.body, fontSize: 12, color: colors.inkMuted, textAlign: 'center' },
})
