<script setup>
import { ref } from 'vue'
import * as authApi from '../api/auth.js'
import { useAuthStore } from '../stores/auth.js'
import { useToastStore } from '../stores/toast.js'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import Input from '../components/ui/Input.vue'
import Badge from '../components/ui/Badge.vue'
import IconChip from '../components/ui/IconChip.vue'
import { KeyRound, Webhook, Plug } from 'lucide-vue-next'

const auth = useAuthStore()
const toast = useToastStore()

const current = ref('')
const next = ref('')
const confirm = ref('')
const error = ref('')
const saving = ref(false)

async function changePassword() {
  error.value = ''
  if (next.value.length < 8) { error.value = 'New password must be at least 8 characters.'; return }
  if (next.value !== confirm.value) { error.value = 'New passwords do not match.'; return }
  saving.value = true
  try {
    await authApi.changePassword(current.value, next.value)
    toast.success('Password updated.')
    current.value = next.value = confirm.value = ''
  } catch (e) {
    error.value = e.message || 'Could not change password'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-8 max-w-2xl">
    <div>
      <h1 class="text-2xl font-bold font-display text-ink">Settings</h1>
      <p class="text-ink-soft text-sm">{{ auth.user?.email }}</p>
    </div>

    <!-- Change password -->
    <Card>
      <div class="flex items-center gap-3 mb-5">
        <IconChip color="indigo"><KeyRound class="w-5 h-5" /></IconChip>
        <div>
          <h2 class="font-semibold font-display text-ink">Change password</h2>
          <p class="text-sm text-ink-soft">Other sessions will be signed out.</p>
        </div>
      </div>
      <form class="flex flex-col gap-4" @submit.prevent="changePassword">
        <Input v-model="current" type="password" label="Current password" autocomplete="current-password" required />
        <Input v-model="next" type="password" label="New password" autocomplete="new-password" required />
        <Input v-model="confirm" type="password" label="Confirm new password" autocomplete="new-password" required />
        <p v-if="error" class="text-sm text-rose">{{ error }}</p>
        <Button type="submit" :disabled="saving" class="self-start">{{ saving ? 'Saving…' : 'Update password' }}</Button>
      </form>
    </Card>

    <!-- Connections (Phase 2 backend exists; UI coming) -->
    <Card>
      <div class="flex items-center gap-3 mb-5">
        <IconChip color="pink"><Plug class="w-5 h-5" /></IconChip>
        <h2 class="font-semibold font-display text-ink">Connections</h2>
      </div>
      <div class="flex flex-col divide-y divide-border-subtle">
        <div class="flex items-center gap-3 py-4">
          <IconChip color="indigo" size="sm"><KeyRound class="w-4 h-4" /></IconChip>
          <div class="flex-1">
            <p class="text-sm font-medium text-ink">MCP / API tokens</p>
            <p class="text-xs text-ink-soft">Connect Vaultly to any AI client.</p>
          </div>
          <Badge color="slate">Coming soon</Badge>
        </div>
        <div class="flex items-center gap-3 py-4">
          <IconChip color="pink" size="sm"><Webhook class="w-4 h-4" /></IconChip>
          <div class="flex-1">
            <p class="text-sm font-medium text-ink">Webhooks</p>
            <p class="text-xs text-ink-soft">Get notified on document events.</p>
          </div>
          <Badge color="slate">Coming soon</Badge>
        </div>
      </div>
    </Card>
  </div>
</template>
