<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import { useUsageStore } from '../stores/usage.js'
import { useToastStore } from '../stores/toast.js'
import * as billingApi from '../api/billing.js'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import Badge from '../components/ui/Badge.vue'
import Modal from '../components/ui/Modal.vue'
import Input from '../components/ui/Input.vue'
import PlanBadge from '../components/PlanBadge.vue'
import UsageRing from '../components/UsageRing.vue'
import { Check } from 'lucide-vue-next'

const auth = useAuthStore()
const usage = useUsageStore()
const toast = useToastStore()

const rawPlans = ref([])
const sub = ref(null)           // current subscription incl. AI usage
const billed = ref('monthly')   // 'monthly' | 'annual'
const busy = ref('')            // id of the plan currently being switched to

async function loadSubscription() {
  try {
    sub.value = await billingApi.fetchSubscription()
  } catch (_) { /* non-fatal — the usage line just won't render */ }
}

onMounted(async () => {
  try {
    rawPlans.value = (await billingApi.fetchPlans()).plans || []
  } catch (e) {
    toast.push(e.message || 'Could not load plans', 'error')
  }
  loadSubscription()
})

const rupee = (n) => `₹${Number(n).toLocaleString('en-IN')}`

// Build a display-friendly feature list from the backend's plan data, so the
// cards stay in sync with env-configured limits (no hardcoded numbers here).
function featureList(p) {
  const f = p.features || {}
  const items = [`${p.storage_gb} GB storage`]
  if (f.pools) items.push('Unlimited pools')
  if (f.hybrid_chat) items.push('Hybrid search + chat')
  if (f.api_tokens) items.push('API token access')
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

const cards = computed(() =>
  rawPlans.value.map((p) => {
    const price = p.contact_only
      ? 'Custom'
      : billed.value === 'annual'
        ? rupee(p.price_inr_annual)
        : rupee(p.price_inr_monthly)
    const period = p.contact_only
      ? 'contact us'
      : p.price_inr_monthly === 0
        ? 'forever'
        : billed.value === 'annual' ? 'per year' : 'per month'
    return {
      id: p.id,
      name: p.name,
      price,
      period,
      contactOnly: p.contact_only,
      highlight: p.id === 'pro',
      features: featureList(p),
    }
  }),
)

async function selectPlan(planId) {
  if (busy.value || planId === usage.plan) return
  busy.value = planId
  try {
    if (planId === 'free') await billingApi.cancelSubscription()
    else await billingApi.checkout(planId)
    await auth.fetchCurrentUser()
    await loadSubscription()
    const name = cards.value.find((p) => p.id === planId)?.name ?? planId
    toast.push(planId === 'free' ? 'Switched to the Free plan.' : `You're now on ${name}!`)
  } catch (err) {
    toast.push(err.message || 'Could not change plan', 'error')
  } finally {
    busy.value = ''
  }
}

// ─── Customize / contact-us modal ───
const contactOpen = ref(false)
const contactBusy = ref(false)
const contact = ref({ name: '', email: '', company: '', message: '' })

function openContact() {
  contact.value = {
    name: auth.user?.username || '',
    email: auth.user?.email || '',
    company: '',
    message: '',
  }
  contactOpen.value = true
}

async function submitContact() {
  if (!contact.value.name || !contact.value.email) {
    toast.push('Name and email are required', 'error')
    return
  }
  contactBusy.value = true
  try {
    await billingApi.submitContact(contact.value)
    contactOpen.value = false
    toast.success("Thanks! We'll be in touch about a Customize plan.")
  } catch (err) {
    toast.push(err.message || 'Could not send your enquiry', 'error')
  } finally {
    contactBusy.value = false
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
            Upgrade any time for more storage, higher AI limits, and team features.
          </p>
          <p v-if="sub" class="text-sm text-ink mt-3">
            <span class="font-semibold">AI answers today:</span>
            {{ sub.ai_questions_used_today }} / {{ sub.ai_questions_per_day }}
            <span v-if="sub.ai_unlimited_plan_wide" class="text-ink-soft">per user (plan unlimited)</span>
            <span class="text-ink-soft"> · resets daily</span>
          </p>
        </div>
      </div>
    </Card>

    <!-- Monthly / annual toggle -->
    <div class="flex items-center justify-center gap-1 p-1 rounded-xl bg-surface-alt border border-border-subtle w-fit mx-auto">
      <button
        v-for="opt in ['monthly', 'annual']" :key="opt"
        class="px-4 py-1.5 rounded-lg text-sm font-semibold transition-all cursor-pointer"
        :class="billed === opt ? 'bg-surface text-indigo shadow-sm' : 'text-ink-soft hover:text-ink'"
        @click="billed = opt"
      >
        {{ opt === 'monthly' ? 'Monthly' : 'Annual' }}
        <span v-if="opt === 'annual'" class="text-xs text-emerald ml-1">save more</span>
      </button>
    </div>

    <div class="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
      <Card v-for="p in cards" :key="p.id" interactive
        class="flex flex-col h-full"
        :class="p.highlight ? 'ring-2 ring-indigo/40' : ''">
        <div class="flex items-center justify-between gap-2 min-h-[1.75rem]">
          <h3 class="text-lg font-semibold font-display text-ink">{{ p.name }}</h3>
          <Badge v-if="p.highlight" color="pink">Popular</Badge>
          <Badge v-else-if="p.contactOnly" color="indigo">Enterprise</Badge>
        </div>
        <p class="mt-3">
          <span class="text-3xl font-bold font-display vaultly-gradtext">{{ p.price }}</span>
          <span class="text-sm text-ink-soft"> / {{ p.period }}</span>
        </p>
        <ul class="flex flex-col gap-2 mt-5 mb-6 flex-1">
          <li v-for="f in p.features" :key="f" class="flex items-center gap-2 text-sm text-ink-soft">
            <Check class="w-4 h-4 text-emerald shrink-0" /> {{ f }}
          </li>
        </ul>

        <Button v-if="p.contactOnly" variant="secondary" block class="mt-auto" @click="openContact">Contact us</Button>
        <Button v-else-if="p.id === usage.plan" variant="secondary" block disabled class="mt-auto">Current plan</Button>
        <Button v-else :variant="p.highlight ? 'primary' : 'secondary'" block class="mt-auto"
          :disabled="!!busy" @click="selectPlan(p.id)">
          <span v-if="busy === p.id">Switching…</span>
          <span v-else>{{ p.id === 'free' ? 'Downgrade to Free' : `Upgrade to ${p.name}` }}</span>
        </Button>
      </Card>
    </div>
    <p class="text-xs text-ink-muted text-center">
      Billing is a demo stub — plan changes apply instantly with no real payment.
    </p>

    <!-- Customize / contact-us modal -->
    <Modal :open="contactOpen" title="Talk to us about a Customize plan" @close="contactOpen = false">
      <p class="text-sm text-ink-soft mb-4">
        Tell us what you need — custom storage, larger teams, higher AI limits — and we'll get back to you.
      </p>
      <div class="flex flex-col gap-3">
        <Input v-model="contact.name" label="Name" placeholder="Your name" />
        <Input v-model="contact.email" label="Email" type="email" placeholder="you@company.com" />
        <Input v-model="contact.company" label="Company (optional)" placeholder="Company name" />
        <label class="text-sm text-ink-soft">
          What do you need?
          <textarea v-model="contact.message" rows="3"
            class="w-full mt-1 rounded-xl border border-border-subtle bg-surface-alt px-3 py-2 text-sm text-ink focus:border-indigo resize-none"
            placeholder="e.g. 50 GB storage, 20 team members, higher daily AI limits" />
        </label>
      </div>
      <div class="flex gap-2 mt-6">
        <Button variant="secondary" block @click="contactOpen = false">Cancel</Button>
        <Button block :disabled="contactBusy" @click="submitContact">
          {{ contactBusy ? 'Sending…' : 'Send enquiry' }}
        </Button>
      </div>
    </Modal>
  </div>
</template>
