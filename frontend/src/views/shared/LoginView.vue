<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <div style="display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:8px;">
          <div style="width:40px;height:40px;background:#e8a600;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:18px;color:#003366;">I</div>
        </div>
        <h1>IDB Loan Portal</h1>
        <p class="login-subtitle">International Development Bank</p>
      </div>

      <div v-if="error" style="background:#ffe3e3;color:#c92a2a;padding:10px 14px;border-radius:6px;margin-bottom:16px;font-size:13px;">
        {{ error }}
      </div>

      <form @submit.prevent="handleLogin">
        <div class="form-field">
          <label class="required">Username</label>
          <input v-model="username" type="text" placeholder="Enter your username" required />
        </div>
        <div class="form-field">
          <label class="required">Password</label>
          <input v-model="password" type="password" placeholder="Enter your password" required />
        </div>
        <button type="submit" class="btn btn-primary w-full btn-lg" :disabled="loading" style="margin-top:8px;">
          {{ loading ? 'Signing in...' : 'Sign In' }}
        </button>
      </form>

      <div style="margin-top:20px;padding-top:16px;border-top:1px solid #dce3ea;font-size:11px;color:#8899aa;text-align:center;">
        <p style="margin-bottom:4px;"><strong>Demo Credentials:</strong></p>
        <code style="font-size:10px;">br_cn_liwei / password123 (Borrower)</code><br/>
        <code style="font-size:10px;">of_anderson / officer123 (Officer)</code><br/>
        <code style="font-size:10px;">ri_mueller / risk123 (Risk)</code><br/>
        <code style="font-size:10px;">ad_martinez / admin123 (Admin)</code>
      </div>

      <div style="margin-top:16px;text-align:center;">
        <a @click="ssoMockLogin" style="color:#1864ab;font-size:13px;cursor:pointer;text-decoration:none;">
          Sign in with Member Government SSO
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore, api } from '../../store/auth'

const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.response?.data?.error || 'Login failed'
  } finally {
    loading.value = false
  }
}

function ssoMockLogin() {
  // VULN-02: SSO callback URL is not validated
  // In a real attack, redirect could point to attacker's server
  const ssoToken = `sso-${username.value || 'br_cn_liwei'}-${Date.now()}`
  window.location.href = `/api/auth/sso/callback?token=${ssoToken}&redirect=/dashboard`
}
</script>
