<template>
  <div style="display:flex;min-height:100vh;">
    <AppSidebar />
    <div class="app-content">
      <h1 style="font-size:22px;font-weight:600;margin-bottom:20px;">Report Export</h1>

      <div class="card" v-if="reportData">
        <div class="card-header"><h2>Portfolio Summary</h2></div>
        <div class="card-body">
          <div class="stats-row">
            <div class="stat-card"><div class="stat-value">{{ reportData.total_applications }}</div><div class="stat-label">Total Applications</div></div>
          </div>
          <table class="data-table mt-4" v-if="reportData.by_status">
            <thead><tr><th>Status</th><th>Count</th></tr></thead>
            <tbody>
              <tr v-for="(count, status) in reportData.by_status" :key="status">
                <td><span :class="`status-badge status-${status}`">{{ formatStatus(status) }}</span></td>
                <td>{{ count }}</td>
              </tr>
            </tbody>
          </table>
          <h3 class="mt-4 mb-4" style="font-size:15px;">By Sector</h3>
          <table class="data-table" v-if="reportData.by_sector?.length">
            <thead><tr><th>Sector</th><th>Applications</th></tr></thead>
            <tbody><tr v-for="s in reportData.by_sector" :key="s.sector"><td>{{ s.sector }}</td><td>{{ s.count }}</td></tr></tbody>
          </table>
        </div>
      </div>

      <div class="card mt-4">
        <div class="card-header"><h2>Export Options</h2></div>
        <div class="card-body">
          <div class="flex gap-2 flex-wrap">
            <a href="/api/reports/export" class="btn btn-primary">Export PDF (All)</a>
            <button @click="exportApp" class="btn btn-outline">Export PDF (By App ID)</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const reportData = ref(null)

onMounted(async () => {
  const res = await api.get('/reports/summary')
  reportData.value = res.data
})

function exportApp() {
  const id = prompt('Enter application ID:')
  if (id) window.open(`/api/reports/export?application_id=${id}`)
}

function formatStatus(s) { return s ? s.replace(/_/g, ' ') : s }
</script>
