<script setup>
import { X } from 'lucide-vue-next'

const props = defineProps({
  open: Boolean,
  title: String,
  // When false, the modal can only be resolved via its own in-content
  // buttons (no backdrop click, no X) — for popups where an incidental
  // click must never silently dismiss it (e.g. the idle-session timeout).
  dismissible: { type: Boolean, default: true },
})
defineEmits(['close'])
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="fixed inset-0 z-[90] flex items-center justify-center p-4 bg-ink/30 backdrop-blur-sm"
        @click.self="dismissible && $emit('close')"
      >
        <div class="w-full max-w-md bg-surface rounded-3xl shadow-[0_24px_48px_rgba(30,27,46,0.24)] border border-border-subtle p-6">
          <div class="flex items-start justify-between mb-4">
            <h3 class="text-lg font-semibold font-display text-ink">{{ title }}</h3>
            <button v-if="dismissible" class="text-ink-muted hover:text-ink cursor-pointer" @click="$emit('close')">
              <X class="w-5 h-5" />
            </button>
          </div>
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
