<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '../api'
import { ElMessage } from 'element-plus'
import { formatTime } from '../utils/format'

const route = useRoute(); const router = useRouter(); const user = ref(null); const newPassword = ref(''); const loading = ref(false)
const load = async () => { try { user.value = await request.get('/admin/users/' + route.params.userId) } catch (error) { ElMessage.error(error.response?.data?.detail || error.message) } }
const resetPassword = async () => {
  if (newPassword.value.length < 6) return ElMessage.warning('新密码至少需要 6 个字符')
  loading.value = true
  try { await request.post('/admin/users/' + route.params.userId + '/reset-password', { new_password: newPassword.value }); newPassword.value = ''; ElMessage.success('密码已重置') } catch (error) { ElMessage.error(error.response?.data?.detail || error.message) } finally { loading.value = false }
}
onMounted(load)
</script>
<template>
  <div v-if="user"><el-button text @click="router.push('/admin/users')">返回用户管理</el-button><h1 class="page-title">用户详情</h1><div class="panel user-detail"><div><span class="muted">用户名</span><strong>{{ user.username }}</strong></div><div><span class="muted">角色</span><strong>{{ user.role === 'admin' ? '管理员' : '普通用户' }}</strong></div><div><span class="muted">状态</span><strong>{{ user.status === 1 ? '正常' : '禁用' }}</strong></div><div><span class="muted">创建时间</span><strong>{{ formatTime(user.created_at) }}</strong></div><div><span class="muted">最后登录</span><strong>{{ formatTime(user.last_login_at) }}</strong></div></div><div class="panel password-panel"><h2>重置密码</h2><p class="muted">管理员可为该用户设置新的初始密码。</p><div class="row"><el-input v-model="newPassword" type="password" show-password placeholder="至少 6 个字符" style="width:100%;max-width:320px"/><el-button type="primary" :loading="loading" @click="resetPassword">重置密码</el-button></div></div></div><el-empty v-else description="正在加载用户信息" />
</template>
<style scoped>.user-detail{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.user-detail span,.user-detail strong{display:block}.user-detail strong{font-size:20px;margin-top:6px}.password-panel{margin-top:20px}@media(max-width:720px){.user-detail{grid-template-columns:1fr}}</style>