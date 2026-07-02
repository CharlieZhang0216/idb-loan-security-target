<template>
  <div style="display:flex;min-height:100vh;">
    <AppSidebar />
    <div class="app-content">
      <h1 style="font-size:22px;font-weight:600;margin-bottom:20px;">Admin Dashboard</h1>

      <div class="stats-row">
        <div class="stat-card"><div class="stat-value">{{ adminStats.users_total || 0 }}</div><div class="stat-label">Total Users</div></div>
        <div class="stat-card"><div class="stat-value">{{ adminStats.applications_total || 0 }}</div><div class="stat-label">Total Applications</div></div>
        <div class="stat-card"><div class="stat-value">{{ adminStats.applications_pending || 0 }}</div><div class="stat-label">Pending</div></div>
        <div class="stat-card"><div class="stat-value">{{ adminStats.documents_total || 0 }}</div><div class="stat-label">Documents</div></div>
      </div>

      <div class="card">
        <div class="card-header"><h2>System Configuration</h2></div>
        <div class="card-body">
          <div v-if="configKeys.length">
            <div v-for="item in configKeys" :key="item.key" style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #f0f0f0;">
              <div>
                <span style="font-family:monospace;font-size:13px;font-weight:500;">{{ item.key }}</span>
                <span class="text-sm text-muted" style="margin-left:12px;">{{ item.description || '' }}</span>
              </div>
              <span class="text-sm" style="font-family:monospace;background:#f8f9fc;padding:3px 8px;border-radius:4px;">{{ item.value }}</span>
            </div>
          </div>
          <div v-else class="text-muted text-sm">No configuration found.</div>
        </div>
      </div>

      <div class="card mt-4">
        <div class="card-header">
          <h2>Recent Audit Logs</h2>
          <router-link to="/admin" class="btn btn-outline btn-sm">Refresh</router-link>
        </div>
        <div class="card-body" v-if="auditLogs.length">
          <table class="data-table">
            <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Resource</th><th>IP</th></tr></thead>
            <tbody>
              <tr v-for="log in auditLogs" :key="log.id">
                <td class="text-sm">{{ formatDate(log.created_at) }}</td>
                <td class="text-sm">{{ log.username || log.user_id }}</td>
                <td class="text-sm">{{ log.action }}</td>
                <td class="text-sm text-muted">{{ log.resource_type }}/{{ log.resource_id }}</td>
                <td class="text-sm text-muted">{{ log.ip_address }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="card-body"><div class="empty-state"><p>No audit logs found.</p></div></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const adminStats = ref({})
const configKeys = ref([])
const auditLogs = ref([])

onMounted(async () => {
  try {
    const [statsRes, configRes, auditRes] = await Promise.all([
      api.get('/admin/stats'),
      api.get('/admin/config'),
      api.get('/admin/audit-logs?per_page=20')
    ])
    adminStats.value = statsRes.data
    const cfg = configRes.data.config || {}
    configKeys.value = Object.entries(cfg).map(([k, v]) => ({
      key: k, value: v, description: getConfigDesc(k)
    }))
    auditLogs.value = auditRes.data.logs || []
  } catch(e) { console.error(e) }
})

function getConfigDesc(key) {
  const desc = {
    min_loan_amount: 'Min loan amount (USD)',
    max_loan_amount: 'Max loan amount (USD)',
    default_interest_spread: 'Default spread over ref rate',
    upload_max_size_mb: 'Max upload size',
    sso_enabled: 'SSO auth enabled',
    enable_interest_rate_override: 'Rate override allowed',
  }
  return desc[key] || ''
}

function formatDate(d) { return d ? new Date(d).toLocaleString() : '' }
</script>
