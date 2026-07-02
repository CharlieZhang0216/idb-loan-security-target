<template>
  <div class="app-sidebar">
    <router-link v-for="item in menuItems" :key="item.path" :to="item.path"
      class="sidebar-item" :class="{ active: isActive(item.path) }">
      <component :is="item.icon" />
      <span>{{ item.label }}</span>
    </router-link>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../store/auth'

const route = useRoute()
const auth = useAuthStore()

const menuItems = computed(() => {
  const items = [
    { path: '/dashboard', label: 'Dashboard', icon: 'HomeFilled', roles: ['borrower','officer','risk','admin'] },
    { path: '/applications', label: 'Applications', icon: 'List', roles: ['borrower','officer','risk','admin'] },
  ]

  if (auth.isOfficer || auth.isAdmin) {
    items.push({ path: '/review', label: 'Review Queue', icon: 'Checked', roles: ['officer','admin'] })
  }
  if (auth.isRisk || auth.isAdmin) {
    items.push({ path: '/risk', label: 'Risk Assessment', icon: 'WarningFilled', roles: ['risk','admin'] })
  }
  if (auth.isAdmin) {
    items.push({ path: '/admin', label: 'Admin', icon: 'Setting', roles: ['admin'] })
    items.push({ path: '/admin/users', label: 'Users', icon: 'UserFilled', roles: ['admin'] })
  }

  items.push({ path: '/reports', label: 'Reports', icon: 'Document', roles: ['borrower','officer','risk','admin'] })

  return items.filter(item => item.roles.includes(auth.role))
})

function isActive(path) {
  return route.path === path || (path !== '/dashboard' && route.path.startsWith(path))
}
</script>
