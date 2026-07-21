<script setup>
import { ref } from 'vue'
import Badge from './ui/Badge.vue'
import IconChip from './ui/IconChip.vue'
import { User, Sparkles, ChevronDown, Zap, Brain, SearchX } from 'lucide-vue-next'

const props = defineProps({
  query: String,
  answer: String,
  reasoning: { type: String, default: '' },
  sources: { type: Array, default: () => [] },
  refused: Boolean,
  streaming: Boolean,
  processingTime: Number,
})

const showSources = ref(false)
const showThinking = ref(false)
</script>

<template>
  <div class="flex flex-col gap-3">
    <!-- User query -->
    <div class="flex items-start gap-3 justify-end">
      <div class="bg-indigo/8 rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[80%]">
        <p class="text-sm text-ink">{{ query }}</p>
      </div>
      <IconChip color="indigo" size="sm"><User class="w-4 h-4" /></IconChip>
    </div>

    <!-- AI answer -->
    <div class="flex items-start gap-3">
      <IconChip :color="refused ? 'amber' : 'pink'" size="sm">
        <SearchX v-if="refused" class="w-4 h-4" />
        <Sparkles v-else class="w-4 h-4" />
      </IconChip>
      <div class="flex-1 min-w-0">
        <!-- Thinking (collapsible, only when reasoning present) -->
        <div v-if="reasoning" class="mb-2">
          <button class="flex items-center gap-1.5 text-xs font-semibold text-indigo hover:opacity-80 cursor-pointer" @click="showThinking = !showThinking">
            <Brain class="w-3.5 h-3.5" />
            {{ streaming ? 'Thinking…' : 'Thinking' }}
            <ChevronDown class="w-3.5 h-3.5 transition-transform" :class="showThinking ? 'rotate-180' : ''" />
          </button>
          <p v-if="showThinking" class="mt-2 text-xs text-ink-soft bg-surface-alt border border-border-subtle rounded-xl p-3 whitespace-pre-wrap">{{ reasoning }}</p>
        </div>

        <div
          class="rounded-2xl rounded-tl-sm px-4 py-3 shadow-[0_8px_24px_rgba(99,102,241,0.08)]"
          :class="refused ? 'bg-amber/5 border border-amber/30' : 'bg-surface border border-border-subtle'"
        >
          <p class="text-sm whitespace-pre-wrap leading-relaxed" :class="refused ? 'text-ink-soft' : 'text-ink'">
            {{ answer }}<span v-if="streaming" class="inline-block w-1.5 h-4 bg-pink ml-0.5 align-middle animate-pulse" />
          </p>

          <div v-if="!refused && sources.length" class="mt-3 pt-3 border-t border-border-subtle">
            <button class="flex items-center gap-1.5 text-xs font-semibold text-ink-soft hover:text-indigo cursor-pointer" @click="showSources = !showSources">
              <ChevronDown class="w-3.5 h-3.5 transition-transform" :class="showSources ? 'rotate-180' : ''" />
              {{ sources.length }} source{{ sources.length > 1 ? 's' : '' }}
            </button>
            <ul v-if="showSources" class="flex flex-col gap-2 mt-3">
              <li v-for="(s, i) in sources" :key="i" class="bg-surface-alt rounded-xl p-3 border border-border-subtle">
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <span class="text-xs font-semibold text-ink truncate">{{ s.file_name }}</span>
                  <Badge color="pink">pool: {{ s.pool }}</Badge>
                  <span class="text-xs font-mono text-ink-muted">{{ (s.score * 100).toFixed(0) }}%</span>
                </div>
                <p class="text-xs text-ink-soft line-clamp-3">{{ s.content }}</p>
              </li>
            </ul>
          </div>
        </div>

        <p v-if="processingTime !== undefined" class="text-xs mt-1.5 flex items-center gap-1"
           :class="processingTime === 0 ? 'text-emerald' : 'text-ink-muted'">
          <Zap v-if="processingTime === 0" class="w-3 h-3" />
          {{ processingTime === 0 ? 'Instant (cached)' : `${(processingTime * 1000).toFixed(0)}ms` }}
        </p>
      </div>
    </div>
  </div>
</template>
