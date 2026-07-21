<script setup>
import { ref, onMounted } from 'vue'
import * as api from '../api/integrations.js'
import { useToastStore } from '../stores/toast.js'
import Button from './ui/Button.vue'
import Input from './ui/Input.vue'
import Badge from './ui/Badge.vue'
import IconChip from './ui/IconChip.vue'
import { Webhook, Trash2, Send, Plus, Copy } from 'lucide-vue-next'

const toast = useToastStore()
const hooks = ref([])
const loading = ref(true)

const url = ref('')
const selected = ref(['document.ingested'])
const creating = ref(false)

async function load() {
  loading.value = true
  try { hooks.value = (await api.fetchWebhooks()).webhooks || [] }
  catch (e) { toast.error(e.message) }
  finally { loading.value = false }
}
onMounted(load)

function toggle(ev) {
  selected.value = selected.value.includes(ev)
    ? selected.value.filter((e) => e !== ev)
    : [...selected.value, ev]
}

async function create() {
  if (!url.value.trim() || selected.value.length === 0) return
  creating.value = true
  try {
    await api.createWebhook(url.value.trim(), selected.value)
    toast.success('Webhook created')
    url.value = ''
    selected.value = ['document.ingested']
    await load()
  } catch (e) { toast.error(e.message) }
  finally { creating.value = false }
}

async function remove(h) {
  try { await api.deleteWebhook(h.webhook_id); toast.success('Webhook deleted'); await load() }
  catch (e) { toast.error(e.message) }
}

async function test(h) {
  try { await api.testWebhook(h.webhook_id); toast.success('Test event queued') }
  catch (e) { toast.error(e.message) }
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast.success('Secret copied') }
  catch (_) { toast.error('Copy failed') }
}

const shortEvent = (e) => e.replace('document.', '')
</script>

<template>
  <div>
    <form class="flex flex-col gap-3 mb-5" @submit.prevent="create">
      <Input v-model="url" label="Endpoint URL" placeholder="https://example.com/webhook" />
      <div>
        <p class="text-sm font-medium text-ink-soft mb-1.5">Events</p>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="ev in api.WEBHOOK_EVENTS" :key="ev" type="button" @click="toggle(ev)"
            class="px-3 py-1.5 rounded-full text-xs font-semibold border cursor-pointer transition-colors"
            :class="selected.includes(ev) ? 'vaultly-gradient text-white border-transparent' : 'border-border-subtle text-ink-soft hover:border-indigo/40'"
          >{{ shortEvent(ev) }}</button>
        </div>
      </div>
      <Button type="submit" :disabled="creating || !url.trim() || selected.length === 0" class="self-start">
        <Plus class="w-4 h-4" /> Add webhook
      </Button>
    </form>

    <div v-if="loading" class="text-sm text-ink-muted py-4">Loading…</div>
    <p v-else-if="hooks.length === 0" class="text-sm text-ink-soft py-2">No webhooks yet.</p>
    <ul v-else class="flex flex-col gap-3">
      <li v-for="h in hooks" :key="h.webhook_id" class="bg-surface-alt border border-border-subtle rounded-xl p-3">
        <div class="flex items-center gap-3">
          <IconChip color="pink" size="sm"><Webhook class="w-4 h-4" /></IconChip>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-ink truncate">{{ h.url }}</p>
            <div class="flex items-center gap-1.5 flex-wrap mt-1">
              <Badge v-for="ev in h.events" :key="ev" color="indigo">{{ shortEvent(ev) }}</Badge>
            </div>
          </div>
          <button class="text-ink-muted hover:text-indigo cursor-pointer p-1.5" title="Send test event" @click="test(h)"><Send class="w-4 h-4" /></button>
          <button class="text-ink-muted hover:text-rose cursor-pointer p-1.5" title="Delete" @click="remove(h)"><Trash2 class="w-4 h-4" /></button>
        </div>
        <div class="flex items-center gap-2 mt-2 pl-11 text-xs text-ink-soft">
          <span class="font-mono">secret: {{ h.secret.slice(0, 8) }}…</span>
          <button class="text-indigo hover:opacity-80 cursor-pointer" @click="copy(h.secret)"><Copy class="w-3.5 h-3.5" /></button>
          <span v-if="h.last_status" class="ml-auto">last: {{ h.last_status }}<span v-if="h.failure_count"> · {{ h.failure_count }} fails</span></span>
        </div>
      </li>
    </ul>
  </div>
</template>
