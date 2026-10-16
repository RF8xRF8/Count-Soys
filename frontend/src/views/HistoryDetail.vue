<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import request from '../api'
import { ElMessage } from 'element-plus'
import ImageViewer from '../components/ImageViewer.vue'
import { formatTime } from '../utils/format'

const route = useRoute()
const task = ref(null)
const showViewer = ref(false), viewerIndex = ref(0)
const openViewer = index => { viewerIndex.value = index; showViewer.value = true }
onMounted(async () => {
  try { task.value = await request.get(`/count/${route.params.taskId}`) } catch (error) { ElMessage.error(error.response?.data?.detail || error.message) }
})
</script>
<template>
  <div v-if="task">
    <el-button text @click="$router.back()">返回历史任务</el-button>
    <h1 class="page-title">任务详情</h1>
    <p class="muted">{{ formatTime(task.created_at) }} · {{ task.mode }} · {{ task.count }} 个颗粒 · {{ task.elapsed_ms }} ms</p>
    <div class="panel detail-images"><div><h3>原图</h3><img :src="task.original_url" class="detail-image zoomable" @click="openViewer(0)"></div><div><h3>标注图</h3><img :src="task.annotated_url" class="detail-image zoomable" @click="openViewer(1)"></div></div>
    <ImageViewer v-if="showViewer" :urls="[task.original_url, task.annotated_url]" :initial-index="viewerIndex" @close="showViewer = false" />
  </div>
  <el-empty v-else description="正在加载任务"></el-empty>
</template>
<style scoped>.detail-images{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.detail-image{display:block;max-width:100%;max-height:720px;object-fit:contain}@media(max-width:720px){.detail-images{grid-template-columns:1fr}}</style>
