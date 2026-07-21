<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import { useUsageStore } from '../stores/usage.js'
import { useToastStore } from '../stores/toast.js'
import * as billingApi from '../api/billing.js'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import Badge from '../components/ui/Badge.vue'
import PlanBadge from '../components/PlanBadge.vue'
import UsageRing from '../components/UsageRing.vue'
import { Check } from 'lucide-vue-next'

const auth = useAuthStore()
const usage = useUsageStore()
const toast = useToastStore()

// Prices mirror backend/billing/plans.py (a Stripe stub — no real charge).
const plans = [
  { id: 'free', name: 'Free', price: '$0', period: 'forever', storage: '1 GB', features: ['1 GB storage', 'Unlimited pools', 'Hybrid search + chat', 'API token access'] },
  { id: 'pro', name: 'Pro', price: '$9', period: 'per month', storage: '25 GB', features: ['25 GB storage', 'Everything in Free', 'Webhooks', 'Priority processing'], highlight: true },
  { id: 'business', name: 'Business', price: '$29', period: 'per month', storage: '250 GB', features: ['250 GB storage', 'Everything in Pro', 'Team members', 'Audit log'] },
]

const busy = ref('')  // id of the plan currently being switched to

async function selectPlan(planId) {
  if (busy.value || planId === usage.plan) return
  busy.value = planId
  try {
    if (planId === 'free') {
      await billingApi.cancelSubscription()
    } else {
      await billingApi.checkout(planId)
    }
    // Refresh the user so plan + quota (and the usage ring) reflect the change.
    await auth.fetchCurrentUser()
    const name = plans.find((p) => p.id === planId)?.name ?? planId
    toast.push(planId === 'free' ? 'Switched to the Free plan.' : `You're now on ${name}!`)
  } catch (err) {
    toast.push(err.message || 'Could not change plan', 'error')
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <div class="flex flex-col gap-8">
    <div>
      <h1 class="text-2xl font-bold font-display text-ink">Billing & Plans</h1>
      <p class="text-ink-soft text-sm">Manage your storage and subscription.</p>
    </div>

    <Card>
      <div class="flex flex-col sm:flex-row items-center gap-8">
        <UsageRing :size="120" />
        <div class="flex-1 text-center sm:text-left">
          <div class="flex items-center gap-2 justify-center sm:justify-start mb-2">
            <span class="text-ink-soft text-sm">Current plan</span>
            <PlanBadge />
          </div>
          <p class="text-ink-soft text-sm max-w-md">
            You're on the Free plan with 1 GB of storage. Upgrade any time for more room and team features.
          </p>
        </div>
      </div>
    </Card>

    <div class="grid gap-5 md:grid-cols-3">
      <Card v-for="p in plans" :key="p.id" interactive
        :class="p.highlight ? 'ring-2 ring-indigo/40' : ''">
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold font-display text-ink">{{ p.name }}</h3>
          <Badge v-if="p.highlight" color="pink">Popular</Badge>
        </div>
        <p class="mt-3">
          <span class="text-3xl font-bold font-display vaultly-gradtext">{{ p.price }}</span>
          <span class="text-sm text-ink-soft"> / {{ p.period }}</span>
        </p>
        <ul class="flex flex-col gap-2 mt-5 mb-6">
          <li v-for="f in p.features" :key="f" class="flex items-center gap-2 text-sm text-ink-soft">
            <Check class="w-4 h-4 text-emerald shrink-0" /> {{ f }}
          </li>
        </ul>
        <Button v-if="p.id === usage.plan" variant="secondary" block disabled>Current plan</Button>
        <Button v-else :variant="p.highlight ? 'primary' : 'secondary'" block
          :disabled="!!busy" @click="selectPlan(p.id)">
          <span v-if="busy === p.id">Switching…</span>
          <span v-else>{{ p.id === 'free' ? 'Downgrade to Free' : `Upgrade to ${p.name}` }}</span>
        </Button>
      </Card>
    </div>
    <p class="text-xs text-ink-muted text-center">
      Billing is a demo stub — plan changes apply instantly with no real payment.
    </p>
  </div>
</template>
