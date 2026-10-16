import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'
import Login from './views/Login.vue'
import Count from './views/Count.vue'
import History from './views/History.vue'
import HistoryDetail from './views/HistoryDetail.vue'
import Stats from './views/Stats.vue'
import Users from './views/Users.vue'
import UserDetail from './views/UserDetail.vue'

const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/login', component: Login },
  { path: '/', redirect: '/count' },
  { path: '/count', component: Count, meta: { auth: true } },
  { path: '/history', component: History, meta: { auth: true } },
  { path: '/history/:taskId', component: HistoryDetail, meta: { auth: true } },
  { path: '/stats', component: Stats, meta: { auth: true } },
  { path: '/admin/users', component: Users, meta: { auth: true, admin: true } }
  ,{ path: '/admin/users/:userId', component: UserDetail, meta: { auth: true, admin: true } },
  // 兜底路由：刷新到已失效或拼错的地址时不再显示 404，直接回到计数页。
  { path: '/:pathMatch(.*)*', redirect: '/count' }
] })
router.beforeEach(to => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.isLoggedIn) return '/login'
  if (to.meta.admin && !auth.isAdmin) return '/count'
  if (to.path === '/login' && auth.isLoggedIn) return '/count'
})
export default router
