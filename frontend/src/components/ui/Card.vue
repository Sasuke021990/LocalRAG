<script setup>
defineProps({
  padded: { type: Boolean, default: true },
  interactive: Boolean,
})
</script>

<template>
  <div
    class="bg-surface border border-border-subtle rounded-2xl shadow-[0_8px_24px_rgba(99,102,241,0.08)] transition-all duration-200"
    :class="[
      padded ? 'p-6' : '',
      interactive ? 'hover:-translate-y-0.5 hover:shadow-[0_12px_32px_rgba(99,102,241,0.16)] hover:border-indigo/30' : '',
    ]"
  >
    <slot />
  </div>
</template>
