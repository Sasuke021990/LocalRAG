<script setup>
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { sendQuery } from '../api/query.js'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import IconChip from '../components/ui/IconChip.vue'
import ChatMessage from '../components/ChatMessage.vue'
import { Sparkles, Send, SlidersHorizontal } from 'lucide-vue-next'

const router = useRouter()
const query = ref('')
const topK = ref(10)
const useReranker = ref(true)
const history = ref([])
const loading = ref(false)
const error = ref('')
const showControls = ref(false)
const listEnd = ref(null)

async function submit() {
  const q = query.value.trim()
  if (!q || loading.value) return
  error.value = ''
  loading.value = true
  query.value = ''
  try {
    const rerankTopK = useReranker.value ? topK.value : 0
    const fetchK = useReranker.value ? topK.value * 2 : topK.value
    const res = await sendQuery(q, fetchK, rerankTopK)
    history.value.push({
      query: q,
      answer: res.answer || 'No answer generated.',
      sources: res.sources || [],
      processingTime: res.processing_time,
    })
    await nextTick()
    listEnd.value?.scrollIntoView({ behavior: 'smooth' })
  } catch (e) {
    error.value = e.message || 'Query failed'
  } finally {
    loading.value = false
  }
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

    <!-- Conversation -->
    <div class="flex-1 overflow-y-auto flex flex-col gap-6 pr-1">
      <div v-if="history.length === 0" class="flex flex-col items-center justify-center text-center h-full gap-3">
        <IconChip color="pink" size="lg"><Sparkles class="w-6 h-6" /></IconChip>
        <p class="font-semibold text-ink">Ask anything about your documents</p>
        <p class="text-sm text-ink-soft max-w-sm">Vaultly searches your knowledge base and answers with citations — never from outside knowledge.</p>
      </div>

      <ChatMessage v-for="(m, i) in history" :key="i" v-bind="m" />

      <div v-if="loading" class="flex items-center gap-2 text-sm text-ink-soft">
        <span class="w-2 h-2 rounded-full bg-pink animate-pulse" />
        Searching your vault…
      </div>
      <div ref="listEnd" />
    </div>

    <p v-if="error" class="text-sm text-rose shrink-0">{{ error }}</p>

    <!-- Composer -->
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
