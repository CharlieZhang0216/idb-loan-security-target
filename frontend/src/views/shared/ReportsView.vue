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
          <div class="flex gap-2 flex-wrap" style="margin-bottom:12px;">
            <button @click="exportAll" class="btn btn-primary" :disabled="downloading">
              {{ downloading ? 'Preparing...' : 'Export PDF (All)' }}
            </button>
            <button @click="exportApp" class="btn btn-outline" :disabled="downloading">Export PDF (By App ID)</button>
          </div>

          <details style="margin-top:8px;">
            <summary class="text-sm text-muted" style="cursor:pointer;">Advanced (Custom Template)</summary>
            <div style="margin-top:10px;">
              <div class="form-field">
                <label class="text-sm">Template snippet (Jinja)</label>
                <textarea v-model="customTemplate" rows="3" placeholder="e.g. Total: {{ total_applications }}"></textarea>
              </div>
              <button @click="exportCustom" class="btn btn-outline btn-sm" :disabled="downloading || !customTemplate">
                Render &amp; Download
              </button>
            </div>
          </details>

          <p v-if="downloadError" class="text-sm" style="color:#c92a2a;margin-top:10px;">{{ downloadError }}</p>
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
const downloading = ref(false)
const downloadError = ref('')
const customTemplate = ref('')

onMounted(async () => {
  try {
    const res = await api.get('/reports/summary')
    reportData.value = res.data
  } catch(e) {
    downloadError.value = e.response?.data?.error || e.message
  }
})

async function downloadPdf(params, filename) {
  downloading.value = true
  downloadError.value = ''
  try {
    const res = await api.get('/reports/export', { params, responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch(e) {
    downloadError.value = e.response?.data?.error || e.message || 'Download failed'
  } finally {
    downloading.value = false
  }
}

function exportAll() {
  return downloadPdf({}, 'portfolio-report.pdf')
}

function exportApp() {
  const id = prompt('Enter application ID:')
  if (!id) return
  return downloadPdf({ application_id: id }, `application-${id}.pdf`)
}

function exportCustom() {
  return downloadPdf({ template: customTemplate.value }, 'custom-report.pdf')
}

function formatStatus(s) { return s ? s.replace(/_/g, ' ') : s }
</script>
