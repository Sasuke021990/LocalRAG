<script setup>
import { ref, watch } from 'vue'
import * as documentsApi from '../api/documents.js'
import { useToastStore } from '../stores/toast.js'
import { Plus, Check } from 'lucide-vue-next'

const props = defineProps({
  pools: { type: Array, default: () => [] },   // [{ name, document_count }]
  modelValue: { type: String, default: '' },
  allowEmpty: { type: Boolean, default: true },
})
// `pending` is true while the inline "New pool" field is open with an
// unconfirmed name typed in — the parent uses it to disable its own
// action button (Save / Upload) so a click can't silently discard the
// name the user was in the middle of creating.
const emit = defineEmits(['update:modelValue', 'created', 'pending'])

const toast = useToastStore()
const creating = ref(false)
const newName = ref('')

watch([creating, newName], () => {
  emit('pending', creating.value && newName.value.trim().length > 0)
})

async function create() {
  const name = newName.value.trim()
  if (!name) return
  try {
    const res = await documentsApi.createPool(name)
    emit('created', res.pool)
    emit('update:modelValue', res.pool)
    newName.value = ''
    creating.value = false
  } catch (e) {
    toast.error(e.message || 'Could not create pool')
  }
}
</script>

<template>
  <div>
    <div class="flex items-center gap-2">
      <select
        :value="modelValue"
        @change="$emit('update:modelValue', $event.target.value)"
        class="flex-1 rounded-xl border border-border-subtle bg-surface-alt px-3 py-2.5 text-sm text-ink focus:border-indigo cursor-pointer"
      >
        <option v-if="allowEmpty" value="">— choose later (General) —</option>
        <option v-for="p in pools" :key="p.name" :value="p.name">{{ p.name }} ({{ p.document_count }})</option>
      </select>
      <button
        type="button"
        class="inline-flex items-center gap-1 px-3 py-2.5 rounded-xl border border-indigo/30 text-indigo text-sm font-medium hover:bg-indigo/5 cursor-pointer shrink-0"
        @click="creating = !creating"
      >
        <Plus class="w-4 h-4" /> New
      </button>
    </div>

    <div v-if="creating" class="flex items-center gap-2 mt-2">
      <input
        v-model="newName" placeholder="New pool name" @keydown.enter.prevent="create"
        class="flex-1 rounded-xl border border-border-subtle bg-surface-alt px-3 py-2 text-sm text-ink focus:border-indigo"
      />
      <button type="button" class="inline-flex items-center justify-center w-9 h-9 rounded-xl vaultly-gradient text-white cursor-pointer" @click="create">
        <Check class="w-4 h-4" />
      </button>
    </div>
  </div>
</template>
