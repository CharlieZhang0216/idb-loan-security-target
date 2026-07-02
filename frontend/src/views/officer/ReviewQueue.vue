<template>
  <div style="display:flex;min-height:100vh;">
    <AppSidebar />
    <div class="app-content">
      <div class="flex-between mb-4">
        <h1 style="font-size:22px;font-weight:600;">Review Queue</h1>
        <span class="text-muted text-sm">{{ reviewableApps.length }} application(s) awaiting review</span>
      </div>

      <div class="card" v-if="reviewableApps.length">
        <table class="data-table">
          <thead><tr><th>App No.</th><th>Project</th><th>Borrower</th><th>Amount</th><th>Submitted</th><th>Status</th><th>Action</th></tr></thead>
          <tbody>
            <tr v-for="app in reviewableApps" :key="app.id">
              <td><router-link :to="`/applications/${app.id}`">{{ app.app_no }}</router-link></td>
              <td>{{ app.project_name }}</td>
              <td class="text-sm">{{ app.borrower_name || '-' }}</td>
              <td><span class="amount">{{ formatAmount(app.amount_requested, app.currency) }}</span></td>
              <td class="text-sm text-muted">{{ formatDate(app.submitted_at) }}</td>
              <td><span :class="`status-badge status-${app.status}`">{{ formatStatus(app.status) }}</span></td>
              <td>
                <router-link :to="`/applications/${app.id}`" class="btn btn-primary btn-sm">Review</router-link>
                <button @click="openSupplementDialog(app)" class="btn btn-outline btn-sm" style="margin-left:6px;">Request Info</button>
                <button @click="quickReject(app)" class="btn btn-danger btn-sm" style="margin-left:6px;">Reject</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="card"><div class="empty-state"><h3>Queue is empty</h3><p>No applications currently awaiting review.</p></div></div>

      <!-- Supplement Dialog -->
      <div v-if="supplementDialog" style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.4);z-index:1000;display:flex;align-items:center;justify-content:center;">
        <div style="background:white;border-radius:8px;padding:32px;width:500px;max-width:90vw;">
          <h2 style="font-size:18px;margin-bottom:20px;">Request Complementary Information</h2>
          <p class="text-sm text-muted mb-4">Application: {{ supplementTarget?.app_no }}</p>
          <div class="form-field"><label class="required">Description of required information</label>
            <textarea v-model="supplementDesc" rows="4" placeholder="Describe what additional information is needed..."></textarea>
          </div>
          <div class="flex gap-2" style="justify-content:flex-end;margin-top:20px;">
            <button class="btn btn-outline" @click="supplementDialog = false">Cancel</button>
            <button class="btn btn-primary" @click="submitSupplement" :disabled="!supplementDesc">Submit Request</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api, useAuthStore } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const auth = useAuthStore()
const reviewableApps = ref([])
const supplementDialog = ref(false)
const supplementTarget = ref(null)
const supplementDesc = ref('')

onMounted(async () => {
  const res = await api.get('/applications', { params: { per_page: 200 } })
  const apps = res.data.applications || []
  reviewableApps.value = apps
    .filter(a => ['submitted', 'under_review', 'pending_supplement'].includes(a.status))
    .map(a => ({ ...a, borrower_name: a.borrower?.full_name }))
})

function openSupplementDialog(app) {
  supplementTarget.value = app
  supplementDesc.value = ''
  supplementDialog.value = true
}

async function submitSupplement() {
  await api.post(`/applications/${supplementTarget.value.id}/supplements`, {
    description: supplementDesc.value
  })
  supplementDialog.value = false
  window.location.reload()
}

async function quickReject(app) {
  const reason = prompt(`Reject application ${app.app_no}? Enter reason (optional):`, 'Does not meet criteria')
  if (reason === null) return
  try {
    await api.post(`/applications/${app.id}/reject`, { reason })
    window.location.reload()
  } catch(e) {
    alert('Reject failed: ' + (e.response?.data?.error || e.message))
  }
}

function formatStatus(s) { return s ? s.replace(/_/g, ' ') : s }
function formatDate(d) { return d ? new Date(d).toLocaleDateString() : '' }
function formatAmount(v, c) { return v ? '$' + new Intl.NumberFormat('en-US').format(Number(v)) : '-' }
</script>
