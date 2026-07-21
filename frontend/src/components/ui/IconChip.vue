<script setup>
import { computed } from 'vue'

const props = defineProps({
  color: { type: String, default: 'indigo' },
  size: { type: String, default: 'md' }, // sm | md | lg
})

const bg = computed(() => ({
  indigo: 'bg-indigo/10 text-indigo',
  pink: 'bg-pink/10 text-pink',
  emerald: 'bg-emerald/10 text-emerald',
  amber: 'bg-amber/10 text-amber',
  rose: 'bg-rose/10 text-rose',
}[props.color] || 'bg-indigo/10 text-indigo'))

const dims = computed(() => ({ sm: 'w-8 h-8', md: 'w-10 h-10', lg: 'w-12 h-12' }[props.size]))
</script>

<template>
  <span class="inline-flex items-center justify-center rounded-xl shrink-0" :class="[bg, dims]">
    <slot />
  </span>
</template>
