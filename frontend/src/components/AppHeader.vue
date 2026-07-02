<template>
  <header class="app-header">
    <router-link to="/dashboard" class="logo">
      <div class="logo-icon">IDB</div>
      <span class="logo-text">Loan Portal</span>
    </router-link>
    <div class="user-info">
      <span class="role-badge">{{ auth.role }}</span>
      <span class="text-sm" style="opacity:0.8;">{{ auth.user?.full_name }}</span>
      <button @click="handleLogout">Sign Out</button>
    </div>
  </header>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'

const router = useRouter()
const auth = useAuthStore()

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>
