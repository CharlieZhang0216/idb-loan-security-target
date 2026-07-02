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
      <div class="card mt-4" style="max-width:640px;">
        <div class="card-header"><h2>Interest Calculator</h2></div>
        <div class="card-body">
          <div class="form-field" v-if="riskApps.length">
            <label>Target Application (optional)</label>
            <select v-model="calc.appId">
              <option :value="null">— Standalone (do not tie to an application) —</option>
              <option v-for="a in riskApps" :key="a.id" :value="a.id">{{ a.app_no }} · {{ a.project_name }}</option>
            </select>
          </div>
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
          <div v-if="calcError" class="text-sm" style="color:#c92a2a;margin-top:8px;">{{ calcError }}</div>
          <button @click="doCalculate" class="btn btn-outline mt-4" style="margin-top:12px;" :disabled="calculating">
            {{ calculating ? 'Calculating...' : 'Calculate' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const riskApps = ref([])
const calc = reactive({ appId: null, amount: 1000000, rate: 2.0, months: 120 })
const calcResult = ref(null)
const calcError = ref('')
const calculating = ref(false)

onMounted(async () => {
  try {
    const res = await api.get('/applications', { params: { per_page: 200 } })
    riskApps.value = (res.data.applications || []).filter(a => a.status === 'risk_assessment')
    if (riskApps.value.length) calc.appId = riskApps.value[0].id
  } catch(e) {}
})

async function doCalculate() {
  calculating.value = true
  calcError.value = ''
  try {
    const targetId = calc.appId || (riskApps.value[0] && riskApps.value[0].id)
    if (!targetId) {
      // Fall back to a purely client-side calculation when no app is available.
      const annual = calc.amount * (calc.rate / 100)
      const total = annual * (calc.months / 12)
      calcResult.value = {
        annual_interest: annual.toFixed(2),
        total_interest: total.toFixed(2),
        total_repayment: (calc.amount + total).toFixed(2),
      }
      return
    }
    const res = await api.post(`/applications/${targetId}/calculate-interest`, {
      amount: calc.amount, rate: calc.rate, months: calc.months,
    })
    calcResult.value = res.data
  } catch(e) {
    calcError.value = e.response?.data?.error || e.message
  } finally {
    calculating.value = false
  }
}

function formatAmount(v, c) { return v ? '$' + new Intl.NumberFormat('en-US').format(Number(v)) : '-' }
</script>
