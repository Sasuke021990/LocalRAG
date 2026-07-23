<script setup>
import { ref, computed } from 'vue'
import * as documentsApi from '../api/documents.js'
import { ACCEPTED_FILE_TYPES } from '../api/documents.js'
import { useToastStore } from '../stores/toast.js'
import { useAuthStore } from '../stores/auth.js'
import PoolPicker from './PoolPicker.vue'
import Button from './ui/Button.vue'
import IconChip from './ui/IconChip.vue'
import { UploadCloud, FileText, Image as ImageIcon, X, Loader2 } from 'lucide-vue-next'

const props = defineProps({ pools: { type: Array, default: () => [] } })
const emit = defineEmits(['uploaded', 'pool-created'])

const toast = useToastStore()
const auth = useAuthStore()
const file = ref(null)
const pool = ref('')
const chunkSize = ref(512)
const chunkOverlap = ref(50)
const dragOver = ref(false)
const uploading = ref(false)
const progressPct = ref(0)
const progressMessage = ref('')
// True while the PoolPicker has an unconfirmed new-pool name typed in — blocks
// upload so the click can't discard the pool the user is mid-creating.
const poolPending = ref(false)

const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tiff', '.tif']
const isImage = computed(() => {
  const name = file.value?.name?.toLowerCase() || ''
  return IMAGE_EXTS.some((ext) => name.endsWith(ext))
})
const formattedSize = computed(() => {
  if (!file.value) return ''
  const kb = file.value.size / 1024
  return kb > 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`
})

function pick(e) { file.value = e.target.files[0] || null }
function drop(e) { dragOver.value = false; file.value = e.dataTransfer.files[0] || null }
function clearFile() { file.value = null }

function submit() {
  if (!file.value || uploading.value) return
  const name = file.value.name
  uploading.value = true
  progressPct.value = 0
  progressMessage.value = 'Uploading…'

  documentsApi.uploadWithProgress(file.value, pool.value, chunkSize.value, chunkOverlap.value, {
    onQueued: (res) => {
      if (res.pool_assigned === false) {
        toast.push('Uploaded to General. Assign it to a pool below once it finishes processing.')
      }
    },
    onProgress: (d) => { progressPct.value = d.progress; progressMessage.value = d.message },
    onDone: (d) => {
      uploading.value = false
      progressPct.value = 0
      if (d.status === 'failed') {
        toast.error(d.message || 'Processing failed')
      } else {
        toast.success(`"${name}" embedded — ready to search.`)
      }
      file.value = null
      pool.value = ''
      emit('uploaded')
    },
    onError: (e) => {
      uploading.value = false
      progressPct.value = 0
      toast.error(e.message || 'Upload failed')
    },
  })
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <label
      class="relative flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center cursor-pointer transition-all duration-200"
      :class="dragOver ? 'border-indigo bg-indigo/5 scale-[1.01]' : file ? 'border-emerald/40 bg-emerald/5' : 'border-border-subtle hover:border-indigo/40 hover:bg-surface-alt'"
      @dragover.prevent="dragOver = true" @dragleave.prevent="dragOver = false" @drop.prevent="drop"
    >
      <IconChip :color="file ? 'emerald' : 'indigo'" size="lg">
        <ImageIcon v-if="isImage" class="w-6 h-6" />
        <FileText v-else-if="file" class="w-6 h-6" />
        <UploadCloud v-else class="w-6 h-6" />
      </IconChip>

      <div v-if="file" class="flex items-center gap-2 max-w-full">
        <div class="min-w-0">
          <p class="text-sm font-semibold text-ink truncate max-w-[14rem]">{{ file.name }}</p>
          <p class="text-xs text-ink-soft">{{ formattedSize }} · click to change</p>
        </div>
        <button
          type="button" title="Remove file"
          class="shrink-0 text-ink-muted hover:text-rose cursor-pointer p-1 rounded-lg hover:bg-rose/5"
          @click.prevent.stop="clearFile"
        >
          <X class="w-4 h-4" />
        </button>
      </div>
      <div v-else>
        <p class="text-sm font-semibold text-ink">Drop a file or click to browse</p>
        <p class="text-xs text-ink-soft mt-0.5">Documents & images · up to 50 MB</p>
      </div>

      <input type="file" class="hidden" @change="pick" :accept="ACCEPTED_FILE_TYPES" />
    </label>

    <div>
      <p class="text-sm font-medium text-ink-soft mb-1.5">Pool</p>
      <PoolPicker v-model="pool" :pools="pools" @created="$emit('pool-created', $event)" @pending="poolPending = $event" />
      <p v-if="poolPending" class="text-xs text-ink-muted mt-1.5">Finish creating the new pool (✓) or pick an existing one to upload.</p>
    </div>

    <!-- Chunking is an implementation detail — only admins get to tune it. -->
    <div v-if="auth.user?.is_admin" class="grid grid-cols-2 gap-3">
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

    <!-- Real ingestion progress: parsing → (OCR for images) → chunking → embedding → storing -->
    <div v-if="uploading" class="flex flex-col gap-1.5">
      <div class="flex items-center justify-between text-xs text-ink-soft">
        <span>{{ progressMessage || 'Uploading…' }}</span>
        <span class="font-mono">{{ progressPct }}%</span>
      </div>
      <div class="h-1.5 rounded-full bg-surface-alt overflow-hidden">
        <div class="h-full vaultly-gradient transition-all duration-300 ease-out" :style="{ width: progressPct + '%' }" />
      </div>
    </div>

    <Button :disabled="!file || uploading || poolPending" block @click="submit">
      <Loader2 v-if="uploading" class="w-4 h-4 animate-spin" />
      <UploadCloud v-else class="w-4 h-4" />
      {{ uploading ? 'Uploading…' : 'Upload & embed' }}
    </Button>
  </div>
</template>
