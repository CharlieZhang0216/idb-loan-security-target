<template>
  <div style="display:flex;min-height:100vh;">
    <AppSidebar />
    <div class="app-content">
      <h1 style="font-size:22px;font-weight:600;margin-bottom:4px;">Risk Assessment</h1>
      <p class="text-muted text-sm mb-4">Applications awaiting risk evaluation</p>

      <div class="card" v-if="riskApps.length">
        <table class="data-table">
          <thead><tr><th>App No.</th><th>Project</th><th>Borrower</th><th>Amount</th><th>Term</th><th>Officer</th><th>Action</th></tr></thead>
          <tbody>
            <tr v-for="app in riskApps" :key="app.id">
              <td><router-link :to="`/applications/${app.id}`">{{ app.app_no }}</router-link></td>
              <td>{{ app.project_name }}</td>
              <td class="text-sm">{{ app.borrower?.country || '-' }}</td>
              <td><span class="amount">{{ formatAmount(app.amount_requested, app.currency) }}</span></td>
              <td class="text-sm">{{ app.term_months }} mo</td>
              <td class="text-sm">{{ app.officer_id || '-' }}</td>
              <td>
                <router-link :to="`/applications/${app.id}`" class="btn btn-primary btn-sm">Assess</router-link>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="card"><div class="empty-state"><h3>No applications pending</h3><p>No applications currently require risk assessment.</p></div></div>

      <!-- Interest Calculator -->
      <div class="card mt-4" style="max-width:600px;">
        <div class="card-header"><h2>Interest Calculator</h2></div>
        <div class="card-body">
          <div class="form-row">
            <div class="form-field"><label>Principal Amount</label><input v-model.number="calc.amount" type="number" min="0" /></div>
            <div class="form-field"><label>Rate (%)</label><input v-model.number="calc.rate" type="number" step="0.01" min="0" max="50" /></div>
          </div>
          <div class="form-row">
            <div class="form-field"><label>Term (months)</label><input v-model.number="calc.months" type="number" min="1" max="480" /></div>
          </div>
          <div v-if="calcResult" style="background:#f8f9fc;padding:16px;border-radius:6px;margin-top:12px;">
            <div class="flex-between"><span class="text-sm text-muted">Annual Interest:</span><span class="amount">${{ calcResult.annual_interest }}</span></div>
            <div class="flex-between"><span class="text-sm text-muted">Total Interest:</span><span class="amount">${{ calcResult.total_interest }}</span></div>
            <div class="flex-between" style="margin-top:8px;font-weight:600;"><span>Total Repayment:</span><span class="amount">${{ calcResult.total_repayment }}</span></div>
          </div>
          <button @click="doCalculate" class="btn btn-outline mt-4" style="margin-top:12px;">Calculate</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const riskApps = ref([])
const calc = ref({ amount: 1000000, rate: 2.0, months: 120 })
const calcResult = ref(null)

onMounted(async () => {
  const res = await api.get('/applications')
  riskApps.value = (res.data.applications || []).filter(a => a.status === 'risk_assessment')
  // Enrich
  for (const app of riskApps.value) {
    try {
      const d = await api.get(`/applications/${app.id}`)
      app.borrower = d.data.application?.borrower
    } catch(e) {}
  }
})

async function doCalculate() {
  try {
    const res = await api.post('/applications/1/calculate-interest', calc.value)
    calcResult.value = res.data
  } catch(e) {}
}

function formatAmount(v, c) { return v ? '$' + new Intl.NumberFormat('en-US').format(Number(v)) : '-' }
</script>
