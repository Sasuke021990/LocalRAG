<script setup>
import { useToastStore } from '../../stores/toast.js'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-vue-next'

const toast = useToastStore()

const icon = (t) => (t === 'success' ? CheckCircle2 : t === 'error' ? AlertCircle : Info)
const accent = (t) => (t === 'success' ? 'text-emerald' : t === 'error' ? 'text-rose' : 'text-indigo')
</script>

<template>
  <div class="fixed top-4 right-4 z-[100] flex flex-col gap-3 w-[min(22rem,calc(100vw-2rem))]">
    <TransitionGroup name="toast">
      <div
        v-for="t in toast.toasts"
        :key="t.id"
        class="flex items-start gap-3 bg-surface border border-border-subtle rounded-3xl shadow-[0_12px_32px_rgba(99,102,241,0.16)] p-4"
      >
        <component :is="icon(t.type)" :class="accent(t.type)" class="w-5 h-5 shrink-0 mt-0.5" />
        <p class="text-sm text-ink flex-1">{{ t.message }}</p>
        <button class="text-ink-muted hover:text-ink cursor-pointer" @click="toast.dismiss(t.id)">
          <X class="w-4 h-4" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 0.25s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(1rem); }
</style>
