<script setup>
import { computed } from 'vue'
import { useUsageStore } from '../stores/usage.js'
import Badge from './ui/Badge.vue'

const usage = useUsageStore()
const color = computed(() => (usage.plan === 'free' ? 'slate' : 'indigo'))
const label = computed(() => usage.plan.charAt(0).toUpperCase() + usage.plan.slice(1))
</script>

<template>
  <Badge :color="color">{{ label }}</Badge>
</template>
