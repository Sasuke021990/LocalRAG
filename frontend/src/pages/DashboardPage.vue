<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import * as documentsApi from '../api/documents.js'
import { ACCEPTED_FILE_TYPES } from '../api/documents.js'
import { useToastStore } from '../stores/toast.js'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import IconChip from '../components/ui/IconChip.vue'
import UsageRing from '../components/UsageRing.vue'
import { FileText, Boxes, Upload, MessageSquare, Sparkles, Loader2, Plug } from 'lucide-vue-next'

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()
const documents = ref([])
const pools = ref([])
const loading = ref(true)
const fileInput = ref(null)
const uploading = ref(false)
const progressPct = ref(0)
const progressMessage = ref('')

async function load() {
  try {
    const [docRes, poolRes] = await Promise.all([documentsApi.fetchDocuments(), documentsApi.fetchPools()])
    documents.value = docRes.documents || []
    pools.value = poolRes.pools || []
  } catch (_) { /* handled by empty states */ } finally {
    loading.value = false
  }
}

onMounted(load)

// "Upload" opens the OS file picker directly and embeds on selection — no
// detour through the Knowledge Base page. Lands in the default pool
// (flagged pool_assigned=false) so it shows up under "needs a pool" there.
function triggerUpload() {
  fileInput.value?.click()
}

function onFilePicked(e) {
  const file = e.target.files[0]
  e.target.value = ''   // reset so picking the same file again still fires 'change'
  if (!file) return
  const name = file.name
  uploading.value = true
  progressPct.value = 0
  progressMessage.value = 'Uploading…'

  documentsApi.uploadWithProgress(file, '', 512, 50, {
    onProgress: (d) => { progressPct.value = d.progress; progressMessage.value = d.message },
    onDone: (d) => {
      uploading.value = false
      progressPct.value = 0
      if (d.status === 'failed') {
        toast.error(d.message || 'Processing failed')
      } else {
        toast.success(`"${name}" embedded — ready to search.`)
      }
      load()
    },
    onError: (err) => {
      uploading.value = false
      progressPct.value = 0
      toast.error(err.message || 'Upload failed')
    },
  })
}

const recent = computed(() =>
  [...documents.value].sort((a, b) => (b.processed_at || '').localeCompare(a.processed_at || '')).slice(0, 5)
)
const firstName = computed(() => auth.user?.username || (auth.user?.email || '').split('@')[0])
</script>

<template>
  <div class="flex flex-col gap-8">
    <div>
      <h1 class="text-2xl md:text-3xl font-bold font-display text-ink">
        Welcome back, <span class="vaultly-gradtext">{{ firstName }}</span>
      </h1>
      <p class="text-ink-soft mt-1">Here's what's in your vault.</p>
    </div>

    <!-- Hero: usage ring + stats -->
    <div class="grid gap-5 md:grid-cols-3">
      <Card class="md:col-span-1 flex items-center justify-center">
        <UsageRing />
      </Card>

      <div class="md:col-span-2 grid grid-cols-2 gap-5">
        <Card interactive class="cursor-pointer" @click="router.push('/knowledge-base')">
          <IconChip color="indigo"><FileText class="w-5 h-5" /></IconChip>
          <p class="text-3xl font-bold font-mono text-ink mt-4">{{ documents.length }}</p>
          <p class="text-sm text-ink-soft">Documents</p>
        </Card>
        <Card interactive class="cursor-pointer" @click="router.push('/knowledge-base')">
          <IconChip color="pink"><Boxes class="w-5 h-5" /></IconChip>
          <p class="text-3xl font-bold font-mono text-ink mt-4">{{ pools.length }}</p>
          <p class="text-sm text-ink-soft">Knowledge pools</p>
        </Card>
        <Card interactive class="col-span-2">
          <div class="flex items-center gap-4">
            <IconChip color="emerald"><Sparkles class="w-5 h-5" /></IconChip>
            <div class="flex-1">
              <p class="font-semibold text-ink">Ask your knowledge base</p>
              <p class="text-sm text-ink-soft">Answers grounded only in your own documents.</p>
            </div>
            <Button variant="secondary" @click="router.push('/chat')">Open chat</Button>
          </div>
        </Card>
      </div>
    </div>

    <!-- Recent documents -->
    <Card>
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold font-display text-ink">Recent documents</h2>
        <div class="flex gap-2">
          <Button variant="secondary" :disabled="uploading" @click="triggerUpload">
            <Loader2 v-if="uploading" class="w-4 h-4 animate-spin" />
            <Upload v-else class="w-4 h-4" />
            {{ uploading ? 'Uploading…' : 'Upload' }}
          </Button>
          <Button @click="router.push('/chat')">
            <MessageSquare class="w-4 h-4" /> Ask a question
          </Button>
        </div>
        <input ref="fileInput" type="file" class="hidden" :accept="ACCEPTED_FILE_TYPES" @change="onFilePicked" />
      </div>

      <!-- Real ingestion progress: parsing → (OCR for images) → chunking → embedding → storing -->
      <div v-if="uploading" class="flex flex-col gap-1.5 mb-4">
        <div class="flex items-center justify-between text-xs text-ink-soft">
          <span>{{ progressMessage || 'Uploading…' }}</span>
          <span class="font-mono">{{ progressPct }}%</span>
        </div>
        <div class="h-1.5 rounded-full bg-surface-alt overflow-hidden">
          <div class="h-full vaultly-gradient transition-all duration-300 ease-out" :style="{ width: progressPct + '%' }" />
        </div>
      </div>

      <div v-if="loading" class="text-sm text-ink-muted py-8 text-center">Loading…</div>

      <div v-else-if="recent.length === 0" class="flex flex-col items-center text-center py-10 gap-3">
        <IconChip color="indigo" size="lg"><Upload class="w-6 h-6" /></IconChip>
        <p class="font-semibold text-ink">Your knowledge base is empty</p>
        <p class="text-sm text-ink-soft max-w-sm">Upload your first document to start building a vault you can search and chat with.</p>
        <Button class="mt-2" :disabled="uploading" @click="triggerUpload">
          {{ uploading ? 'Uploading…' : 'Upload a document' }}
        </Button>
      </div>

      <ul v-else class="flex flex-col divide-y divide-border-subtle">
        <li v-for="d in recent" :key="d.key" class="flex items-center gap-3 py-3">
          <IconChip color="indigo" size="sm"><FileText class="w-4 h-4" /></IconChip>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-ink truncate">{{ d.file_name }}</p>
            <p class="text-xs text-ink-soft">{{ d.chunk_count }} chunks · pool: {{ d.pool }}</p>
          </div>
          <span v-if="d.pool_assigned === false" class="text-xs text-amber font-semibold">needs a pool</span>
        </li>
      </ul>
    </Card>

    <!-- MCP awareness — surfaces the integration without requiring users to
         already know to look in Settings for it. -->
    <Card interactive class="cursor-pointer" @click="router.push('/settings')">
      <div class="flex items-center gap-4">
        <IconChip color="indigo"><Plug class="w-5 h-5" /></IconChip>
        <div class="flex-1">
          <p class="font-semibold text-ink">Connect your AI tools via MCP</p>
          <p class="text-sm text-ink-soft">Let Claude Desktop, Cursor, and other AI agents search your Vaultly knowledge base directly — create an API token in Settings to get started.</p>
        </div>
        <Button variant="secondary" @click.stop="router.push('/settings')">Set up</Button>
      </div>
    </Card>
  </div>
</template>
