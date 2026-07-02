<template>
  <div>
    <AppHeader v-if="showChrome" />
    <router-view />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './store/auth'
import AppHeader from './components/AppHeader.vue'

const route = useRoute()
const auth = useAuthStore()

// The AppHeader (with logout + notifications) shows on every authenticated
// route. Login page hides it.
const showChrome = computed(() => auth.isAuthenticated && route.name !== 'Login')
</script>

<style>
.app-body { display: flex; }
.app-content { flex: 1; padding: 24px; }
</style>
