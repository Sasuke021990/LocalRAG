<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { googleLoginUrl } from '../api/auth.js'
import AuthShell from '../components/AuthShell.vue'
import Button from '../components/ui/Button.vue'
import Input from '../components/ui/Input.vue'

const router = useRouter()
const auth = useAuthStore()
const username = ref('')
const email = ref('')
const password = ref('')
const confirm = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  if (!username.value.trim()) { error.value = 'Please enter a username.'; return }
  if (password.value.length < 8) { error.value = 'Password must be at least 8 characters.'; return }
  if (password.value !== confirm.value) { error.value = 'Passwords do not match.'; return }
  loading.value = true
  try {
    await auth.signup(username.value.trim(), email.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.message || 'Signup failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthShell title="Create your vault" subtitle="1 GB free — your documents, always yours.">
    <form class="flex flex-col gap-4" @submit.prevent="submit">
      <Input v-model="username" label="Username" placeholder="How should we call you?" autocomplete="username" required />
      <Input v-model="email" type="email" label="Email" placeholder="you@example.com" autocomplete="email" required />
      <Input v-model="password" type="password" label="Password" placeholder="At least 8 characters" autocomplete="new-password" required />
      <Input v-model="confirm" type="password" label="Confirm password" placeholder="••••••••" autocomplete="new-password" required />
      <p v-if="error" class="text-sm text-rose">{{ error }}</p>
      <Button type="submit" :disabled="loading" block>{{ loading ? 'Creating…' : 'Create account' }}</Button>
    </form>

    <div class="flex items-center gap-3 my-5">
      <div class="h-px flex-1 bg-border-subtle" />
      <span class="text-xs text-ink-muted">or</span>
      <div class="h-px flex-1 bg-border-subtle" />
    </div>

    <a :href="googleLoginUrl" class="block">
      <Button variant="secondary" block type="button">Continue with Google</Button>
    </a>

    <p class="text-sm text-ink-soft text-center mt-6">
      Already have an account?
      <router-link to="/login" class="text-indigo font-semibold hover:underline">Sign in</router-link>
    </p>
  </AuthShell>
</template>
