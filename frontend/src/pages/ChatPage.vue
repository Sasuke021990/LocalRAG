<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { streamQuery } from '../api/query.js'
import { fetchDocuments, fetchPools } from '../api/documents.js'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import IconChip from '../components/ui/IconChip.vue'
import Modal from '../components/ui/Modal.vue'
import ChatMessage from '../components/ChatMessage.vue'
import { Sparkles, Send, Boxes, ChevronDown, Check } from 'lucide-vue-next'

const query = ref('')
const history = ref([])
const loading = ref(false)
const listEnd = ref(null)
const documents = ref([])
const pools = ref([])
const selectedPool = ref('')      // '' = search across all pools
const poolChosen = ref(false)     // has the user made an explicit choice (incl. "All pools") yet
const poolPopupOpen = ref(false)

// Fixed retrieval depth: fetch 40 candidates, rerank, keep the top 20 passages.
const RETRIEVE_K = 20

// Load the user's documents (for tailored prompts) and pools (for the picker),
// then gate entry behind the pool-selection popup — replaces the old always-
// visible inline dropdown. Re-opens every time this page is entered.
onMounted(async () => {
  try {
    documents.value = (await fetchDocuments()).documents || []
  } catch (_) { /* no docs / not ready — fall back to the generic prompts */ }
  try {
    pools.value = (await fetchPools()).pools || []
  } catch (_) { /* no pools yet — the popup still offers "All pools" */ }
  poolPopupOpen.value = true
})

function choosePool(name) {
  selectedPool.value = name
  poolChosen.value = true
  poolPopupOpen.value = false
}

// Dismissing without an explicit pick (backdrop click / X) is treated as
// choosing "All pools" — never leaves the user stuck with no way in.
function dismissPoolPopup() {
  choosePool(selectedPool.value)
}

// Quick-start prompt chips, tailored to the selected pool: "Summarise <doc>"
// for docs in that pool (all pools when none is selected), then a few prompts.
const suggestions = computed(() => {
  const pool = selectedPool.value
  const inScope = pool ? documents.value.filter((d) => d.pool === pool) : documents.value
  const docChips = inScope.slice(0, 3).map((d) => `Summarise ${d.file_name}`)
  const generic = pool
    ? [`Summarise the ${pool} pool`, 'What are the key points?', 'List the pros and cons']
    : ['What are the key points?', 'Explain in simple terms', 'List the pros and cons']
  return [...docChips, ...generic].slice(0, 5)
})

function useSuggestion(text) {
  if (loading.value) return
  query.value = text
  submit()
}

async function scrollDown() {
  await nextTick()
  listEnd.value?.scrollIntoView({ behavior: 'smooth' })
}

function submit() {
  const q = query.value.trim()
  if (!q || loading.value) return
  loading.value = true
  query.value = ''

  // A reactive object we mutate as tokens arrive. It MUST be reactive():
  // the stream handlers below mutate `m` directly, and only a reactive proxy
  // propagates those mutations to the template. A plain object pushed into the
  // array is exposed to the render as a *separate* reactive proxy, so mutating
  // the raw object never triggers a re-render and the answer bubble stays empty
  // while tokens stream in.
  const m = reactive({
    query: q, answer: '', reasoning: '', sources: [], refused: false, streaming: true,
    processingTime: undefined, queryPool: selectedPool.value,
  })
  history.value.push(m)
  const started = performance.now()
  scrollDown()

  streamQuery(q, { topK: RETRIEVE_K * 2, rerankTopK: RETRIEVE_K, pool: selectedPool.value }, {
    onSources: (list) => { m.sources = list },
    onThinking: (t) => { m.reasoning += t; scrollDown() },
    onToken: (t) => { m.answer += t; scrollDown() },
    onRefusal: (msg) => { m.answer = msg; m.refused = true },
    onDone: (data) => {
      if (data.answer) m.answer = data.answer
      m.reasoning = data.reasoning || m.reasoning
      m.refused = data.refused
      m.streaming = false
      m.processingTime = data.cached ? 0 : (performance.now() - started) / 1000
      loading.value = false
      scrollDown()
    },
    onError: (err) => {
      m.answer = m.answer || err.message || 'Something went wrong.'
      m.streaming = false
      loading.value = false
    },
  })
}
</script>

<template>
  <div class="flex flex-col gap-6 h-[calc(100vh-9rem)]">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold font-display text-ink">Chat</h1>
        <p class="text-ink-soft text-sm">Answers come only from your documents.</p>
      </div>
      <!-- Shows the current scope; click to switch pools mid-conversation
           (reopens the same popup shown on entry). -->
      <button
        type="button" title="Change knowledge pool"
        class="flex items-center gap-1.5 rounded-xl border border-border-subtle bg-surface px-3 py-2 text-sm text-ink-soft hover:border-indigo hover:text-indigo transition cursor-pointer"
        @click="poolPopupOpen = true"
      >
        <Boxes class="w-4 h-4" />
        {{ selectedPool || 'All pools' }}
        <ChevronDown class="w-3.5 h-3.5" />
      </button>
    </div>

    <div class="flex-1 overflow-y-auto flex flex-col gap-6 pr-1">
      <div v-if="history.length === 0" class="flex flex-col items-center justify-center text-center h-full gap-3">
        <IconChip color="pink" size="lg"><Sparkles class="w-6 h-6" /></IconChip>
        <p class="font-semibold text-ink">Ask anything about your documents</p>
        <p class="text-sm text-ink-soft max-w-sm">Vaultly searches your knowledge base and answers with citations — never from outside knowledge.</p>
      </div>

      <ChatMessage v-for="(m, i) in history" :key="i" v-bind="m" />
      <div ref="listEnd" />
    </div>

    <!-- Quick-start prompt chips (tailored to the user's documents) -->
    <div v-if="poolChosen && suggestions.length" class="shrink-0 flex gap-2 overflow-x-auto pb-0.5">
      <button
        v-for="(s, i) in suggestions" :key="i"
        type="button" :disabled="loading" @click="useSuggestion(s)"
        class="whitespace-nowrap text-xs px-3 py-1.5 rounded-full border border-border-subtle bg-surface text-ink-soft hover:border-indigo hover:text-indigo transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {{ s }}
      </button>
    </div>

    <Card class="shrink-0" :padded="false">
      <form class="flex items-end gap-2 p-3" @submit.prevent="submit">
        <textarea
          v-model="query" rows="1" placeholder="Ask a question…"
          class="flex-1 resize-none bg-transparent px-2 py-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none max-h-32"
          @keydown.enter.exact.prevent="submit"
        />
        <Button type="submit" :disabled="loading || !query.trim()">
          <Send class="w-4 h-4" />
        </Button>
      </form>
    </Card>

    <!-- Pool-selection popup: shown on entry, and again via the pill above to
         switch pools mid-conversation. Dismissing without a pick keeps/defaults
         to "All pools" rather than trapping the user. -->
    <Modal :open="poolPopupOpen" title="Choose a knowledge pool" @close="dismissPoolPopup">
      <p class="text-sm text-ink-soft mb-4">
        Vaultly will search only this pool while you chat. You can switch anytime.
      </p>
      <div class="flex flex-col gap-2 max-h-80 overflow-y-auto">
        <button
          type="button"
          class="flex items-center justify-between gap-2 rounded-xl border px-4 py-3 text-left transition cursor-pointer"
          :class="selectedPool === '' ? 'border-indigo bg-indigo/5' : 'border-border-subtle hover:border-indigo/40'"
          @click="choosePool('')"
        >
          <span class="text-sm font-medium text-ink">All pools</span>
          <Check v-if="selectedPool === ''" class="w-4 h-4 text-indigo shrink-0" />
        </button>
        <button
          v-for="p in pools" :key="p.name"
          type="button"
          class="flex items-center justify-between gap-2 rounded-xl border px-4 py-3 text-left transition cursor-pointer"
          :class="selectedPool === p.name ? 'border-indigo bg-indigo/5' : 'border-border-subtle hover:border-indigo/40'"
          @click="choosePool(p.name)"
        >
          <span class="text-sm font-medium text-ink truncate">{{ p.name }}</span>
          <span class="flex items-center gap-2 shrink-0">
            <span class="text-xs text-ink-muted">{{ p.document_count }} doc{{ p.document_count === 1 ? '' : 's' }}</span>
            <Check v-if="selectedPool === p.name" class="w-4 h-4 text-indigo" />
          </span>
        </button>
        <p v-if="pools.length === 0" class="text-sm text-ink-muted text-center py-3">
          No pools yet — "All pools" works fine until you create one.
        </p>
      </div>
    </Modal>
  </div>
</template>
