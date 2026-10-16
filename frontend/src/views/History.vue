<script setup>
import { ref, onMounted } from 'vue'
import request from '../api'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'
import { formatTime } from '../utils/format'

const auth = useAuthStore()
const items = ref([])
const load = async () => { items.value = (await request.get('/tasks')).items }
const remove = async id => { try { await request.delete('/tasks/' + id); await load() } catch (e) { ElMessage.error(e.message) } }
const modeLabel = mode => ({ pills: '药片', beans: '黄豆', cells: '细胞' }[mode] || mode)
onMounted(load)
</script>
<template>
	<h1 class="page-title">历史任务</h1>
	<p class="muted">点击记录查看原图和压缩后的标注图。{{ auth.isAdmin ? '管理员可查看所有用户记录。' : '' }}</p>
	<div class="panel desktop-only">
		<el-table :data="items" empty-text="还没有计数记录" @row-click="row => $router.push('/history/' + row.task_id)">
			<el-table-column v-if="auth.isAdmin" prop="username" label="用户" min-width="100"/>
			<el-table-column prop="created_at" label="时间" min-width="160"><template #default="scope">{{ formatTime(scope.row.created_at) }}</template></el-table-column>
			<el-table-column label="模式" min-width="90"><template #default="scope">{{ modeLabel(scope.row.mode) }}</template></el-table-column>
			<el-table-column prop="count" label="计数" min-width="80"/>
			<el-table-column prop="elapsed_ms" label="耗时(ms)" min-width="100"/>
			<el-table-column label="操作" min-width="150"><template #default="scope"><el-button link type="primary" @click.stop="$router.push('/history/' + scope.row.task_id)">查看图片</el-button><el-button v-if="!auth.isAdmin" link type="danger" @click.stop="remove(scope.row.task_id)">删除</el-button></template></el-table-column>
		</el-table>
	</div>
	<div class="only-mobile">
		<el-empty v-if="!items.length" description="还没有计数记录"/>
		<div v-else class="task-cards">
			<div v-for="row in items" :key="row.task_id" class="panel task-card" @click="$router.push('/history/' + row.task_id)">
				<div class="task-card-top"><span class="task-card-count">{{ row.count }} <small>个颗粒</small></span><span class="muted">{{ modeLabel(row.mode) }}</span></div>
				<div class="muted task-card-meta">{{ formatTime(row.created_at) }}<template v-if="auth.isAdmin"> · {{ row.username }}</template> · {{ row.elapsed_ms }} ms</div>
				<div class="task-card-actions">
					<el-button link type="primary">查看图片</el-button>
					<el-button v-if="!auth.isAdmin" link type="danger" @click.stop="remove(row.task_id)">删除</el-button>
				</div>
			</div>
		</div>
	</div>
</template>
