<template>
  <div style="display:flex;min-height:100vh;">
    <AppSidebar />
    <div class="app-content">
      <h1 style="font-size:22px;font-weight:600;margin-bottom:20px;">New Loan Application</h1>

      <div class="card" style="max-width:800px;">
        <div class="card-header"><h2>Project Information</h2></div>
        <div class="card-body">
          <form @submit.prevent="submitForm">
            <div class="form-section"><h3>Basic Details</h3>
              <div class="form-field"><label class="required">Project Name</label>
                <input v-model="form.project_name" required maxlength="256" placeholder="Enter project name" />
              </div>
              <div class="form-row">
                <div class="form-field"><label class="required">Sector</label>
                  <select v-model="form.sector" required>
                    <option value="">Select sector...</option>
                    <option>Infrastructure</option><option>Energy</option><option>Transport</option>
                    <option>Water</option><option>Healthcare</option><option>Education</option>
                    <option>Agriculture</option><option>Environment</option><option>Urban Development</option>
                    <option>Digital Infrastructure</option>
                  </select>
                </div>
              </div>
            </div>

            <div class="form-section"><h3>Financial Details</h3>
              <div class="form-row">
                <div class="form-field"><label class="required">Amount Requested</label>
                  <input v-model.number="form.amount_requested" type="number" min="0" step="0.01" required placeholder="0.00" />
                </div>
                <div class="form-field"><label class="required">Currency</label>
                  <select v-model="form.currency" required>
                    <option value="USD">USD — US Dollar</option>
                    <option value="EUR">EUR — Euro</option>
                    <option value="CNY">CNY — Chinese Yuan</option>
                    <option value="BRL">BRL — Brazilian Real</option>
                    <option value="INR">INR — Indian Rupee</option>
                    <option value="ZAR">ZAR — South African Rand</option>
                    <option value="AED">AED — UAE Dirham</option>
                    <option value="RUB">RUB — Russian Ruble</option>
                  </select>
                </div>
              </div>
              <div class="form-row">
                <div class="form-field"><label class="required">Term (months)</label>
                  <input v-model.number="form.term_months" type="number" min="1" max="480" required placeholder="e.g. 240" />
                </div>
              </div>
            </div>

            <div class="form-section"><h3>Project Details</h3>
              <div class="form-field"><label>Project Description</label>
                <textarea v-model="form.project_description" rows="5" placeholder="Describe the project scope, objectives, and expected outcomes..."></textarea>
              </div>
              <div class="form-field"><label>Loan Purpose</label>
                <textarea v-model="form.purpose" rows="3" placeholder="How the funds will be utilized..."></textarea>
              </div>
            </div>

            <div style="border-top:1px solid #dce3ea;padding-top:20px;margin-top:20px;">
              <button type="submit" class="btn btn-primary btn-lg" :disabled="submitting">
                {{ submitting ? 'Creating...' : 'Create Application' }}
              </button>
              <router-link to="/applications" class="btn btn-outline" style="margin-left:12px;">Cancel</router-link>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const router = useRouter()
const submitting = ref(false)

const form = reactive({
  project_name: '',
  amount_requested: null,
  currency: 'USD',
  term_months: null,
  sector: '',
  project_description: '',
  purpose: '',
})

async function submitForm() {
  submitting.value = true
  try {
    const res = await api.post('/applications', form)
    router.push(`/applications/${res.data.application.id}`)
  } catch(e) {
    alert('Failed to create: ' + (e.response?.data?.error || e.message))
  } finally {
    submitting.value = false
  }
}
</script>
