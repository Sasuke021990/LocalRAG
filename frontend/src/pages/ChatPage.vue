<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { streamQuery } from '../api/query.js'
import { fetchDocuments, fetchPools } from '../api/documents.js'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import IconChip from '../components/ui/IconChip.vue'
import ChatMessage from '../components/ChatMessage.vue'
import { Sparkles, Send } from 'lucide-vue-next'

const query = ref('')
const history = ref([])
const loading = ref(false)
const listEnd = ref(null)
const documents = ref([])
const pools = ref([])
const selectedPool = ref('')   // '' = search across all pools

// Fixed retrieval depth: fetch 40 candidates, rerank, keep the top 20 passages.
const RETRIEVE_K = 20

// Load the user's documents (for tailored prompts) and pools (for the picker).
onMounted(async () => {
  try {
    documents.value = (await fetchDocuments()).documents || []
  } catch (_) { /* no docs / not ready — fall back to the generic prompts */ }
  try {
    pools.value = (await fetchPools()).pools || []
  } catch (_) { /* no pools yet — the picker just shows "All pools" */ }
})

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
      <div class="flex items-center gap-2">
        <!-- Restrict the model to one knowledge pool (or search across all). -->
        <label class="text-sm text-ink-soft">Pool</label>
        <select
          v-model="selectedPool"
          title="Which knowledge pool to search"
          class="rounded-xl border border-border-subtle bg-surface px-3 py-2 text-sm text-ink-soft focus:border-indigo cursor-pointer max-w-48"
        >
          <option value="">All pools</option>
          <option v-for="p in pools" :key="p.name" :value="p.name">
            {{ p.name }} ({{ p.document_count }})
          </option>
        </select>
      </div>
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
    <div v-if="suggestions.length" class="shrink-0 flex gap-2 overflow-x-auto pb-0.5">
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
  </div>
</template>
