<template>
  <div style="display:flex;min-height:100vh;">
    <AppSidebar />
    <div class="app-content">
      <div class="card" v-if="loading">
        <div class="card-body" style="text-align:center;padding:60px;">Loading applications...</div>
      </div>
      <template v-else>
        <div class="flex-between mb-4">
          <div>
            <h1 style="font-size:22px;font-weight:600;margin-bottom:2px;">Loan Applications</h1>
            <p class="text-muted text-sm">{{ applications.length }} applications found</p>
          </div>
          <router-link v-if="auth.isBorrower || auth.isAdmin" to="/applications/create" class="btn btn-primary">
            + New Application
          </router-link>
        </div>

        <div class="card" style="margin-bottom:12px;">
          <div class="card-body" style="padding:12px 20px;">
            <div class="flex gap-2 flex-wrap">
              <span class="text-sm text-muted" style="padding-top:4px;">Filter:</span>
              <button @click="filterStatus = ''" :class="['btn btn-sm', filterStatus ? 'btn-outline' : 'btn-primary']">All</button>
              <button v-for="s in statuses" :key="s" @click="filterStatus = s" :class="['btn btn-sm', filterStatus === s ? 'btn-primary' : 'btn-outline']">{{ formatStatus(s) }}</button>
            </div>
          </div>
        </div>

        <div class="card" v-if="filteredApps.length">
          <table class="data-table">
            <thead>
              <tr>
                <th>App No.</th>
                <th>Project</th>
                <th>Borrower</th>
                <th>Sector</th>
                <th>Amount</th>
                <th>Term</th>
                <th>Status</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="app in filteredApps" :key="app.id">
                <td><router-link :to="`/applications/${app.id}`">{{ app.app_no }}</router-link></td>
                <td style="max-width:220px;">{{ app.project_name }}</td>
                <td class="text-sm">{{ app.borrower?.country || '-' }}</td>
                <td class="text-sm">{{ app.sector || '-' }}</td>
                <td><span class="amount">{{ formatAmount(app.amount_requested, app.currency) }}</span></td>
                <td class="text-sm">{{ app.term_months }} mo</td>
                <td><span :class="`status-badge status-${app.status}`">{{ formatStatus(app.status) }}</span></td>
                <td class="text-sm text-muted">{{ formatDate(app.updated_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="card">
          <div class="empty-state"><p>No applications match the selected filter.</p></div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore, api } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const auth = useAuthStore()
const applications = ref([])
const loading = ref(true)
const filterStatus = ref('')

const statuses = ['draft','submitted','under_review','pending_supplement','risk_assessment','approved','rejected','disbursed']

const filteredApps = computed(() =>
  filterStatus.value ? applications.value.filter(a => a.status === filterStatus.value) : applications.value
)

onMounted(async () => {
  try {
    // Backend now returns { applications: [...], total, page, per_page } with
    // borrower already embedded (batch-loaded server-side) — no more N+1.
    const res = await api.get('/applications', { params: { per_page: 200 } })
    applications.value = res.data.applications || []
  } catch(e) {} finally { loading.value = false }
})

function formatStatus(s) { return s ? s.replace(/_/g, ' ') : s }
function formatDate(d) { return d ? new Date(d).toLocaleDateString() : '' }
function formatAmount(v, c) { return v ? new Intl.NumberFormat('en-US',{minimumFractionDigits:0}).format(Number(v)) + ' ' + (c||'') : '-' }
</script>
