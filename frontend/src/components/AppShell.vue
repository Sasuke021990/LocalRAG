<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import PlanBadge from './PlanBadge.vue'
import Modal from './ui/Modal.vue'
import Button from './ui/Button.vue'
import { Vault, LayoutDashboard, MessageSquare, Database, CreditCard, Settings, ShieldCheck, LogOut, Menu, X } from 'lucide-vue-next'

const router = useRouter()
const auth = useAuthStore()
const mobileOpen = ref(false)

const links = computed(() => [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/chat', label: 'Chat', icon: MessageSquare },
  { to: '/knowledge-base', label: 'Knowledge Base', icon: Database },
  { to: '/billing', label: 'Billing', icon: CreditCard },
  { to: '/settings', label: 'Settings', icon: Settings },
  ...(auth.user?.is_admin ? [{ to: '/admin', label: 'Admin', icon: ShieldCheck }] : []),
])

async function logout() {
  await auth.logout()
  router.push('/login')
}

// ─── Idle-session timeout ───────────────────────────────────────────────────
// After `idle_timeout_seconds` (server-configured via SESSION_IDLE_TIMEOUT_
// SECONDS, from /auth/me) of no mouse/keyboard/touch/scroll activity, show a
// "still there?" popup. It resolves only via its own buttons (or the modal
// backdrop) — not by incidental page activity, so it can't flicker open and
// silently vanish. Left unanswered for another full timeout window, the user
// is force-logged-out.
const idlePopupOpen = ref(false)
let lastActivity = Date.now()
let popupOpenedAt = 0
let checkTimer = null

const idleTimeoutMs = computed(() => (auth.user?.idle_timeout_seconds ?? 60) * 1000)
const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll']

function markActivity() {
  if (idlePopupOpen.value) return  // once prompted, only the popup's own actions resolve it
  lastActivity = Date.now()
}

function checkIdle() {
  if (!auth.isAuthenticated) return
  const now = Date.now()
  if (!idlePopupOpen.value) {
    if (now - lastActivity >= idleTimeoutMs.value) {
      idlePopupOpen.value = true
      popupOpenedAt = now
    }
  } else if (now - popupOpenedAt >= idleTimeoutMs.value) {
    forceLogout()
  }
}

function continueSession() {
  idlePopupOpen.value = false
  lastActivity = Date.now()
}

async function forceLogout() {
  idlePopupOpen.value = false
  await auth.logout()
  router.push('/login')
}

onMounted(() => {
  ACTIVITY_EVENTS.forEach((evt) => window.addEventListener(evt, markActivity, { passive: true }))
  checkTimer = setInterval(checkIdle, 1000)
})
onUnmounted(() => {
  ACTIVITY_EVENTS.forEach((evt) => window.removeEventListener(evt, markActivity))
  clearInterval(checkTimer)
})
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="sticky top-0 z-40 bg-surface/80 backdrop-blur-md border-b border-border-subtle">
      <div class="max-w-6xl mx-auto px-4 md:px-6 h-16 flex items-center justify-between gap-4">
        <router-link to="/" class="flex items-center gap-2 shrink-0">
          <span class="inline-flex items-center justify-center w-9 h-9 rounded-xl vaultly-gradient text-white">
            <Vault class="w-5 h-5" />
          </span>
          <span class="text-lg font-bold font-display text-ink hidden sm:inline">Vault<span class="vaultly-gradtext">ly</span></span>
        </router-link>

        <nav class="hidden md:flex items-center gap-1">
          <router-link
            v-for="l in links" :key="l.to" :to="l.to"
            class="flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium text-ink-soft hover:bg-black/5 transition-colors"
            active-class="!text-indigo bg-indigo/8"
          >
            <component :is="l.icon" class="w-4 h-4" />
            {{ l.label }}
          </router-link>
        </nav>

        <div class="flex items-center gap-3">
          <PlanBadge class="hidden sm:inline-flex" />
          <span class="text-sm text-ink-soft hidden lg:inline max-w-[12rem] truncate" :title="auth.user?.email">
            {{ auth.user?.username || auth.user?.email }}
          </span>
          <button class="hidden md:inline-flex text-ink-muted hover:text-rose transition-colors cursor-pointer" title="Log out" @click="logout">
            <LogOut class="w-5 h-5" />
          </button>
          <button class="md:hidden text-ink cursor-pointer" @click="mobileOpen = !mobileOpen">
            <component :is="mobileOpen ? X : Menu" class="w-6 h-6" />
          </button>
        </div>
      </div>

      <!-- Mobile nav -->
      <nav v-if="mobileOpen" class="md:hidden border-t border-border-subtle px-4 py-3 flex flex-col gap-1">
        <router-link
          v-for="l in links" :key="l.to" :to="l.to" @click="mobileOpen = false"
          class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-ink-soft hover:bg-black/5"
          active-class="!text-indigo bg-indigo/8"
        >
          <component :is="l.icon" class="w-4 h-4" />
          {{ l.label }}
        </router-link>
        <button class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-rose hover:bg-rose/5 cursor-pointer" @click="logout">
          <LogOut class="w-4 h-4" /> Log out
        </button>
      </nav>
    </header>

    <main class="flex-1 w-full max-w-6xl mx-auto px-4 md:px-6 py-8">
      <slot />
    </main>

    <Modal :open="idlePopupOpen" title="Still there?" @close="continueSession">
      <p class="text-sm text-ink-soft mb-6">
        You've been inactive for a while. For your security, we'll sign you out soon unless you confirm you're still here.
      </p>
      <div class="flex gap-2">
        <Button variant="secondary" block @click="forceLogout">Log out</Button>
        <Button block @click="continueSession">Continue session</Button>
      </div>
    </Modal>
  </div>
</template>
