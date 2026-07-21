<script setup>
import { useRoute } from 'vue-router'
import AppShell from './components/AppShell.vue'
import ToastHost from './components/ui/Toast.vue'

const route = useRoute()
</script>

<template>
  <AppShell v-if="!route.meta.public">
    <router-view />
  </AppShell>
  <router-view v-else />
  <ToastHost />
</template>
