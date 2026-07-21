<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import Badge from './ui/Badge.vue'
import IconChip from './ui/IconChip.vue'
import { User, Sparkles, ChevronDown, Zap, Brain, SearchX, FolderOpen } from 'lucide-vue-next'

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

// GitHub-flavoured markdown; single newlines become <br> (chat-friendly).
marked.setOptions({ gfm: true, breaks: true })

// Render the streamed answer as sanitised HTML. Sanitising is not optional: the
// answer is synthesised from the user's own uploaded documents, so a malicious
// file could otherwise inject markup/script. Recomputes on each streamed token.
const renderedAnswer = computed(() =>
  DOMPurify.sanitize(marked.parse(props.answer || '', { async: false })),
)

// Distinct pool(s) the answer's passages actually came from — shown as a badge
// so it's clear at a glance which knowledge pool a reply is grounded in.
const sourcePools = computed(() => [
  ...new Set((props.sources || []).map((s) => s.pool).filter(Boolean)),
])
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

        <!-- Which knowledge pool(s) this answer is grounded in -->
        <div v-if="!refused && sourcePools.length" class="flex flex-wrap items-center gap-1 mb-1.5">
          <Badge v-for="p in sourcePools" :key="p" color="indigo">
            <FolderOpen class="w-3 h-3" /> {{ p }}
          </Badge>
        </div>

        <div
          class="rounded-2xl rounded-tl-sm px-4 py-3 shadow-[0_8px_24px_rgba(99,102,241,0.08)]"
          :class="refused ? 'bg-amber/5 border border-amber/30' : 'bg-surface border border-border-subtle'"
        >
          <div class="text-sm leading-relaxed" :class="refused ? 'text-ink-soft' : 'text-ink'">
            <div class="markdown" v-html="renderedAnswer" /><span v-if="streaming" class="inline-block w-1.5 h-4 bg-pink ml-0.5 align-middle animate-pulse" />
          </div>

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

<style scoped>
/* Markdown rendered via v-html — Tailwind preflight resets these elements, so
   restore chat-friendly typography. :deep() pierces the scope into v-html. */
.markdown :deep(p) { margin: 0 0 0.5rem; }
.markdown :deep(h1:first-child),
.markdown :deep(h2:first-child),
.markdown :deep(h3:first-child),
.markdown :deep(p:first-child) { margin-top: 0; }
.markdown :deep(p:last-child),
.markdown :deep(ul:last-child),
.markdown :deep(ol:last-child) { margin-bottom: 0; }
.markdown :deep(ul),
.markdown :deep(ol) { margin: 0.25rem 0 0.5rem; padding-left: 1.25rem; }
.markdown :deep(ul) { list-style: disc; }
.markdown :deep(ol) { list-style: decimal; }
.markdown :deep(li) { margin: 0.15rem 0; }
.markdown :deep(li > ul),
.markdown :deep(li > ol) { margin: 0.15rem 0; }
.markdown :deep(strong) { font-weight: 600; }
.markdown :deep(em) { font-style: italic; }
.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3),
.markdown :deep(h4) { font-weight: 700; line-height: 1.3; margin: 0.75rem 0 0.375rem; }
.markdown :deep(h1) { font-size: 1.15rem; }
.markdown :deep(h2) { font-size: 1.05rem; }
.markdown :deep(h3) { font-size: 1rem; }
.markdown :deep(a) { color: var(--color-indigo); text-decoration: underline; }
.markdown :deep(code) {
  font-family: var(--font-mono); font-size: 0.85em;
  background: var(--color-surface-alt); border: 1px solid var(--color-border-subtle);
  border-radius: 4px; padding: 0.05rem 0.3rem;
}
.markdown :deep(pre) {
  background: var(--color-surface-alt); border: 1px solid var(--color-border-subtle);
  border-radius: 8px; padding: 0.75rem; overflow-x: auto; margin: 0.5rem 0;
}
.markdown :deep(pre code) { background: none; border: none; padding: 0; font-size: 0.85em; }
.markdown :deep(blockquote) {
  border-left: 3px solid var(--color-border-subtle);
  padding-left: 0.75rem; color: var(--color-ink-soft); margin: 0.5rem 0;
}
.markdown :deep(table) {
  border-collapse: collapse; margin: 0.5rem 0; font-size: 0.9em;
  display: block; overflow-x: auto;
}
.markdown :deep(th),
.markdown :deep(td) { border: 1px solid var(--color-border-subtle); padding: 0.3rem 0.5rem; text-align: left; }
.markdown :deep(hr) { border: none; border-top: 1px solid var(--color-border-subtle); margin: 0.75rem 0; }
</style>
