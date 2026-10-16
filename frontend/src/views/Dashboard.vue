<script setup>
import { useAuthStore } from '../stores/auth'; const auth=useAuthStore()
</script>
<template><h1 class="page-title">你好，{{ auth.user?.username }}</h1><p class="muted">准备好处理下一张图片了吗？</p><div class="stats-grid"><div class="panel stat"><span class="muted">今日配额</span><strong>{{ auth.user?.daily_quota }}</strong><span class="muted">次可用</span></div><div class="panel stat"><span class="muted">系统状态</span><strong>在线</strong><span class="muted">服务运行正常</span></div></div><div class="panel"><h2>快速开始</h2><p class="muted">上传一张药片、豆子或细胞图片，系统会自动识别并标记每个目标。</p><el-button type="primary" @click="$router.push('/count')">开始图片计数</el-button></div></template>
