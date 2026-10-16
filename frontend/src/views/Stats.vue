<script setup>
import { ref, onMounted } from 'vue'
import request from '../api'
import { useAuthStore } from '../stores/auth'
const auth = useAuthStore(); const data = ref({}); const users = ref([])
onMounted(async () => { data.value = await request.get('/stats/me/summary'); if (auth.isAdmin) users.value = await request.get('/admin/stats/users') })
</script>
<template><h1 class="page-title">统计分析</h1><p class="muted">任务数量和平均处理时长。</p><div class="stats-grid"><div class="panel stat"><span class="muted">我的总任务</span><strong>{{ data.total_tasks||0 }}</strong></div><div class="panel stat"><span class="muted">成功任务</span><strong>{{ data.success_tasks||0 }}</strong></div><div class="panel stat"><span class="muted">累计目标</span><strong>{{ data.total_objects||0 }}</strong></div><div class="panel stat"><span class="muted">平均耗时</span><strong>{{ data.avg_elapsed_ms||0 }}<small> ms</small></strong></div></div><div v-if="auth.isAdmin" class="panel"><h2>用户任务统计</h2><div class="table-scroll"><el-table :data="users"><el-table-column prop="username" label="用户"/><el-table-column prop="task_count" label="任务次数"/><el-table-column prop="success_count" label="成功"/><el-table-column prop="failed_count" label="失败"/><el-table-column prop="avg_elapsed_ms" label="平均耗时(ms)"/><el-table-column prop="total_objects" label="识别目标"/></el-table></div></div></template>
