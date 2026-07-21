<script setup>
import { ref, nextTick } from 'vue'
import { streamQuery } from '../api/query.js'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import IconChip from '../components/ui/IconChip.vue'
import ChatMessage from '../components/ChatMessage.vue'
import { Sparkles, Send, SlidersHorizontal } from 'lucide-vue-next'

const query = ref('')
const topK = ref(10)
const useReranker = ref(true)
const history = ref([])
const loading = ref(false)
const showControls = ref(false)
const listEnd = ref(null)

async function scrollDown() {
  await nextTick()
  listEnd.value?.scrollIntoView({ behavior: 'smooth' })
}

function submit() {
  const q = query.value.trim()
  if (!q || loading.value) return
  loading.value = true
  query.value = ''

  // Push a plain object we mutate as tokens arrive (Vue deep reactivity).
  const m = { query: q, answer: '', reasoning: '', sources: [], refused: false, streaming: true, processingTime: undefined }
  history.value.push(m)
  const started = performance.now()
  scrollDown()

  streamQuery(q, { topK: useReranker.value ? topK.value * 2 : topK.value, rerankTopK: useReranker.value ? topK.value : 0 }, {
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
      m.answer = m.answer || `Something went wrong: ${err.message}`
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
      <Button variant="ghost" @click="showControls = !showControls">
        <SlidersHorizontal class="w-4 h-4" /> Retrieval
      </Button>
    </div>

    <Card v-if="showControls" class="shrink-0">
      <div class="flex flex-col sm:flex-row gap-6">
        <label class="flex-1">
          <span class="text-sm font-medium text-ink-soft">Passages to retrieve: <span class="font-mono text-indigo">{{ topK }}</span></span>
          <input type="range" min="3" max="30" v-model.number="topK" class="w-full mt-2 accent-[#6366F1]" />
        </label>
        <label class="flex items-center gap-2 text-sm text-ink-soft">
          <input type="checkbox" v-model="useReranker" class="accent-[#6366F1] w-4 h-4" />
          Cross-encoder rerank
        </label>
      </div>
    </Card>

    <div class="flex-1 overflow-y-auto flex flex-col gap-6 pr-1">
      <div v-if="history.length === 0" class="flex flex-col items-center justify-center text-center h-full gap-3">
        <IconChip color="pink" size="lg"><Sparkles class="w-6 h-6" /></IconChip>
        <p class="font-semibold text-ink">Ask anything about your documents</p>
        <p class="text-sm text-ink-soft max-w-sm">Vaultly searches your knowledge base and answers with citations — never from outside knowledge.</p>
      </div>

      <ChatMessage v-for="(m, i) in history" :key="i" v-bind="m" />
      <div ref="listEnd" />
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
