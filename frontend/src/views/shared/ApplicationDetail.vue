<template>
  <div style="display:flex;min-height:100vh;">
    <AppSidebar />
    <div class="app-content">
      <div v-if="loading" style="text-align:center;padding:60px;">Loading...</div>

      <template v-else-if="app">
        <div class="flex-between mb-4">
          <div>
            <h1 style="font-size:22px;font-weight:600;">{{ app.project_name }}</h1>
            <p class="text-muted">{{ app.app_no }} · <span :class="`status-badge status-${app.status}`">{{ formatStatus(app.status) }}</span></p>
          </div>
          <div class="flex gap-2" v-if="canEdit">
            <button v-if="app.status === 'draft'" class="btn btn-primary" @click="submitApp">Submit for Review</button>
            <router-link :to="`/applications/${app.id}/edit`" class="btn btn-outline">Edit</router-link>
          </div>
          <div class="flex gap-2" v-if="auth.isOfficer && ['submitted','under_review','pending_supplement'].includes(app.status)">
            <button class="btn btn-success" @click="moveToReview">Start Review</button>
            <button class="btn btn-outline" @click="showRejectPanel = true">Reject</button>
          </div>
          <div class="flex gap-2" v-if="auth.isRisk && app.status === 'risk_assessment'">
            <button class="btn btn-success" @click="showRiskPanel = true">Risk Assessment</button>
          </div>
        </div>

        <div class="detail-grid mb-4">
          <div class="card"><div class="card-body">
            <h3 style="font-size:15px;font-weight:600;margin-bottom:16px;">Basic Information</h3>
            <div class="detail-item"><div class="detail-label">Application No.</div><div class="detail-value">{{ app.app_no }}</div></div>
            <div class="detail-item"><div class="detail-label">Project Name</div><div class="detail-value">{{ app.project_name }}</div></div>
            <div class="detail-item"><div class="detail-label">Sector</div><div class="detail-value">{{ app.sector || 'Not specified' }}</div></div>
            <div class="detail-item"><div class="detail-label">Borrower</div><div class="detail-value">{{ app.borrower?.full_name }} ({{ app.borrower?.country }})</div></div>
            <div class="detail-item"><div class="detail-label">Created</div><div class="detail-value text-sm">{{ formatDate(app.created_at) }}</div></div>
          </div></div>
          <div class="card"><div class="card-body">
            <h3 style="font-size:15px;font-weight:600;margin-bottom:16px;">Financial Details</h3>
            <div class="detail-item"><div class="detail-label">Amount Requested</div><div class="detail-value amount" style="font-size:20px;">
              {{ formatCurrency(app.amount_requested, app.currency) }}
            </div></div>
            <div class="detail-item"><div class="detail-label">Currency</div><div class="detail-value">{{ app.currency }}</div></div>
            <div class="detail-item"><div class="detail-label">Term</div><div class="detail-value">{{ app.term_months }} months</div></div>
            <div class="detail-item"><div class="detail-label">Interest Rate</div><div class="detail-value">{{ app.interest_rate ? app.interest_rate + '%' : 'TBD' }}</div></div>
            <div class="detail-item">
              <div class="detail-label">Interest Preview</div>
              <button class="btn btn-outline btn-sm" @click="calcInterest">Calculate</button>
              <div v-if="calcResult" class="text-sm mt-2">
                Total interest: {{ formatCurrency(calcResult.total_interest, app.currency) }} ·
                Repayment: {{ formatCurrency(calcResult.total_repayment, app.currency) }}
              </div>
            </div>
          </div></div>
        </div>

        <div class="card mb-4" v-if="app.project_description">
          <div class="card-header"><h2>Project Description</h2></div>
          <div class="card-body"><p style="font-size:14px;line-height:1.7;white-space:pre-wrap;">{{ app.project_description }}</p></div>
        </div>

        <div class="card mb-4">
          <div class="card-header"><h2>Application Timeline</h2></div>
          <div class="card-body">
            <div class="timeline">
              <div class="timeline-item" :class="{ active: app.created_at }">
                <div class="timeline-time">{{ formatDate(app.created_at) }}</div>
                <div class="timeline-title">Application Created</div>
              </div>
              <div class="timeline-item" :class="{ active: app.submitted_at }" v-if="app.submitted_at">
                <div class="timeline-time">{{ formatDate(app.submitted_at) }}</div>
                <div class="timeline-title">Submitted for Review</div>
              </div>
              <div class="timeline-item" :class="{ active: app.reviewed_at }" v-if="app.reviewed_at">
                <div class="timeline-time">{{ formatDate(app.reviewed_at) }}</div>
                <div class="timeline-title">Reviewed by Officer</div>
              </div>
              <div class="timeline-item" :class="{ active: app.approved_at }" v-if="app.approved_at">
                <div class="timeline-time">{{ formatDate(app.approved_at) }}</div>
                <div class="timeline-title">Approved</div>
              </div>
              <div class="timeline-item" :class="{ active: app.disbursed_at }" v-if="app.disbursed_at">
                <div class="timeline-time">{{ formatDate(app.disbursed_at) }}</div>
                <div class="timeline-title">Disbursed</div>
              </div>
            </div>
          </div>
        </div>

        <div class="card mb-4">
          <div class="card-header">
            <h2>Documents</h2>
            <button v-if="auth.isBorrower || auth.isAdmin" class="btn btn-outline btn-sm" @click="showUpload = true">+ Upload</button>
          </div>
          <div class="card-body" v-if="documents.length">
            <table class="data-table">
              <thead><tr><th>File</th><th>Type</th><th>Size</th><th>Category</th><th>Uploaded</th><th>Action</th></tr></thead>
              <tbody>
                <tr v-for="doc in documents" :key="doc.id">
                  <td>{{ doc.original_name }}</td>
                  <td class="text-sm text-muted">{{ doc.file_type }}</td>
                  <td class="text-sm">{{ formatSize(doc.file_size) }}</td>
                  <td><span class="text-sm">{{ doc.category }}</span></td>
                  <td class="text-sm text-muted">{{ formatDate(doc.created_at) }}</td>
                  <td><button class="link-btn" @click="downloadDoc(doc)">Download</button></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="card-body"><div class="empty-state"><p>No documents uploaded yet.</p></div></div>
        </div>

        <div class="card mb-4" v-if="app.supplements?.length">
          <div class="card-header"><h2>Complementary Information Requests</h2></div>
          <div class="card-body">
            <div v-for="s in app.supplements" :key="s.id" style="padding:12px;border:1px solid #dce3ea;border-radius:6px;margin-bottom:8px;">
              <div class="flex-between mb-2">
                <strong class="text-sm">Request from {{ s.requester_name }}:</strong>
                <span :class="`status-badge ${s.status === 'responded' ? 'status-approved' : 'status-pending_supplement'}`">{{ s.status }}</span>
              </div>
              <!-- VULN-06 kept: v-html renders unfiltered HTML -->
              <div style="background:#f8f9fc;padding:10px;border-radius:4px;margin-bottom:8px;font-size:13px;line-height:1.5;" v-html="s.description"></div>
              <div v-if="s.response" style="background:#e8f0fe;padding:10px;border-radius:4px;font-size:13px;line-height:1.5;">
                <strong>Response:</strong> <span v-html="s.response"></span>
              </div>
              <div v-if="s.status === 'pending' && auth.isBorrower && app.borrower_id === auth.user?.id" class="mt-2">
                <textarea v-model="supplementReplies[s.id]" rows="3" style="width:100%;"></textarea>
                <button class="btn btn-primary btn-sm mt-2" @click="respondSupplement(s)">Send Response</button>
              </div>
            </div>
          </div>
        </div>

        <div class="card mb-4" v-if="app.reviews?.length">
          <div class="card-header"><h2>Review Comments</h2></div>
          <div class="card-body">
            <div v-for="r in app.reviews" :key="r.id" style="padding:12px;border-left:3px solid #0066cc;margin-bottom:10px;">
              <div class="flex-between mb-1">
                <span class="text-sm font-weight:500">{{ r.reviewer_name }}</span>
                <span class="text-sm text-muted">{{ formatDate(r.created_at) }}</span>
              </div>
              <p style="font-size:13px;margin-top:4px;">{{ r.comment }}</p>
              <div v-if="r.rating" class="text-sm text-muted mt-2">Rating: {{ r.rating }}/10</div>
            </div>
          </div>
        </div>
      </template>

      <!-- Risk Assessment Modal -->
      <div v-if="showRiskPanel" class="modal-overlay">
        <div class="modal-body">
          <h2 style="font-size:18px;margin-bottom:20px;">Risk Assessment — {{ app.app_no }}</h2>
          <div class="form-field">
            <label class="required">Decision</label>
            <select v-model="riskDecision"><option value="">Select...</option><option value="approved">Approve</option><option value="rejected">Reject</option></select>
          </div>
          <div class="form-field" v-if="riskDecision === 'rejected'">
            <label>Rejection Reason</label>
            <textarea v-model="riskReason" rows="3"></textarea>
          </div>
          <div class="form-field">
            <label>Interest Rate (%)</label>
            <input v-model="riskRate" type="number" step="0.01" min="0" max="50" placeholder="e.g. 2.35" />
          </div>
          <div class="flex gap-2" style="justify-content:flex-end;margin-top:20px;">
            <button class="btn btn-outline" @click="showRiskPanel = false">Cancel</button>
            <button class="btn btn-success" @click="submitRiskAssessment" :disabled="!riskDecision">Submit</button>
          </div>
        </div>
      </div>

      <!-- Reject Modal -->
      <div v-if="showRejectPanel" class="modal-overlay">
        <div class="modal-body">
          <h2 style="font-size:18px;margin-bottom:20px;">Reject application</h2>
          <div class="form-field">
            <label>Reason</label>
            <textarea v-model="rejectReason" rows="4"></textarea>
          </div>
          <div class="flex gap-2" style="justify-content:flex-end;margin-top:20px;">
            <button class="btn btn-outline" @click="showRejectPanel = false">Cancel</button>
            <button class="btn btn-danger" @click="doReject">Reject</button>
          </div>
        </div>
      </div>

      <!-- Upload Modal -->
      <div v-if="showUpload" class="modal-overlay">
        <div class="modal-body">
          <h2 style="font-size:18px;margin-bottom:20px;">Upload document</h2>
          <input type="file" ref="fileInput" @change="uploadFile" />
          <div class="form-field">
            <label>Category</label>
            <select v-model="uploadCategory">
              <option value="general">General</option>
              <option value="feasibility_study">Feasibility Study</option>
              <option value="financial">Financial</option>
              <option value="environmental">Environmental</option>
              <option value="technical">Technical</option>
            </select>
          </div>
          <div class="flex gap-2" style="justify-content:flex-end;margin-top:20px;">
            <button class="btn btn-outline" @click="showUpload = false">Close</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore, api } from '../../store/auth'
import AppSidebar from '../../components/Sidebar.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const app = ref(null)
const documents = ref([])
const loading = ref(true)
const showRiskPanel = ref(false)
const showRejectPanel = ref(false)
const showUpload = ref(false)
const riskDecision = ref('')
const riskReason = ref('')
const riskRate = ref('')
const rejectReason = ref('')
const uploadCategory = ref('general')
const fileInput = ref(null)
const calcResult = ref(null)
const supplementReplies = reactive({})

const canEdit = computed(() =>
  auth.isBorrower && app.value?.borrower_id === auth.user?.id && app.value?.status === 'draft'
)

async function reload() {
  loading.value = true
  try {
    const [appRes, docsRes] = await Promise.all([
      api.get(`/applications/${route.params.id}`),
      api.get(`/documents/application/${route.params.id}`)
    ])
    app.value = appRes.data.application
    documents.value = docsRes.data.documents || []
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

onMounted(reload)

async function submitApp() {
  await api.post(`/applications/${route.params.id}/submit`)
  reload()
}

async function moveToReview() {
  await api.post(`/applications/${route.params.id}/pick-up`).catch(() => {})
  await api.post(`/applications/${route.params.id}/approve`).catch(() => {})
  reload()
}

async function submitRiskAssessment() {
  await api.post(`/applications/${route.params.id}/risk-assessment`, {
    decision: riskDecision.value,
    reason: riskReason.value,
    interest_rate: riskRate.value || null
  })
  showRiskPanel.value = false
  reload()
}

async function doReject() {
  await api.post(`/applications/${route.params.id}/reject`, { reason: rejectReason.value })
  showRejectPanel.value = false
  reload()
}

async function respondSupplement(s) {
  const text = supplementReplies[s.id] || ''
  await api.post(`/applications/${route.params.id}/supplements/${s.id}/respond`, { response: text })
  reload()
}

async function calcInterest() {
  const res = await api.post(`/applications/${route.params.id}/calculate-interest`, {})
  calcResult.value = res.data
}

async function downloadDoc(doc) {
  // Fixed: authenticated blob download so JWT interceptor is respected.
  const res = await api.get(`/documents/${doc.id}`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = doc.original_name
  a.click()
  URL.revokeObjectURL(url)
}

async function uploadFile(e) {
  const f = e.target.files?.[0]
  if (!f) return
  const form = new FormData()
  form.append('file', f)
  form.append('category', uploadCategory.value)
  await api.post(`/documents/upload/${route.params.id}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  showUpload.value = false
  reload()
}

function formatStatus(s) { return s ? s.replace(/_/g, ' ') : s }
function formatDate(d) { return d ? new Date(d).toLocaleDateString('en-US', { year:'numeric', month:'short', day:'numeric' }) : '' }
function formatCurrency(v, c) { return v ? new Intl.NumberFormat('en-US',{minimumFractionDigits:0}).format(Number(v)) + ' ' + (c||'USD') : '-' }
function formatSize(b) { if (!b) return '-'; return b < 1024 ? b+'B' : b < 1048576 ? (b/1024).toFixed(1)+'KB' : (b/1048576).toFixed(1)+'MB' }
</script>

<style scoped>
.modal-overlay { position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.4);z-index:1000;display:flex;align-items:center;justify-content:center; }
.modal-body { background:white;border-radius:8px;padding:32px;width:500px;max-width:90vw; }
.link-btn { background:none;border:none;color:#1864ab;cursor:pointer;padding:0;font-size:13px; }
.btn-danger { background:#d64545;color:#fff;border:none;padding:8px 14px;border-radius:4px;cursor:pointer; }
</style>
