<template>
  <header class="app-header">
    <router-link to="/dashboard" class="logo">
      <div class="logo-icon">IDB</div>
      <span class="logo-text">Loan Portal</span>
    </router-link>
    <div class="user-info">
      <div class="notif-wrap" @click="toggleNotif" v-click-outside="closeNotif">
        <span class="notif-bell">🔔</span>
        <span v-if="unreadCount" class="notif-badge">{{ unreadCount }}</span>
        <div v-if="showNotif" class="notif-dropdown" @click.stop>
          <div v-if="!notifications.length" class="notif-empty">No notifications</div>
          <div v-for="n in notifications" :key="n.id"
               class="notif-item"
               :class="{ unread: !n.is_read }"
               @click="openNotif(n)">
            <div class="notif-title">{{ n.title }}</div>
            <div class="notif-msg">{{ n.message }}</div>
          </div>
          <div class="notif-footer">
            <router-link to="/notifications" @click="showNotif = false">View all</router-link>
          </div>
        </div>
      </div>
      <span class="role-badge">{{ auth.role }}</span>
      <span class="text-sm" style="opacity:0.8;">{{ auth.user?.full_name }}</span>
      <button @click="handleLogout" class="btn-logout">Sign Out</button>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore, api } from '../store/auth'

const router = useRouter()
const auth = useAuthStore()

const notifications = ref([])
const showNotif = ref(false)
const unreadCount = computed(() => notifications.value.filter(n => !n.is_read).length)

async function loadNotifications() {
  try {
    const res = await api.get('/auth/notifications')
    notifications.value = res.data.notifications || []
  } catch (_) {
    notifications.value = []
  }
}

function toggleNotif() {
  showNotif.value = !showNotif.value
  if (showNotif.value) loadNotifications()
}

function closeNotif() { showNotif.value = false }

async function openNotif(n) {
  try {
    await api.post(`/auth/notifications/${n.id}/read`)
  } catch (_) { /* noop */ }
  showNotif.value = false
  if (n.related_type === 'loan_application' && n.related_id) {
    router.push(`/applications/${n.related_id}`)
  } else {
    router.push('/notifications')
  }
}

async function handleLogout() {
  try { await api.post('/auth/logout') } catch (_) { /* noop */ }
  auth.logout()
  router.push('/login')
}

// Simple v-click-outside directive shim.
const vClickOutside = {
  mounted(el, binding) {
    el._outside = (e) => { if (!el.contains(e.target)) binding.value() }
    document.addEventListener('click', el._outside)
  },
  unmounted(el) {
    document.removeEventListener('click', el._outside)
  },
}

onMounted(loadNotifications)
</script>

<style scoped>
.app-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; background: #0b3d91; color: #fff;
}
.logo { display: flex; align-items: center; gap: 10px; text-decoration: none; color: inherit; }
.logo-icon { background: #fff; color: #0b3d91; font-weight: 700; padding: 4px 8px; border-radius: 4px; }
.user-info { display: flex; align-items: center; gap: 14px; }
.role-badge { background: rgba(255,255,255,0.15); padding: 2px 8px; border-radius: 8px; font-size: 12px; }
.btn-logout { background: #d64545; color: #fff; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
.notif-wrap { position: relative; cursor: pointer; }
.notif-bell { font-size: 18px; }
.notif-badge {
  position: absolute; top: -6px; right: -8px; background: #d64545;
  color: white; border-radius: 10px; padding: 0 6px; font-size: 11px;
}
.notif-dropdown {
  position: absolute; right: 0; top: 28px; width: 320px; max-height: 400px;
  overflow-y: auto; background: #fff; color: #222; border-radius: 6px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.15); z-index: 1000;
}
.notif-item { padding: 10px 12px; border-bottom: 1px solid #eee; cursor: pointer; }
.notif-item.unread { background: #eef4ff; }
.notif-title { font-weight: 600; font-size: 13px; }
.notif-msg { font-size: 12px; color: #555; margin-top: 2px; }
.notif-empty { padding: 16px; text-align: center; color: #888; }
.notif-footer { padding: 8px; text-align: center; border-top: 1px solid #eee; }
</style>
