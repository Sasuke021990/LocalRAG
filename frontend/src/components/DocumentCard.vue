<script setup>
import IconChip from './ui/IconChip.vue'
import { FileText, FolderInput, Trash2 } from 'lucide-vue-next'

defineProps({ document: { type: Object, required: true } })
defineEmits(['move', 'delete'])
</script>

<template>
  <div class="flex items-center gap-3 py-3">
    <IconChip color="indigo" size="sm"><FileText class="w-4 h-4" /></IconChip>
    <div class="flex-1 min-w-0">
      <p class="text-sm font-medium text-ink truncate">{{ document.file_name }}</p>
      <p class="text-xs text-ink-soft">
        {{ document.chunk_count }} chunks
        <span v-if="document.pool_assigned === false" class="text-amber font-semibold">· needs a pool</span>
      </p>
    </div>
    <button class="text-ink-muted hover:text-indigo transition-colors cursor-pointer p-1.5" title="Move to another pool" @click="$emit('move', document)">
      <FolderInput class="w-4 h-4" />
    </button>
    <button class="text-ink-muted hover:text-rose transition-colors cursor-pointer p-1.5" title="Delete" @click="$emit('delete', document)">
      <Trash2 class="w-4 h-4" />
    </button>
  </div>
</template>
