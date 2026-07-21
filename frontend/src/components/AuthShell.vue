<script setup>
import { Vault } from 'lucide-vue-next'
import Card from './ui/Card.vue'

defineProps({ title: String, subtitle: String })
</script>

<template>
  <div class="min-h-screen flex flex-col items-center justify-center px-4 py-10">
    <div class="w-full max-w-md">
      <div class="flex flex-col items-center text-center mb-8">
        <div class="flex items-center gap-2 mb-3">
          <span class="inline-flex items-center justify-center w-10 h-10 rounded-2xl vaultly-gradient text-white shadow-[0_8px_24px_rgba(99,102,241,0.28)]">
            <Vault class="w-5 h-5" />
          </span>
          <span class="text-2xl font-bold font-display text-ink">Vault<span class="vaultly-gradtext">ly</span></span>
        </div>
        <h1 class="text-xl font-semibold font-display text-ink">{{ title }}</h1>
        <p v-if="subtitle" class="text-sm text-ink-soft mt-1">{{ subtitle }}</p>
      </div>
      <Card>
        <slot />
      </Card>
      <p class="text-xs text-ink-muted text-center mt-6">
        Retrieval-Augmented. Cloud-Powered. Encrypted. Always Yours.
      </p>
    </div>
  </div>
</template>
