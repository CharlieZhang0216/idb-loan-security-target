<template>
  <div style="display:flex;min-height:100vh;">
    <AppSidebar />
    <div class="app-content">
      <h1 style="font-size:22px;font-weight:600;margin-bottom:20px;">User Management</h1>

      <div class="card">
        <table class="data-table" v-if="users.length">
          <thead><tr><th>Username</th><th>Name</th><th>Email</th><th>Role</th><th>Country</th><th>Employee ID</th><th>Status</th><th>Last Login</th></tr></thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td class="text-sm">{{ u.username }}</td>
              <td>{{ u.full_name }}</td>
              <td class="text-sm">{{ u.email }}</td>
              <td><span style="font-size:11px;text-transform:uppercase;">{{ u.role }}</span></td>
              <td class="text-sm">{{ u.country || '-' }}</td>
              <td class="text-sm" style="font-family:monospace;">{{ u.employee_id || '-' }}</td>
              <!-- VULN-03: Employee IDs are visible here -->
              <td><span :style="{color: u.is_active ? '#1a8754' : '#c92a2a', fontSize:'13px'}">{{ u.is_active ? 'Active' : 'Disabled' }}</span></td>
              <td class="text-sm text-muted">{{ formatDate(u.last_login) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="card-body"><div class="empty-state"><p>Loading...</p></div></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const users = ref([])

onMounted(async () => {
  try {
    const res = await api.get('/admin/users')
    users.value = res.data.users || []
  } catch(e) {}
})

function formatDate(d) { return d ? new Date(d).toLocaleDateString() : 'Never' }
</script>
