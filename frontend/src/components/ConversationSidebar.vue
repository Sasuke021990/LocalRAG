<script setup>
import { ref } from 'vue'
import Button from './ui/Button.vue'
import Modal from './ui/Modal.vue'
import { timeAgo } from '../utils/format.js'
import { Plus, Pencil, Trash2, Check, X, MessageSquare } from 'lucide-vue-next'

defineProps({
  conversations: { type: Array, default: () => [] },
  activeId: { type: String, default: '' },
  loading: Boolean,
})
const emit = defineEmits(['select', 'new-chat', 'rename', 'delete'])

const editingId = ref('')
const draftTitle = ref('')

function startEdit(conv) {
  editingId.value = conv.id
  draftTitle.value = conv.title
}
function commitEdit(conv) {
  const title = draftTitle.value.trim()
  if (title && title !== conv.title) emit('rename', conv, title)
  editingId.value = ''
}
function cancelEdit() {
  editingId.value = ''
}

const deleteTarget = ref(null)
function doDelete() {
  emit('delete', deleteTarget.value)
  deleteTarget.value = null
}
</script>

<template>
  <aside class="flex flex-col h-full w-64 shrink-0 border-r border-border-subtle pr-3">
    <Button block class="mb-3 shrink-0" @click="$emit('new-chat')">
      <Plus class="w-4 h-4" /> New chat
    </Button>

    <div class="flex-1 overflow-y-auto flex flex-col gap-1">
      <div v-if="loading" class="text-xs text-ink-muted text-center py-6">Loading…</div>

      <div v-else-if="conversations.length === 0" class="flex flex-col items-center text-center gap-2 py-8 px-2">
        <MessageSquare class="w-5 h-5 text-ink-muted" />
        <p class="text-xs text-ink-muted">No conversations yet — send a message to start one.</p>
      </div>

      <div
        v-for="c in conversations" :key="c.id"
        class="group flex items-start gap-1.5 rounded-xl px-2.5 py-2 cursor-pointer transition"
        :class="c.id === activeId ? 'bg-indigo/8' : 'hover:bg-surface-alt'"
        @click="editingId !== c.id && $emit('select', c)"
      >
        <div class="flex-1 min-w-0">
          <div v-if="editingId === c.id" class="flex items-center gap-1" @click.stop>
            <input
              v-model="draftTitle" autofocus
              class="flex-1 min-w-0 text-sm rounded-lg border border-indigo/40 bg-surface px-2 py-1 focus:outline-none"
              @keydown.enter.prevent="commitEdit(c)" @keydown.esc.prevent="cancelEdit"
            />
            <button type="button" class="text-emerald cursor-pointer p-1" title="Save" @click="commitEdit(c)"><Check class="w-3.5 h-3.5" /></button>
            <button type="button" class="text-ink-muted cursor-pointer p-1" title="Cancel" @click="cancelEdit"><X class="w-3.5 h-3.5" /></button>
          </div>
          <template v-else>
            <p class="text-sm font-medium truncate" :class="c.id === activeId ? 'text-indigo' : 'text-ink'">{{ c.title }}</p>
            <p class="text-xs text-ink-muted truncate">{{ c.preview || 'No messages yet' }}</p>
            <p class="text-[11px] text-ink-muted mt-0.5">{{ timeAgo(c.updated_at) }}<span v-if="c.pool"> · {{ c.pool }}</span></p>
          </template>
        </div>

        <div v-if="editingId !== c.id" class="hidden group-hover:flex items-center gap-0.5 shrink-0">
          <button type="button" class="text-ink-muted hover:text-indigo cursor-pointer p-1" title="Rename" @click.stop="startEdit(c)">
            <Pencil class="w-3.5 h-3.5" />
          </button>
          <button type="button" class="text-ink-muted hover:text-rose cursor-pointer p-1" title="Delete" @click.stop="deleteTarget = c">
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>

    <Modal :open="!!deleteTarget" title="Delete conversation?" @close="deleteTarget = null">
      <p class="text-sm text-ink-soft mb-6">
        This permanently deletes <span class="font-semibold text-ink">{{ deleteTarget?.title }}</span> and its messages. This can't be undone.
      </p>
      <div class="flex gap-2">
        <Button variant="secondary" block @click="deleteTarget = null">Cancel</Button>
        <Button variant="danger" block @click="doDelete">Delete</Button>
      </div>
    </Modal>
  </aside>
</template>
