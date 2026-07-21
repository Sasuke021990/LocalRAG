<script setup>
import { ref, onMounted, computed } from 'vue'
import * as admin from '../api/admin.js'
import { useAuthStore } from '../stores/auth.js'
import { useToastStore } from '../stores/toast.js'
import { formatBytes, bytesToGb, gbToBytes } from '../utils/format.js'
import Card from '../components/ui/Card.vue'
import Button from '../components/ui/Button.vue'
import Badge from '../components/ui/Badge.vue'
import Input from '../components/ui/Input.vue'
import Modal from '../components/ui/Modal.vue'
import IconChip from '../components/ui/IconChip.vue'
import { Users, ShieldCheck, HardDrive, FileText, RefreshCw, Trash2, HardDriveUpload } from 'lucide-vue-next'

const auth = useAuthStore()
const toast = useToastStore()
const stats = ref(null)
const settings = ref({ signups_enabled: true, default_storage_quota_bytes: 0 })
const users = ref([])
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const [s, cfg, u] = await Promise.all([admin.fetchStats(), admin.fetchSettings(), admin.fetchUsers()])
    stats.value = s
    settings.value = cfg.settings
    users.value = u.users || []
  } catch (e) { toast.error(e.message) }
  finally { loading.value = false }
}
onMounted(load)

const statCards = computed(() => stats.value ? [
  { label: 'Users', value: stats.value.total_users, sub: `${stats.value.active_users} active`, icon: Users, color: 'indigo' },
  { label: 'Admins', value: stats.value.admin_users, icon: ShieldCheck, color: 'pink' },
  { label: 'Storage used', value: formatBytes(stats.value.total_storage_used_bytes), icon: HardDrive, color: 'emerald' },
  { label: 'Documents', value: stats.value.total_documents, sub: `${stats.value.total_tokens} tokens · ${stats.value.total_webhooks} webhooks`, icon: FileText, color: 'amber' },
] : [])

const isSelf = (u) => u.user_id === auth.user?.user_id

// ─── Settings ───
async function toggleSignups() {
  try {
    await admin.updateSetting('signups_enabled', !settings.value.signups_enabled)
    settings.value.signups_enabled = !settings.value.signups_enabled
    toast.success(`Signups ${settings.value.signups_enabled ? 'enabled' : 'disabled'}`)
  } catch (e) { toast.error(e.message) }
}
const defaultGb = ref(0)
async function saveDefaultQuota() {
  try {
    const bytes = gbToBytes(defaultGb.value)
    await admin.updateSetting('default_storage_quota_bytes', bytes)
    settings.value.default_storage_quota_bytes = bytes
    toast.success('Default quota updated')
  } catch (e) { toast.error(e.message) }
}

// ─── User actions ───
async function toggleActive(u) {
  try { const r = await admin.setActive(u.user_id, !u.is_active); Object.assign(u, r); toast.success('Updated') }
  catch (e) { toast.error(e.message) }
}
async function toggleAdmin(u) {
  try { const r = await admin.setAdmin(u.user_id, !u.is_admin); Object.assign(u, r); toast.success('Updated') }
  catch (e) { toast.error(e.message) }
}

// Quota modal
const quotaUser = ref(null)
const quotaGb = ref(0)
function openQuota(u) { quotaUser.value = u; quotaGb.value = bytesToGb(u.storage_quota_bytes) }
async function saveQuota() {
  try {
    const r = await admin.setQuota(quotaUser.value.user_id, gbToBytes(quotaGb.value))
    Object.assign(quotaUser.value, r)
    toast.success('Quota updated')
    quotaUser.value = null
  } catch (e) { toast.error(e.message) }
}

// Delete modal
const deleteTarget = ref(null)
async function confirmDelete() {
  try {
    await admin.deleteUser(deleteTarget.value.user_id)
    toast.success(`Deleted ${deleteTarget.value.email}`)
    deleteTarget.value = null
    await load()
  } catch (e) { toast.error(e.message) }
}
</script>

<template>
  <div class="flex flex-col gap-8">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold font-display text-ink">Admin</h1>
        <p class="text-ink-soft text-sm">Metadata only — document contents are never accessible here.</p>
      </div>
      <Button variant="ghost" @click="load"><RefreshCw class="w-4 h-4" /> Refresh</Button>
    </div>

    <!-- Stats -->
    <div class="grid gap-5 grid-cols-2 lg:grid-cols-4">
      <Card v-for="c in statCards" :key="c.label" interactive>
        <IconChip :color="c.color"><component :is="c.icon" class="w-5 h-5" /></IconChip>
        <p class="text-2xl font-bold font-mono text-ink mt-4">{{ c.value }}</p>
        <p class="text-sm text-ink-soft">{{ c.label }}</p>
        <p v-if="c.sub" class="text-xs text-ink-muted mt-1">{{ c.sub }}</p>
      </Card>
    </div>

    <!-- Settings -->
    <Card>
      <h2 class="text-lg font-semibold font-display text-ink mb-4">System settings</h2>
      <div class="flex flex-col gap-4">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-ink">Public signups</p>
            <p class="text-xs text-ink-soft">Allow new accounts to register.</p>
          </div>
          <button
            class="relative w-11 h-6 rounded-full transition-colors cursor-pointer"
            :class="settings.signups_enabled ? 'vaultly-gradient' : 'bg-ink-muted/40'"
            @click="toggleSignups"
          >
            <span class="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform" :class="settings.signups_enabled ? 'translate-x-5' : ''" />
          </button>
        </div>
        <div class="flex items-end gap-2">
          <div class="flex-1 max-w-xs">
            <Input v-model.number="defaultGb" type="number" label="Default quota for new users (GB)"
              :placeholder="String(bytesToGb(settings.default_storage_quota_bytes))" />
          </div>
          <Button variant="secondary" @click="saveDefaultQuota">Save</Button>
          <span class="text-xs text-ink-muted pb-3">current: {{ formatBytes(settings.default_storage_quota_bytes) }}</span>
        </div>
      </div>
    </Card>

    <!-- Users -->
    <Card :padded="false">
      <div class="p-6 pb-3"><h2 class="text-lg font-semibold font-display text-ink">Users</h2></div>
      <div v-if="loading" class="p-6 text-sm text-ink-muted">Loading…</div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-ink-soft border-b border-border-subtle">
              <th class="px-6 py-2 font-medium">User</th>
              <th class="px-3 py-2 font-medium">Storage</th>
              <th class="px-3 py-2 font-medium">Docs</th>
              <th class="px-3 py-2 font-medium">Status</th>
              <th class="px-6 py-2 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.user_id" class="border-b border-border-subtle last:border-0 hover:bg-surface-alt">
              <td class="px-6 py-3">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-ink truncate max-w-[16rem]">{{ u.email }}</span>
                  <Badge v-if="u.is_admin" color="pink">admin</Badge>
                  <Badge v-if="isSelf(u)" color="slate">you</Badge>
                </div>
              </td>
              <td class="px-3 py-3 text-ink-soft whitespace-nowrap">
                {{ formatBytes(u.storage_used_bytes) }} / {{ formatBytes(u.storage_quota_bytes) }}
              </td>
              <td class="px-3 py-3 text-ink-soft">{{ u.document_count }}</td>
              <td class="px-3 py-3">
                <Badge :color="u.is_active ? 'emerald' : 'rose'">{{ u.is_active ? 'active' : 'disabled' }}</Badge>
              </td>
              <td class="px-6 py-3">
                <div class="flex items-center gap-1 justify-end">
                  <button class="text-xs px-2 py-1 rounded-lg text-ink-soft hover:bg-black/5 cursor-pointer" @click="openQuota(u)" title="Set quota">
                    <HardDriveUpload class="w-4 h-4" />
                  </button>
                  <button class="text-xs px-2 py-1 rounded-lg cursor-pointer hover:bg-black/5" :class="u.is_admin ? 'text-pink' : 'text-ink-soft'" @click="toggleAdmin(u)" :disabled="isSelf(u)" title="Toggle admin">admin</button>
                  <button class="text-xs px-2 py-1 rounded-lg cursor-pointer hover:bg-black/5" :class="u.is_active ? 'text-amber' : 'text-emerald'" @click="toggleActive(u)" :disabled="isSelf(u)">{{ u.is_active ? 'disable' : 'enable' }}</button>
                  <button class="text-rose px-2 py-1 rounded-lg hover:bg-rose/5 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed" @click="deleteTarget = u" :disabled="isSelf(u)" title="Delete user">
                    <Trash2 class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- Quota modal -->
    <Modal :open="!!quotaUser" title="Set storage quota" @close="quotaUser = null">
      <p class="text-sm text-ink-soft mb-4 truncate">{{ quotaUser?.email }}</p>
      <Input v-model.number="quotaGb" type="number" label="Quota (GB)" />
      <div class="flex gap-2 mt-6">
        <Button variant="secondary" block @click="quotaUser = null">Cancel</Button>
        <Button block @click="saveQuota">Save</Button>
      </div>
    </Modal>

    <!-- Delete confirm -->
    <Modal :open="!!deleteTarget" title="Delete user?" @close="deleteTarget = null">
      <p class="text-sm text-ink-soft mb-4">
        Permanently delete <span class="font-semibold text-ink">{{ deleteTarget?.email }}</span> and all their documents, pools, tokens, and webhooks. This can't be undone.
      </p>
      <div class="flex gap-2">
        <Button variant="secondary" block @click="deleteTarget = null">Cancel</Button>
        <Button variant="danger" block @click="confirmDelete">Delete</Button>
      </div>
    </Modal>
  </div>
</template>
