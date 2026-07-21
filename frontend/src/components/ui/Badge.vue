<script setup>
import { computed } from 'vue'

const props = defineProps({
  color: { type: String, default: 'indigo' }, // indigo | pink | emerald | amber | rose | slate
})

const classes = computed(() => {
  const map = {
    indigo: 'bg-indigo/10 text-indigo',
    pink: 'bg-pink/10 text-pink',
    emerald: 'bg-emerald/10 text-emerald',
    amber: 'bg-amber/10 text-amber',
    rose: 'bg-rose/10 text-rose',
    slate: 'bg-ink-soft/10 text-ink-soft',
  }
  return map[props.color] || map.indigo
})
</script>

<template>
  <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold" :class="classes">
    <slot />
  </span>
</template>
