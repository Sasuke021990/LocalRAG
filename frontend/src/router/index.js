import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

import LoginPage from '../pages/LoginPage.vue'
import SignupPage from '../pages/SignupPage.vue'
import ResetPasswordPage from '../pages/ResetPasswordPage.vue'
import DashboardPage from '../pages/DashboardPage.vue'
import ChatPage from '../pages/ChatPage.vue'
import KnowledgeBasePage from '../pages/KnowledgeBasePage.vue'
import BillingPage from '../pages/BillingPage.vue'
import SettingsPage from '../pages/SettingsPage.vue'
import AdminPage from '../pages/AdminPage.vue'

const routes = [
  { path: '/login', name: 'login', component: LoginPage, meta: { public: true } },
  { path: '/signup', name: 'signup', component: SignupPage, meta: { public: true } },
  { path: '/reset-password', name: 'reset-password', component: ResetPasswordPage, meta: { public: true } },
  { path: '/', name: 'dashboard', component: DashboardPage },
  { path: '/chat', name: 'chat', component: ChatPage },
  { path: '/knowledge-base', name: 'knowledge-base', component: KnowledgeBasePage },
  { path: '/billing', name: 'billing', component: BillingPage },
  { path: '/settings', name: 'settings', component: SettingsPage },
  { path: '/admin', name: 'admin', component: AdminPage, meta: { admin: true } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.checked) await auth.fetchCurrentUser()
  if (!to.meta.public && !auth.isAuthenticated) return { name: 'login' }
  if (to.meta.public && auth.isAuthenticated) return { name: 'dashboard' }
  if (to.meta.admin && !auth.user?.is_admin) return { name: 'dashboard' }
})

export default router
