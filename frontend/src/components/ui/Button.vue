<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: { type: String, default: 'primary' }, // primary | secondary | ghost | danger
  type: { type: String, default: 'button' },
  disabled: Boolean,
  block: Boolean,
})

const classes = computed(() => {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold font-display transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed'
  const byVariant = {
    primary: 'vaultly-gradient text-white shadow-[0_8px_24px_rgba(99,102,241,0.28)] hover:shadow-[0_10px_28px_rgba(99,102,241,0.4)] hover:-translate-y-px',
    secondary: 'bg-white text-indigo border border-indigo/30 hover:border-indigo hover:bg-indigo/5',
    ghost: 'bg-transparent text-ink-soft hover:bg-black/5',
    danger: 'bg-white text-rose border border-rose/30 hover:bg-rose/5',
  }
  return `${base} ${byVariant[props.variant] || byVariant.primary} ${props.block ? 'w-full' : ''}`
})
</script>

<template>
  <button :type="type" :class="classes" :disabled="disabled">
    <slot />
  </button>
</template>
