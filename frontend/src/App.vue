<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
const route = useRoute(); const router = useRouter(); const auth = useAuthStore()
const logout = async () => { await auth.logout(); router.push('/login') }
const tabs = [
  { path: '/count', label: '计数', icon: 'count' },
  { path: '/history', label: '历史', icon: 'history' },
  { path: '/stats', label: '统计', icon: 'stats' },
  { path: '/admin/users', label: '用户', icon: 'users', admin: true }
]
const isActive = tab => route.path === tab.path || route.path.startsWith(tab.path + '/')
</script>
<template>
  <el-container v-if="route.path !== '/login'" class="shell">
    <el-aside width="220px" class="sidebar">
      <div class="brand">PHOTO<br><strong>COUNT</strong></div>
      <el-menu router :default-active="route.path">
        <el-menu-item index="/count">开始计数</el-menu-item>
        <el-menu-item index="/history">历史任务</el-menu-item>
        <el-menu-item index="/stats">统计分析</el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/admin/users">用户管理</el-menu-item>
      </el-menu>
      <el-button text class="logout" @click="logout">退出登录</el-button>
    </el-aside>
    <el-main class="main">
      <header class="topbar">
        <strong class="topbar-brand">PHOTO COUNT</strong>
        <el-button text type="danger" @click="logout">退出</el-button>
      </header>
      <router-view />
      <nav class="tabbar">
        <button v-for="tab in tabs" v-show="!tab.admin || auth.isAdmin" :key="tab.path" type="button" class="tabbar-item" :class="{ active: isActive(tab) }" @click="router.push(tab.path)">
          <svg v-if="tab.icon === 'count'" class="tabbar-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8.5h3.2l1.6-2h6.4l1.6 2H20a1 1 0 0 1 1 1V18a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.2" r="3.1"/></svg>
          <svg v-else-if="tab.icon === 'history'" class="tabbar-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l2.6 2"/></svg>
          <svg v-else-if="tab.icon === 'stats'" class="tabbar-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19v-7M12 19V6M19 19v-5"/></svg>
          <svg v-else class="tabbar-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.2"/><path d="M5.5 19c1.2-3.1 3.6-4.7 6.5-4.7s5.3 1.6 6.5 4.7"/></svg>
          <span class="tabbar-label">{{ tab.label }}</span>
        </button>
      </nav>
    </el-main>
  </el-container>
  <router-view v-else />
</template>
