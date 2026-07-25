import React, { useEffect, useMemo, useState } from 'react'
import { View, Text, StyleSheet, Alert, Pressable, Modal, TextInput } from 'react-native'
import { useQueryClient } from '@tanstack/react-query'
import { Check } from 'lucide-react-native'
import Screen from '../components/Screen'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Input from '../components/ui/Input'
import UsageRing from '../components/UsageRing'
import { useUsageStore } from '../stores/usageStore'
import { useAuthStore } from '../stores/authStore'
import * as billingApi from '../api/billing'
import type { Plan, Subscription } from '../api/billing'
import { useAppTheme } from '../theme/ThemeContext'
import { fonts, radius } from '../theme/tokens'

const rupee = (n: number) => `₹${Number(n).toLocaleString('en-IN')}`

// Display-friendly feature list built from backend plan data, so cards stay
// in sync with env-configured limits instead of hardcoding numbers here.
function featureList(p: Plan): string[] {
  const f = p.features || ({} as Plan['features'])
  const items = [`${p.storage_gb} GB storage`]
  if (f.pools) items.push('Unlimited pools')
  if (f.hybrid_chat) items.push('Hybrid search + chat')
  if (f.api_tokens) items.push('Unlimited API/MCP tokens')
  if (f.webhooks) items.push('Webhooks')
  if (f.priority_processing) items.push('Priority processing')
  if (f.team_members) items.push(`Team sharing (up to ${f.team_members})`)
  items.push(
    p.ai_unlimited_plan_wide
      ? `Unlimited AI answers (${p.ai_questions_per_day}/user/day)`
      : `${p.ai_questions_per_day} AI answers / day`,
  )
  return items
}

interface Card_ {
  id: string
  name: string
  price: string
  period: string
  contactOnly: boolean
  highlight: boolean
  features: string[]
}

export default function BillingScreen() {
  const qc = useQueryClient()
  const { colors } = useAppTheme()
  const plan = useUsageStore((s) => s.plan)
  const user = useAuthStore((s) => s.user)
  const refresh = useAuthStore((s) => s.refresh)

  const [rawPlans, setRawPlans] = useState<Plan[]>([])
  const [sub, setSub] = useState<Subscription | null>(null)
  const [billed, setBilled] = useState<'monthly' | 'annual'>('monthly')
  const [busy, setBusy] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  function loadData() {
    return Promise.all([
      billingApi.fetchPlans().then((r) => setRawPlans(r.plans || [])).catch(() => {}),
      billingApi.fetchSubscription().then(setSub).catch(() => {}),
    ])
  }

  useEffect(() => { loadData() }, [])

  async function onRefresh() {
    setRefreshing(true)
    await loadData()
    setRefreshing(false)
  }

  const cards: Card_[] = useMemo(() => rawPlans.map((p) => {
    const price = p.contact_only
      ? 'Custom'
      : billed === 'annual' ? rupee(p.price_inr_annual || 0) : rupee(p.price_inr_monthly || 0)
    const period = p.contact_only
      ? 'contact us'
      : p.price_inr_monthly === 0 ? 'forever' : billed === 'annual' ? 'per year' : 'per month'
    return {
      id: p.id, name: p.name, price, period,
      contactOnly: p.contact_only, highlight: p.id === 'pro',
      features: featureList(p),
    }
  }), [rawPlans, billed])

  async function selectPlan(planId: string) {
    if (busy || planId === plan) return
    setBusy(planId)
    try {
      if (planId === 'free') await billingApi.cancelSubscription()
      else await billingApi.checkout(planId)
      await refresh()
      billingApi.fetchSubscription().then(setSub).catch(() => {})
      // Other screens (e.g. the Graph tab's plan gate) read the subscription
      // via React Query — drop their cached copy so the plan change is seen
      // immediately, not just here on the Billing screen.
      qc.invalidateQueries({ queryKey: ['subscription'] })
      const name = cards.find((p) => p.id === planId)?.name ?? planId
      Alert.alert(planId === 'free' ? 'Switched to Free' : `You're now on ${name}`)
    } catch (err: any) {
      Alert.alert('Could not change plan', err?.message ?? 'Please try again.')
    } finally {
      setBusy('')
    }
  }

  // ─── Customize / contact-us modal ───
  const [contactOpen, setContactOpen] = useState(false)
  const [contactBusy, setContactBusy] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [company, setCompany] = useState('')
  const [message, setMessage] = useState('')

  function openContact() {
    setName(user?.username || '')
    setEmail(user?.email || '')
    setCompany('')
    setMessage('')
    setContactOpen(true)
  }

  async function submitContact() {
    if (!name || !email) {
      Alert.alert('Name and email are required')
      return
    }
    setContactBusy(true)
    try {
      await billingApi.submitContact({ name, email, company, message })
      setContactOpen(false)
      Alert.alert('Thanks!', "We'll be in touch about a Customize plan.")
    } catch (err: any) {
      Alert.alert('Could not send your enquiry', err?.message ?? 'Please try again.')
    } finally {
      setContactBusy(false)
    }
  }

  return (
    <Screen refreshing={refreshing} onRefresh={onRefresh}>
      <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 16 }}>
        <UsageRing size={110} stroke={10} />
        <View style={{ flex: 1 }}>
          <Text style={[styles.currentLabel, { color: colors.inkSoft }]}>Current plan</Text>
          <Badge label={plan.charAt(0).toUpperCase() + plan.slice(1)} color={plan === 'free' ? 'slate' : 'indigo'} />
          {sub ? (
            <Text style={[styles.aiUsage, { color: colors.inkSoft }]}>
              AI answers today: {sub.ai_questions_used_today} / {sub.ai_questions_per_day}
              {sub.ai_unlimited_plan_wide ? ' per user (plan unlimited)' : ''} · resets daily
            </Text>
          ) : null}
        </View>
      </Card>

      <View style={[styles.toggleWrap, { backgroundColor: colors.surfaceAlt, borderColor: colors.border }]}>
        {(['monthly', 'annual'] as const).map((opt) => (
          <Pressable
            key={opt}
            style={[styles.toggleBtn, billed === opt && { backgroundColor: colors.surface }]}
            onPress={() => setBilled(opt)}
          >
            <Text style={[styles.toggleText, { color: billed === opt ? colors.indigo : colors.inkSoft }]}>
              {opt === 'monthly' ? 'Monthly' : 'Annual'}
            </Text>
            {opt === 'annual' ? <Text style={[styles.saveMore, { color: colors.emerald }]}> save more</Text> : null}
          </Pressable>
        ))}
      </View>

      {cards.map((p) => (
        <Card key={p.id} style={p.highlight ? { borderColor: colors.indigo, borderWidth: 2 } : undefined}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text style={[styles.planName, { color: colors.ink }]}>{p.name}</Text>
            {p.highlight ? <Badge label="Popular" color="pink" /> : p.contactOnly ? <Badge label="Enterprise" color="indigo" /> : null}
          </View>
          {p.contactOnly ? (
            <Text style={[styles.price, { color: colors.indigo, marginVertical: 12 }]}>{p.price}</Text>
          ) : (
            <>
              <Text style={[styles.price, { color: colors.indigo }]}>
                {p.price}<Text style={[styles.per, { color: colors.inkSoft }]}> / {p.period}</Text>
              </Text>
              <View style={{ gap: 6, marginVertical: 12 }}>
                {p.features.map((f) => (
                  <View key={f} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Check color={colors.emerald} size={15} />
                    <Text style={[styles.feature, { color: colors.inkSoft }]}>{f}</Text>
                  </View>
                ))}
              </View>
            </>
          )}
          {p.contactOnly
            ? <Button title="Contact us" variant="secondary" onPress={openContact} />
            : p.id === plan
              ? <Button title="Current plan" variant="secondary" disabled />
              : <Button
                  title={busy === p.id ? 'Switching…' : (p.id === 'free' ? 'Downgrade to Free' : `Upgrade to ${p.name}`)}
                  variant={p.highlight ? 'primary' : 'secondary'}
                  disabled={!!busy}
                  onPress={() => selectPlan(p.id)} />}
        </Card>
      ))}
      <Text style={[styles.note, { color: colors.inkMuted }]}>Billing is a demo stub — plan changes apply instantly, no real payment.</Text>

      <Modal visible={contactOpen} transparent animationType="fade" onRequestClose={() => setContactOpen(false)}>
        <Pressable style={[styles.backdrop, { backgroundColor: colors.backdrop }]} onPress={() => setContactOpen(false)}>
          <Pressable style={[styles.sheet, { backgroundColor: colors.surface }]} onPress={(e) => e.stopPropagation()}>
            <Text style={[styles.sheetTitle, { color: colors.ink }]}>Talk to us about a Customize plan</Text>
            <Text style={[styles.sheetHint, { color: colors.inkSoft }]}>
              Tell us what you need — custom storage, larger teams, higher AI limits — and we'll get back to you.
            </Text>
            <View style={{ gap: 10 }}>
              <Input label="Name" value={name} onChangeText={setName} placeholder="Your name" />
              <Input label="Email" value={email} onChangeText={setEmail} placeholder="you@company.com" keyboardType="email-address" />
              <Input label="Company (optional)" value={company} onChangeText={setCompany} placeholder="Company name" />
              <View>
                <Text style={[styles.msgLabel, { color: colors.inkSoft }]}>What do you need?</Text>
                <TextInput
                  value={message}
                  onChangeText={setMessage}
                  multiline
                  numberOfLines={3}
                  placeholder="e.g. 50 GB storage, 20 team members, higher daily AI limits"
                  placeholderTextColor={colors.inkMuted}
                  style={[styles.msgInput, { backgroundColor: colors.surfaceAlt, borderColor: colors.border, color: colors.ink }]}
                />
              </View>
            </View>
            <View style={styles.sheetActions}>
              <Button title="Cancel" variant="secondary" onPress={() => setContactOpen(false)} style={{ flex: 1 }} />
              <Button title={contactBusy ? 'Sending…' : 'Send enquiry'} onPress={submitContact} disabled={contactBusy} style={{ flex: 1 }} />
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </Screen>
  )
}

const styles = StyleSheet.create({
  currentLabel: { fontFamily: fonts.body, fontSize: 13, marginBottom: 6 },
  aiUsage: { fontFamily: fonts.body, fontSize: 12, marginTop: 8 },
  toggleWrap: {
    flexDirection: 'row', alignSelf: 'center', gap: 4, padding: 4,
    borderRadius: radius.md, borderWidth: 1,
  },
  toggleBtn: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 7, borderRadius: radius.sm },
  toggleText: { fontFamily: fonts.bodySemi, fontSize: 13 },
  saveMore: { fontFamily: fonts.body, fontSize: 11 },
  planName: { fontFamily: fonts.displaySemi, fontSize: 18 },
  price: { fontFamily: fonts.display, fontSize: 26, marginTop: 6 },
  per: { fontFamily: fonts.body, fontSize: 13 },
  feature: { fontFamily: fonts.body, fontSize: 14 },
  note: { fontFamily: fonts.body, fontSize: 12, textAlign: 'center' },
  backdrop: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  sheet: { width: '100%', maxWidth: 420, borderRadius: radius.lg, padding: 20, gap: 4, maxHeight: '90%' },
  sheetTitle: { fontFamily: fonts.displaySemi, fontSize: 17 },
  sheetHint: { fontFamily: fonts.body, fontSize: 13, marginBottom: 14 },
  msgLabel: { fontFamily: fonts.bodyMedium, fontSize: 13, marginBottom: 6 },
  msgInput: {
    minHeight: 72, borderWidth: 1,
    borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 10,
    fontFamily: fonts.body, fontSize: 15, textAlignVertical: 'top',
  },
  sheetActions: { flexDirection: 'row', gap: 10, marginTop: 16 },
})
