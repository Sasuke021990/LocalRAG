<script setup>
import { ref, computed, onMounted } from 'vue'
import confetti from 'canvas-confetti'
import * as documentsApi from '../api/documents.js'
import { useToastStore } from '../stores/toast.js'
import { useAuthStore } from '../stores/auth.js'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import Badge from '../components/ui/Badge.vue'
import Modal from '../components/ui/Modal.vue'
import Input from '../components/ui/Input.vue'
import IconChip from '../components/ui/IconChip.vue'
import PoolPicker from '../components/PoolPicker.vue'
import UploadDropzone from '../components/UploadDropzone.vue'
import DocumentCard from '../components/DocumentCard.vue'
import { Boxes, AlertCircle, RefreshCw, Trash2, Plus } from 'lucide-vue-next'

const toast = useToastStore()
const auth = useAuthStore()
const pools = ref([])
const documents = ref([])
const loading = ref(true)
let lastCount = 0

const MILESTONES = [1, 10, 25, 50, 100, 250, 500]

async function load() {
  try {
    const [poolRes, docRes] = await Promise.all([documentsApi.fetchPools(), documentsApi.fetchDocuments()])
    pools.value = poolRes.pools || []
    const prev = lastCount
    documents.value = docRes.documents || []
    // Milestone confetti when the document count first crosses a threshold.
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!reduce && MILESTONES.includes(documents.value.length) && documents.value.length > prev) {
      confetti({ particleCount: 90, spread: 70, origin: { y: 0.3 }, colors: ['#6366F1', '#EC4899', '#10B981'] })
    }
    lastCount = documents.value.length
    // keep the header usage/plan fresh
    auth.fetchCurrentUser()
  } catch (e) {
    toast.error(e.message || 'Could not load knowledge base')
  } finally {
    loading.value = false
  }
}

onMounted(load)

// After an upload the doc embeds in the background — refetch shortly after.
function onUploaded() {
  setTimeout(load, 1500)
}

const unassigned = computed(() => documents.value.filter((d) => d.pool_assigned === false))
const grouped = computed(() => {
  const map = {}
  for (const p of pools.value) map[p.name] = []
  for (const d of documents.value) (map[d.pool] ||= []).push(d)
  return Object.entries(map).sort((a, b) => a[0].localeCompare(b[0]))
})

// ─── Move / assign modal ───
const moveOpen = ref(false)
const moving = ref(null)     // the document being moved
const targetPool = ref('')
// True while the PoolPicker has an unconfirmed new-pool name typed in — used
// to disable Save so the click can't discard the pool the user is creating.
const movePoolPending = ref(false)

function openMove(doc) {
  moving.value = doc
  targetPool.value = doc.pool
  movePoolPending.value = false
  moveOpen.value = true
}

async function confirmMove() {
  const doc = moving.value
  const dest = targetPool.value || 'General'
  try {
    await documentsApi.moveDocument(doc.file_name, doc.pool, dest)
    toast.success(dest === doc.pool ? `Kept in "${dest}"` : `Moved to "${dest}"`)
    moveOpen.value = false
    await load()
  } catch (e) {
    toast.error(e.message || 'Move failed')
  }
}

async function removeDoc(doc) {
  try {
    await documentsApi.deleteDocument(doc.file_name, doc.pool)
    toast.success(`Deleted "${doc.file_name}"`)
    await load()
  } catch (e) {
    toast.error(e.message || 'Delete failed')
  }
}

async function removePool(name) {
  try {
    await documentsApi.deletePool(name)
    toast.success(`Deleted pool "${name}"`)
    await load()
  } catch (e) {
    toast.error(e.message || 'Could not delete pool')
  }
}

// ─── Dedicated "create pool" flow — previously only possible as a side
// effect of uploading or moving a document (buried inside PoolPicker's
// inline "+ New" toggle). This gives it a clear, direct entry point. ───
const newPoolOpen = ref(false)
const newPoolName = ref('')
const creatingPool = ref(false)

function openNewPool() {
  newPoolName.value = ''
  newPoolOpen.value = true
}

async function createPool() {
  const name = newPoolName.value.trim()
  if (!name) return
  creatingPool.value = true
  try {
    await documentsApi.createPool(name)
    toast.success(`Pool "${name}" created`)
    newPoolOpen.value = false
    await load()
  } catch (e) {
    toast.error(e.message || 'Could not create pool')
  } finally {
    creatingPool.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-8">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold font-display text-ink">Knowledge Base</h1>
        <p class="text-ink-soft text-sm">Organize documents into pools.</p>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="secondary" @click="openNewPool"><Plus class="w-4 h-4" /> New pool</Button>
        <Button variant="ghost" @click="load"><RefreshCw class="w-4 h-4" /> Refresh</Button>
      </div>
    </div>

    <div class="grid gap-8 lg:grid-cols-[22rem_1fr]">
      <!-- Upload -->
      <div class="flex flex-col gap-6">
        <Card>
          <h2 class="text-lg font-semibold font-display text-ink mb-4">Upload</h2>
          <UploadDropzone :pools="pools" @uploaded="onUploaded" @pool-created="load" />
        </Card>
      </div>

      <!-- Documents -->
      <div class="flex flex-col gap-6">
        <!-- Needs-a-pool strip -->
        <Card v-if="unassigned.length" class="border-amber/40 bg-amber/5">
          <div class="flex items-center gap-2 mb-3">
            <AlertCircle class="w-5 h-5 text-amber" />
            <h3 class="font-semibold text-ink">{{ unassigned.length }} document{{ unassigned.length > 1 ? 's need' : ' needs' }} a pool</h3>
          </div>
          <ul class="flex flex-col divide-y divide-amber/20">
            <li v-for="d in unassigned" :key="d.key" class="flex items-center gap-3 py-2">
              <span class="text-sm text-ink flex-1 truncate">{{ d.file_name }}</span>
              <Button variant="secondary" @click="openMove(d)">Choose a pool</Button>
            </li>
          </ul>
        </Card>

        <div v-if="loading" class="text-sm text-ink-muted py-8 text-center">Loading…</div>

        <div v-else-if="documents.length === 0" class="flex flex-col items-center text-center py-12 gap-3">
          <IconChip color="indigo" size="lg"><Boxes class="w-6 h-6" /></IconChip>
          <p class="font-semibold text-ink">No documents yet</p>
          <p class="text-sm text-ink-soft max-w-sm">Upload your first document on the left to start a pool.</p>
        </div>

        <Card v-for="[name, docs] in grouped" v-else :key="name">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <h3 class="font-semibold font-display text-ink">{{ name }}</h3>
              <Badge color="indigo">{{ docs.length }}</Badge>
            </div>
            <button
              v-if="docs.length === 0 && name !== 'General'"
              class="text-ink-muted hover:text-rose cursor-pointer p-1" title="Delete empty pool" @click="removePool(name)"
            >
              <Trash2 class="w-4 h-4" />
            </button>
          </div>
          <p v-if="docs.length === 0" class="text-sm text-ink-muted py-2">Empty pool.</p>
          <ul v-else class="flex flex-col divide-y divide-border-subtle">
            <DocumentCard v-for="d in docs" :key="d.key" :document="d" @move="openMove" @delete="removeDoc" />
          </ul>
        </Card>
      </div>
    </div>

    <!-- Move / assign modal -->
    <Modal :open="moveOpen" title="Choose a pool" @close="moveOpen = false">
      <p class="text-sm text-ink-soft mb-4">
        Move <span class="font-semibold text-ink">{{ moving?.file_name }}</span> to a pool, or keep it where it is.
      </p>
      <PoolPicker v-model="targetPool" :pools="pools" :allow-empty="false" @created="load" @pending="movePoolPending = $event" />
      <p v-if="movePoolPending" class="text-xs text-ink-muted mt-2">Finish creating the new pool (✓) or pick an existing one to continue.</p>
      <div class="flex gap-2 mt-6">
        <Button variant="secondary" block @click="moveOpen = false">Cancel</Button>
        <Button block :disabled="movePoolPending" @click="confirmMove">Save</Button>
      </div>
    </Modal>

    <!-- Dedicated pool-creation flow -->
    <Modal :open="newPoolOpen" title="Create a knowledge pool" @close="newPoolOpen = false">
      <p class="text-sm text-ink-soft mb-4">
        Pools let you organize documents by topic, project, or team — chat and search can be scoped to just one.
      </p>
      <Input v-model="newPoolName" label="Pool name" placeholder="e.g. Finance, Legal, Product Docs" @keydown.enter.prevent="createPool" />
      <div class="flex gap-2 mt-6">
        <Button variant="secondary" block @click="newPoolOpen = false">Cancel</Button>
        <Button block :disabled="creatingPool || !newPoolName.trim()" @click="createPool">
          {{ creatingPool ? 'Creating…' : 'Create pool' }}
        </Button>
      </div>
    </Modal>
  </div>
</template>
