<template>
  <div>
    <AppHeader />
    <div class="app-body">
      <AppSidebar />
      <div class="app-content">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup>
import AppHeader from './AppHeader.vue'
import AppSidebar from './Sidebar.vue'
</script>
