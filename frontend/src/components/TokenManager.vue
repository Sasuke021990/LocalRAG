<script setup>
import { ref, onMounted } from 'vue'
import * as api from '../api/integrations.js'
import { useToastStore } from '../stores/toast.js'
import Button from './ui/Button.vue'
import Input from './ui/Input.vue'
import Modal from './ui/Modal.vue'
import IconChip from './ui/IconChip.vue'
import { KeyRound, Copy, Trash2, Plus } from 'lucide-vue-next'

const toast = useToastStore()
const tokens = ref([])
const loading = ref(true)
const newName = ref('')
const creating = ref(false)

// Show-once modal
const revealed = ref(null) // { token, name, prefix }

async function load() {
  loading.value = true
  try { tokens.value = (await api.fetchTokens()).tokens || [] }
  catch (e) { toast.error(e.message) }
  finally { loading.value = false }
}
onMounted(load)

async function create() {
  const name = newName.value.trim()
  if (!name) return
  creating.value = true
  try {
    revealed.value = await api.createToken(name)
    newName.value = ''
    await load()
  } catch (e) { toast.error(e.message) }
  finally { creating.value = false }
}

async function revoke(t) {
  try {
    await api.revokeToken(t.token_id)
    toast.success(`Revoked "${t.name}"`)
    await load()
  } catch (e) { toast.error(e.message) }
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast.success('Copied to clipboard') }
  catch (_) { toast.error('Copy failed — select and copy manually') }
}
</script>

<template>
  <div>
    <form class="flex items-end gap-2 mb-5" @submit.prevent="create">
      <div class="flex-1">
        <Input v-model="newName" label="New API token" placeholder="e.g. Claude Desktop" />
      </div>
      <Button type="submit" :disabled="creating || !newName.trim()"><Plus class="w-4 h-4" /> Create</Button>
    </form>

    <div v-if="loading" class="text-sm text-ink-muted py-4">Loading…</div>
    <p v-else-if="tokens.length === 0" class="text-sm text-ink-soft py-2">No tokens yet. Create one to connect an AI client.</p>
    <ul v-else class="flex flex-col divide-y divide-border-subtle">
      <li v-for="t in tokens" :key="t.token_id" class="flex items-center gap-3 py-3">
        <IconChip color="indigo" size="sm"><KeyRound class="w-4 h-4" /></IconChip>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-ink truncate">{{ t.name }}</p>
          <p class="text-xs text-ink-soft font-mono">{{ t.prefix }}… · {{ t.last_used_at ? 'last used ' + t.last_used_at.slice(0, 10) : 'never used' }}</p>
        </div>
        <button class="text-ink-muted hover:text-rose cursor-pointer p-1.5" title="Revoke" @click="revoke(t)">
          <Trash2 class="w-4 h-4" />
        </button>
      </li>
    </ul>

    <!-- Show-once token reveal -->
    <Modal :open="!!revealed" title="Copy your token now" @close="revealed = null">
      <p class="text-sm text-ink-soft mb-3">
        This is the only time <span class="font-semibold text-ink">{{ revealed?.name }}</span> will be shown. Store it securely.
      </p>
      <div class="flex items-center gap-2 bg-surface-alt border border-border-subtle rounded-xl p-3">
        <code class="flex-1 text-xs text-ink font-mono break-all">{{ revealed?.token }}</code>
        <button class="text-indigo hover:opacity-80 cursor-pointer shrink-0" @click="copy(revealed.token)">
          <Copy class="w-4 h-4" />
        </button>
      </div>
      <Button class="mt-5" block @click="revealed = null">Done</Button>
    </Modal>
  </div>
</template>
