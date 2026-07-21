<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import * as authApi from '../api/auth.js'
import AuthShell from '../components/AuthShell.vue'
import Button from '../components/ui/Button.vue'
import Input from '../components/ui/Input.vue'

const route = useRoute()
const token = computed(() => route.query.token || '')

// Request phase
const email = ref('')
const requestSent = ref(false)

async function requestReset() {
  try { await authApi.requestPasswordReset(email.value) } catch (_) { /* never leak existence */ }
  requestSent.value = true
}

// Confirm phase
const password = ref('')
const confirm = ref('')
const error = ref('')
const done = ref(false)
const loading = ref(false)

async function confirmReset() {
  error.value = ''
  if (password.value.length < 8) { error.value = 'Password must be at least 8 characters.'; return }
  if (password.value !== confirm.value) { error.value = 'Passwords do not match.'; return }
  loading.value = true
  try {
    await authApi.confirmPasswordReset(token.value, password.value)
    done.value = true
  } catch (e) {
    error.value = e.status === 400 ? 'This reset link is invalid or has expired.' : (e.message || 'Reset failed')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthShell title="Reset your password">
    <!-- With a token: set a new password -->
    <div v-if="token">
      <div v-if="done" class="text-center">
        <p class="text-sm text-ink-soft mb-4">Your password has been updated.</p>
        <router-link to="/login"><Button block>Back to sign in</Button></router-link>
      </div>
      <form v-else class="flex flex-col gap-4" @submit.prevent="confirmReset">
        <Input v-model="password" type="password" label="New password" placeholder="At least 8 characters" autocomplete="new-password" required />
        <Input v-model="confirm" type="password" label="Confirm new password" placeholder="••••••••" autocomplete="new-password" required />
        <p v-if="error" class="text-sm text-rose">{{ error }}</p>
        <Button type="submit" :disabled="loading" block>{{ loading ? 'Updating…' : 'Update password' }}</Button>
      </form>
    </div>

    <!-- Without a token: request a reset link -->
    <div v-else>
      <div v-if="requestSent" class="text-center">
        <p class="text-sm text-ink-soft mb-4">If that email exists, a reset link has been sent.</p>
        <router-link to="/login" class="text-indigo font-semibold hover:underline text-sm">Back to sign in</router-link>
      </div>
      <form v-else class="flex flex-col gap-4" @submit.prevent="requestReset">
        <Input v-model="email" type="email" label="Email" placeholder="you@example.com" autocomplete="email" required />
        <Button type="submit" block>Send reset link</Button>
        <router-link to="/login" class="text-ink-muted hover:text-ink-soft text-sm text-center">Back to sign in</router-link>
      </form>
    </div>
  </AuthShell>
</template>
