<script setup>
import { ref, onMounted } from 'vue'
import request from '../api'
import { ElMessage } from 'element-plus'
import { formatTime } from '../utils/format'
const users = ref([]); const visible = ref(false); const form = ref({ username: '', password: '', role: 'user' })
const load = async () => { users.value = (await request.get('/admin/users')).items }
const create = async () => {
	if (!form.value.username.trim()) return ElMessage.warning('请输入用户名')
	if (form.value.password.length < 6) return ElMessage.warning('密码至少需要 6 个字符')
	try { await request.post('/admin/users', { ...form.value, username: form.value.username.trim() }); visible.value = false; form.value = { username: '', password: '', role: 'user' }; await load(); ElMessage.success('用户已创建') }
	catch (error) { const detail = error.response?.data?.detail; ElMessage.error(Array.isArray(detail) ? detail.map(item => item.msg).join('；') : detail || error.message) }
}
onMounted(load)
</script>
<template><h1 class="page-title">用户管理</h1><p class="muted">管理员可以新增内部使用账号并查看账号状态。</p><div class="panel"><div class="row" style="justify-content:flex-end;margin-bottom:16px"><el-button type="primary" @click="visible=true">新增用户</el-button></div><div class="table-scroll"><el-table :data="users" @row-click="row => $router.push('/admin/users/' + row.id)"><el-table-column prop="username" label="用户名"/><el-table-column label="角色"><template #default="scope">{{ scope.row.role === 'admin' ? '管理员' : '普通用户' }}</template></el-table-column><el-table-column label="状态"><template #default="scope">{{ scope.row.status === 1 ? '正常' : '禁用' }}</template></el-table-column><el-table-column label="创建时间"><template #default="scope">{{ formatTime(scope.row.created_at) }}</template></el-table-column><el-table-column label="最后登录"><template #default="scope">{{ formatTime(scope.row.last_login_at) }}</template></el-table-column></el-table></div></div><el-dialog v-model="visible" title="新增用户" width="420px"><el-form label-position="top"><el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item><el-form-item label="初始密码"><el-input v-model="form.password" type="password" show-password /></el-form-item><el-form-item label="角色"><el-select v-model="form.role"><el-option label="普通用户" value="user"/><el-option label="管理员" value="admin"/></el-select></el-form-item></el-form><template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" @click="create">创建</el-button></template></el-dialog></template>
