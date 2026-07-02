import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../store/auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/shared/LoginView.vue'), meta: { guest: true } },
  { path: '/', redirect: '/dashboard' },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/shared/DashboardView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/applications',
    name: 'Applications',
    component: () => import('../views/shared/ApplicationsView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/applications/create',
    name: 'CreateApplication',
    component: () => import('../views/borrower/CreateApplication.vue'),
    meta: { requiresAuth: true, roles: ['borrower', 'admin'] }
  },
  {
    path: '/applications/:id',
    name: 'ApplicationDetail',
    component: () => import('../views/shared/ApplicationDetail.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/review',
    name: 'ReviewQueue',
    component: () => import('../views/officer/ReviewQueue.vue'),
    meta: { requiresAuth: true, roles: ['officer', 'admin'] }
  },
  {
    path: '/risk',
    name: 'RiskAssessment',
    component: () => import('../views/risk/RiskAssessment.vue'),
    meta: { requiresAuth: true, roles: ['risk', 'admin'] }
  },
  {
    path: '/admin',
    name: 'AdminPanel',
    component: () => import('../views/admin/AdminView.vue'),
    meta: { requiresAuth: true, roles: ['admin'] }
  },
  {
    path: '/admin/users',
    name: 'UserManagement',
    component: () => import('../views/admin/UserManagement.vue'),
    meta: { requiresAuth: true, roles: ['admin'] }
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('../views/shared/ReportsView.vue'),
    meta: { requiresAuth: true }
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    next('/login')
  } else if (to.meta.guest && auth.isAuthenticated) {
    next('/dashboard')
  } else if (to.meta.roles && !to.meta.roles.includes(auth.user?.role)) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
