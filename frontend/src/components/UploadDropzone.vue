<script setup>
import { ref } from 'vue'
import * as documentsApi from '../api/documents.js'
import { useToastStore } from '../stores/toast.js'
import PoolPicker from './PoolPicker.vue'
import Button from './ui/Button.vue'
import IconChip from './ui/IconChip.vue'
import { UploadCloud, FileText } from 'lucide-vue-next'

const props = defineProps({ pools: { type: Array, default: () => [] } })
const emit = defineEmits(['uploaded', 'pool-created'])

const toast = useToastStore()
const file = ref(null)
const pool = ref('')
const chunkSize = ref(512)
const chunkOverlap = ref(50)
const dragOver = ref(false)
const uploading = ref(false)

function pick(e) { file.value = e.target.files[0] || null }
function drop(e) { dragOver.value = false; file.value = e.dataTransfer.files[0] || null }

async function submit() {
  if (!file.value) return
  uploading.value = true
  try {
    const res = await documentsApi.uploadDocument(file.value, pool.value, chunkSize.value, chunkOverlap.value)
    if (res.pool_assigned === false) {
      toast.push(`Uploaded to General. Assign it to a pool below once it finishes processing.`)
    } else {
      toast.success(`Uploaded to "${res.pool}". Processing…`)
    }
    file.value = null
    pool.value = ''
    emit('uploaded')
  } catch (e) {
    toast.error(e.message || 'Upload failed')
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <label
      class="flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-8 text-center cursor-pointer transition-colors"
      :class="dragOver ? 'border-indigo bg-indigo/5' : 'border-border-subtle hover:border-indigo/40'"
      @dragover.prevent="dragOver = true" @dragleave.prevent="dragOver = false" @drop.prevent="drop"
    >
      <IconChip color="indigo" size="lg">
        <FileText v-if="file" class="w-6 h-6" />
        <UploadCloud v-else class="w-6 h-6" />
      </IconChip>
      <div v-if="file">
        <p class="text-sm font-semibold text-ink">{{ file.name }}</p>
        <p class="text-xs text-ink-soft">{{ (file.size / 1024).toFixed(0) }} KB · click to change</p>
      </div>
      <div v-else>
        <p class="text-sm font-semibold text-ink">Drop a file or click to browse</p>
        <p class="text-xs text-ink-soft">PDF, DOCX, TXT, CSV, MD, HTML, JSON, XML</p>
      </div>
      <input type="file" class="hidden" @change="pick"
        accept=".pdf,.docx,.txt,.csv,.md,.html,.htm,.json,.xml" />
    </label>

    <div>
      <p class="text-sm font-medium text-ink-soft mb-1.5">Pool</p>
      <PoolPicker v-model="pool" :pools="pools" @created="$emit('pool-created', $event)" />
    </div>

    <div class="grid grid-cols-2 gap-3">
      <label class="text-sm text-ink-soft">
        Chunk size
        <input type="number" v-model.number="chunkSize" min="128" max="2048"
          class="w-full mt-1 rounded-xl border border-border-subtle bg-surface-alt px-3 py-2 text-sm text-ink focus:border-indigo" />
      </label>
      <label class="text-sm text-ink-soft">
        Chunk overlap
        <input type="number" v-model.number="chunkOverlap" min="0" max="512"
          class="w-full mt-1 rounded-xl border border-border-subtle bg-surface-alt px-3 py-2 text-sm text-ink focus:border-indigo" />
      </label>
    </div>

    <Button :disabled="!file || uploading" block @click="submit">
      {{ uploading ? 'Uploading…' : 'Upload & embed' }}
    </Button>
  </div>
</template>
