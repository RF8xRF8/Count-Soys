<script setup>
import { ref } from 'vue'
import request from '../api'
import { ElMessage } from 'element-plus'
import { compressImage } from '../utils/image'
import ImageViewer from '../components/ImageViewer.vue'

const file = ref(null), mode = ref('beans'), result = ref(null), loading = ref(false)
const params = ref({ min_area: 500, draw_number: true })
const original = ref(''), fileName = ref(''), fileSize = ref(0)
const showViewer = ref(false), viewerIndex = ref(0)
const cameraInput = ref(null), albumInput = ref(null)
// 触摸设备才提供「拍照」入口；桌面上两个入口都是打开文件选择框。
const isTouch = typeof window !== 'undefined' && (window.matchMedia?.('(pointer: coarse)').matches || 'ontouchstart' in window)
const openViewer = index => { viewerIndex.value = index; showViewer.value = true }

const formatSize = bytes => bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(bytes / 1024)) + ' KB'

const selectFile = e => {
  const picked = e.target.files?.[0]
  if (!picked) return
  file.value = picked; fileName.value = picked.name; fileSize.value = picked.size
  if (original.value) URL.revokeObjectURL(original.value)
  original.value = URL.createObjectURL(picked)
  result.value = null
  e.target.value = ''
}

// 直接点上传区：手机上默认调起相机，桌面端打开文件选择框。
const pickPhoto = () => (isTouch ? cameraInput : albumInput).value?.click()

const submit = async () => {
  if (!file.value) return ElMessage.warning('请先选择图片')
  loading.value = true
  try {
    const compressed = await compressImage(file.value)
    const form = new FormData()
    const name = compressed.type === 'image/jpeg' ? fileName.value.replace(/\.\w+$/i, '') + '.jpg' : fileName.value
    form.append('file', compressed, name)
    form.append('mode', mode.value)
    form.append('params', JSON.stringify(params.value))
    result.value = await request.post('/count', form)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  } finally {
    loading.value = false
  }
}

</script>
<template>
  <h1 class="page-title">图片计数</h1>
  <p class="muted">选择颗粒类型，拍照或上传图片，系统会自动识别每个颗粒。</p>
  <div class="panel">
    <div class="count-controls">
      <div class="control">
        <span class="control-label">颗粒类型</span>
        <el-radio-group v-model="mode">
          <el-radio-button value="pills">药片</el-radio-button>
          <el-radio-button value="beans">黄豆</el-radio-button>
        </el-radio-group>
      </div>
      <div class="control">
        <span class="control-label">最小颗粒面积</span>
        <el-input-number v-model="params.min_area" :min="20" :step="50" size="large" />
      </div>
    </div>
    <div class="upload-box" style="margin-top:26px" @click="pickPhoto">
      <div v-if="!file">点击拍照或选择图片</div>
      <div v-else>{{ fileName }} <span class="muted">· {{ formatSize(fileSize) }}</span></div>
      <div class="muted upload-hint">支持手机拍照，也可从相册选择，上传前会自动压缩图片</div>
      <div class="upload-actions" @click.stop>
        <el-button v-if="isTouch" @click="cameraInput.click()">拍照</el-button>
        <el-button @click="albumInput.click()">{{ isTouch ? '从相册选择' : '选择图片' }}</el-button>
      </div>
      <input ref="cameraInput" type="file" accept="image/*" capture="environment" hidden @click.stop @change="selectFile">
      <input ref="albumInput" type="file" accept="image/*" hidden @click.stop @change="selectFile">
    </div>
    <el-button class="submit-btn" type="primary" size="large" :loading="loading" @click="submit">上传并计数</el-button>
  </div>
  <div v-if="result" class="panel" style="margin-top:20px">
    <div class="result-head">
      <div>
        <span class="muted">识别结果</span>
        <div class="result-count">{{ result.count }} <small>个颗粒</small></div>
        <span class="muted">耗时 {{ result.elapsed_ms }} ms</span>
      </div>
      <div class="result-actions">
        <el-button :loading="loading" @click="submit">重新计数</el-button>
      </div>
    </div>
    <div class="compare">
      <figure>
        <figcaption>原图</figcaption>
        <img v-if="original" :src="original" class="result-image zoomable" @click="openViewer(0)">
      </figure>
      <figure>
        <figcaption>标注图</figcaption>
        <img :src="result.annotated_url" class="result-image zoomable" @click="openViewer(1)">
      </figure>
    </div>
    <ImageViewer v-if="showViewer" :urls="[original, result.annotated_url]" :initial-index="viewerIndex" @close="showViewer = false" />
  </div>
</template>
