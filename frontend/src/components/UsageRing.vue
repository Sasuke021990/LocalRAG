<script setup>
import { computed } from 'vue'
import { useUsageStore } from '../stores/usage.js'

const props = defineProps({
  size: { type: Number, default: 132 },
  stroke: { type: Number, default: 12 },
})

const usage = useUsageStore()
const radius = computed(() => (props.size - props.stroke) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const dash = computed(() => (usage.percentUsed / 100) * circumference.value)

function fmt(bytes) {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = bytes / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`
}
const usedLabel = computed(() => fmt(usage.storageUsedBytes))
const quotaLabel = computed(() => fmt(usage.storageQuotaBytes))
</script>

<template>
  <div class="flex flex-col items-center">
    <div class="relative" :style="{ width: size + 'px', height: size + 'px' }">
      <svg :width="size" :height="size" class="-rotate-90">
        <defs>
          <linearGradient id="ring-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#6366F1" />
            <stop offset="100%" stop-color="#EC4899" />
          </linearGradient>
        </defs>
        <circle :cx="size / 2" :cy="size / 2" :r="radius" :stroke-width="stroke" fill="none" stroke="#EEECF7" />
        <circle
          :cx="size / 2" :cy="size / 2" :r="radius" :stroke-width="stroke" fill="none"
          stroke="url(#ring-grad)" stroke-linecap="round"
          :stroke-dasharray="`${dash} ${circumference}`"
          class="transition-[stroke-dasharray] duration-700 ease-out"
        />
      </svg>
      <div class="absolute inset-0 flex flex-col items-center justify-center">
        <span class="font-mono text-2xl font-bold vaultly-gradtext">{{ Math.round(usage.percentUsed) }}%</span>
        <span class="text-xs text-ink-muted">used</span>
      </div>
    </div>
    <p class="text-sm text-ink-soft mt-3">
      <span class="font-semibold text-ink">{{ usedLabel }}</span> of {{ quotaLabel }}
    </p>
  </div>
</template>
