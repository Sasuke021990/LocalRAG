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
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.message || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthShell title="Welcome back" subtitle="Sign in to your knowledge base.">
    <form class="flex flex-col gap-4" @submit.prevent="submit">
      <Input v-model="email" type="text" label="Email or username" placeholder="you@example.com" autocomplete="username" required />
      <Input v-model="password" type="password" label="Password" placeholder="••••••••" autocomplete="current-password" required />
      <p v-if="error" class="text-sm text-rose">{{ error }}</p>
      <Button type="submit" :disabled="loading" block>{{ loading ? 'Signing in…' : 'Sign in' }}</Button>
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
      New here?
      <router-link to="/signup" class="text-indigo font-semibold hover:underline">Create an account</router-link>
    </p>
    <p class="text-sm text-center mt-2">
      <router-link to="/reset-password" class="text-ink-muted hover:text-ink-soft">Forgot your password?</router-link>
    </p>
  </AuthShell>
</template>
