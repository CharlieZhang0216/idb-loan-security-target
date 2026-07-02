<template>
  <div style="display:flex;min-height:100vh;">
    <AppSidebar />
    <div class="app-content">
      <div v-if="loading" style="text-align:center;padding:60px;">Loading...</div>

      <template v-else-if="app">
        <div class="flex-between mb-4">
          <div>
            <h1 style="font-size:22px;font-weight:600;">Edit Application</h1>
            <p class="text-muted text-sm">{{ app.app_no }} · <span :class="`status-badge status-${app.status}`">{{ formatStatus(app.status) }}</span></p>
          </div>
          <router-link :to="`/applications/${app.id}`" class="btn btn-outline">Back to Detail</router-link>
        </div>

        <!-- Draft: full edit -->
        <div class="card" v-if="mode === 'draft'" style="max-width:800px;">
          <div class="card-header"><h2>Project Information</h2></div>
          <div class="card-body">
            <form @submit.prevent="submitForm">
              <div class="form-section"><h3>Basic Details</h3>
                <div class="form-field"><label class="required">Project Name</label>
                  <input v-model="form.project_name" required maxlength="256" />
                </div>
                <div class="form-field"><label>Sector</label>
                  <select v-model="form.sector">
                    <option value="">Select sector...</option>
                    <option>Infrastructure</option><option>Energy</option><option>Transport</option>
                    <option>Water</option><option>Healthcare</option><option>Education</option>
                    <option>Agriculture</option><option>Environment</option><option>Urban Development</option>
                    <option>Digital Infrastructure</option>
                  </select>
                </div>
              </div>

              <div class="form-section"><h3>Financial Details</h3>
                <div class="form-row">
                  <div class="form-field"><label class="required">Amount Requested</label>
                    <input v-model.number="form.amount_requested" type="number" step="0.01" required />
                  </div>
                  <div class="form-field"><label class="required">Currency</label>
                    <select v-model="form.currency" required>
                      <option value="USD">USD</option><option value="EUR">EUR</option>
                      <option value="CNY">CNY</option><option value="BRL">BRL</option>
                      <option value="INR">INR</option><option value="ZAR">ZAR</option>
                      <option value="AED">AED</option><option value="RUB">RUB</option>
                    </select>
                  </div>
                </div>
                <div class="form-row">
                  <div class="form-field"><label class="required">Term (months)</label>
                    <input v-model.number="form.term_months" type="number" min="1" max="480" required />
                  </div>
                </div>
              </div>

              <div class="form-section"><h3>Project Details</h3>
                <div class="form-field"><label>Project Description</label>
                  <textarea v-model="form.project_description" rows="5"></textarea>
                </div>
                <div class="form-field"><label>Loan Purpose</label>
                  <textarea v-model="form.purpose" rows="3"></textarea>
                </div>
              </div>

              <div style="border-top:1px solid #dce3ea;padding-top:20px;margin-top:20px;">
                <button type="submit" class="btn btn-primary btn-lg" :disabled="saving">
                  {{ saving ? 'Saving...' : 'Save Changes' }}
                </button>
                <router-link :to="`/applications/${app.id}`" class="btn btn-outline" style="margin-left:12px;">Cancel</router-link>
              </div>
            </form>
          </div>
        </div>

        <!-- Approved / disbursed borrower: currency-only edit (VULN-31 UI companion) -->
        <div class="card" v-else-if="mode === 'currency_only'" style="max-width:640px;">
          <div class="card-header"><h2>Amend Currency</h2></div>
          <div class="card-body">
            <div class="alert alert-warning" style="background:#fff8e1;border:1px solid #ffca28;padding:10px 14px;border-radius:6px;font-size:13px;margin-bottom:16px;">
              This application is already <strong>{{ formatStatus(app.status) }}</strong>.
              Only the settlement currency may be amended here — approved terms remain locked.
            </div>
            <form @submit.prevent="submitForm">
              <div class="form-field"><label class="required">Currency</label>
                <select v-model="form.currency" required>
                  <option value="USD">USD</option><option value="EUR">EUR</option>
                  <option value="CNY">CNY</option><option value="BRL">BRL</option>
                  <option value="INR">INR</option><option value="ZAR">ZAR</option>
                  <option value="AED">AED</option><option value="RUB">RUB</option>
                </select>
              </div>
              <div style="border-top:1px solid #dce3ea;padding-top:16px;margin-top:16px;">
                <button type="submit" class="btn btn-primary" :disabled="saving">
                  {{ saving ? 'Saving...' : 'Amend Currency' }}
                </button>
                <router-link :to="`/applications/${app.id}`" class="btn btn-outline" style="margin-left:12px;">Cancel</router-link>
              </div>
            </form>
          </div>
        </div>

        <div class="card" v-else>
          <div class="card-body">
            <div class="empty-state">
              <p>This application cannot be edited in its current state.</p>
              <router-link :to="`/applications/${app.id}`" class="btn btn-primary btn-sm mt-2">Back to Detail</router-link>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore, api } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const app = ref(null)
const loading = ref(true)
const saving = ref(false)

const form = reactive({
  project_name: '',
  project_description: '',
  sector: '',
  amount_requested: null,
  currency: 'USD',
  term_months: null,
  purpose: '',
})

const mode = computed(() => {
  if (!app.value) return null
  if (app.value.status === 'draft'
      && (auth.isBorrower && app.value.borrower_id === auth.user?.id || auth.isAdmin)) {
    return 'draft'
  }
  if (['approved', 'disbursed'].includes(app.value.status)
      && auth.isBorrower && app.value.borrower_id === auth.user?.id) {
    return 'currency_only'
  }
  return null
})

onMounted(async () => {
  try {
    const res = await api.get(`/applications/${route.params.id}`)
    app.value = res.data.application
    Object.assign(form, {
      project_name: app.value.project_name || '',
      project_description: app.value.project_description || '',
      sector: app.value.sector || '',
      amount_requested: app.value.amount_requested,
      currency: app.value.currency || 'USD',
      term_months: app.value.term_months,
      purpose: app.value.purpose || '',
    })
  } catch(e) { console.error(e) }
  finally { loading.value = false }
})

async function submitForm() {
  saving.value = true
  try {
    let payload
    if (mode.value === 'draft') {
      payload = {
        project_name: form.project_name,
        project_description: form.project_description,
        sector: form.sector,
        amount_requested: form.amount_requested,
        currency: form.currency,
        term_months: form.term_months,
        purpose: form.purpose,
      }
    } else if (mode.value === 'currency_only') {
      payload = { currency: form.currency }
    } else {
      return
    }
    await api.put(`/applications/${route.params.id}`, payload)
    router.push(`/applications/${route.params.id}`)
  } catch(e) {
    alert('Failed to save: ' + (e.response?.data?.error || e.message))
  } finally {
    saving.value = false
  }
}

function formatStatus(s) { return s ? s.replace(/_/g, ' ') : s }
</script>
