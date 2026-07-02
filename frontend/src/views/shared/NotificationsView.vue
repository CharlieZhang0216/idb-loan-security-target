<template>
  <div style="display:flex;min-height:100vh;">
    <AppSidebar />
    <div class="app-content">
      <h1 style="font-size:22px;font-weight:600;margin-bottom:20px;">Notifications</h1>
      <div class="card">
        <div class="card-body">
          <div v-if="!notifications.length" style="padding:40px;text-align:center;color:#888;">
            No notifications yet.
          </div>
          <div v-else>
            <div v-for="n in notifications" :key="n.id"
                 class="notif-row" :class="{ unread: !n.is_read }"
                 @click="open(n)">
              <div class="notif-title">{{ n.title }}</div>
              <div class="notif-msg">{{ n.message }}</div>
              <div class="notif-time">{{ formatTime(n.created_at) }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const notifications = ref([])
const router = useRouter()

async function load() {
  const res = await api.get('/auth/notifications', { params: { limit: 100 } })
  notifications.value = res.data.notifications || []
}

async function open(n) {
  if (!n.is_read) {
    try { await api.post(`/auth/notifications/${n.id}/read`) } catch (_) {}
  }
  if (n.related_type === 'loan_application' && n.related_id) {
    router.push(`/applications/${n.related_id}`)
  }
}

function formatTime(t) { return t ? new Date(t).toLocaleString() : '' }

onMounted(load)
</script>

<style scoped>
.notif-row { padding: 12px; border-bottom: 1px solid #eee; cursor: pointer; }
.notif-row.unread { background: #eef4ff; }
.notif-title { font-weight: 600; }
.notif-msg { color: #555; margin: 4px 0; }
.notif-time { font-size: 12px; color: #999; }
</style>
