<template>
  <div class="app-body">
    <AppSidebar />
    <div class="app-content">
      <h1 style="font-size:22px;font-weight:600;margin-bottom:4px;">Dashboard</h1>
      <p class="text-muted text-sm mb-4">Welcome back, {{ auth.user?.full_name }}</p>

      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-value">{{ stats.applications?.total || 0 }}</div>
          <div class="stat-label">Total Applications</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.applications?.pending || 0 }}</div>
          <div class="stat-label">Pending Review</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.applications?.approved || 0 }}</div>
          <div class="stat-label">Approved</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="font-size:18px;padding-top:6px;">${{ formatAmount(stats.applications?.totalAmount) }}</div>
          <div class="stat-label">Total Portfolio Value</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h2>Recent Applications</h2>
          <router-link to="/applications" class="btn btn-outline btn-sm">View All</router-link>
        </div>
        <div class="card-body">
          <table class="data-table" v-if="recentApps.length">
            <thead>
              <tr>
                <th>App No.</th>
                <th>Project</th>
                <th>Sector</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="app in recentApps" :key="app.id">
                <td><router-link :to="`/applications/${app.id}`">{{ app.app_no }}</router-link></td>
                <td>{{ app.project_name }}</td>
                <td class="text-sm">{{ app.sector }}</td>
                <td><span class="amount">{{ formatCurrency(app.amount_requested, app.currency) }}</span></td>
                <td><span :class="`status-badge status-${app.status}`">{{ formatStatus(app.status) }}</span></td>
                <td class="text-sm text-muted">{{ formatDate(app.updated_at) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty-state">
            <p>No applications found.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore, api } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const auth = useAuthStore()
const stats = ref({ applications: {} })
const recentApps = ref([])

onMounted(async () => {
  try {
    const [summaryRes, appsRes] = await Promise.all([
      api.get('/reports/summary'),
      api.get('/applications')
    ])
    const summary = summaryRes.data
    stats.value = {
      applications: {
        total: summary.total_applications,
        pending: (summary.by_status?.submitted || 0) + (summary.by_status?.under_review || 0),
        approved: summary.by_status?.approved || 0,
        totalAmount: 0,
      }
    }
    recentApps.value = (appsRes.data.applications || []).slice(0, 10)
  } catch (e) {
    console.error('Failed to load dashboard', e)
  }
})

function formatStatus(s) {
  return s ? s.replace(/_/g, ' ') : s
}

function formatDate(d) {
  return d ? new Date(d).toLocaleDateString('en-US', { year:'numeric', month:'short', day:'numeric' }) : ''
}

function formatCurrency(val, cur) {
  if (!val) return '-'
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(val))
}

function formatAmount(val) {
  if (!val) return '0'
  const n = Number(val)
  if (n >= 1e9) return (n/1e9).toFixed(1) + 'B'
  if (n >= 1e6) return (n/1e6).toFixed(0) + 'M'
  return n.toLocaleString()
}
</script>
