<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

// 全屏图片查看器：双指捏合缩放、单指/鼠标拖动、双击放大、滚轮缩放。
// Element Plus 的 el-image-viewer 在移动端只处理单指拖动（touches.length !== 1 直接返回），
// 没有双指缩放，所以这里自己实现一个覆盖层。

const props = defineProps({
  urls: { type: Array, default: () => [] },
  initialIndex: { type: Number, default: 0 }
})
const emit = defineEmits(['close'])

const MIN_SCALE = 1
const MAX_SCALE = 8
const DOUBLE_TAP_SCALE = 2.5

const container = ref(null)
const imageEl = ref(null)
const index = ref(0)
const scale = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)
const animate = ref(false)

// 手势状态放在普通变量里，避免每次 pointermove 都触发响应式更新。
const pointers = new Map()
let gesture = null
let lastTapAt = 0
let pressedAt = 0
let moved = false
let pressedBackdrop = false
let previousOverflow = ''

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))
const currentUrl = computed(() => props.urls[index.value] || '')
const hasMultiple = computed(() => props.urls.length > 1)
const imageStyle = computed(() => ({
  transform: `translate(-50%, -50%) translate(${offsetX.value}px, ${offsetY.value}px) scale(${scale.value})`
}))

// 视口中心（图片未缩放时所在的屏幕坐标）。
const viewportCenter = () => {
  const rect = container.value?.getBoundingClientRect()
  return rect ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 } : { x: 0, y: 0 }
}

// 把平移量限制在合理范围，保证图片不会整个滑出视野。
const limitOffset = () => {
  const element = imageEl.value
  const box = container.value
  if (!element || !box) return
  const maxX = Math.max(0, (element.offsetWidth * scale.value - box.clientWidth) / 2)
  const maxY = Math.max(0, (element.offsetHeight * scale.value - box.clientHeight) / 2)
  offsetX.value = clamp(offsetX.value, -maxX, maxX)
  offsetY.value = clamp(offsetY.value, -maxY, maxY)
}

const reset = (withAnimation = true) => {
  animate.value = withAnimation
  scale.value = MIN_SCALE
  offsetX.value = 0
  offsetY.value = 0
}

// 以屏幕坐标 (clientX, clientY) 为锚点缩放：锚点下的像素在缩放前后保持不动。
const zoomAt = (nextScale, clientX, clientY) => {
  const target = clamp(nextScale, MIN_SCALE, MAX_SCALE)
  const center = viewportCenter()
  const mx = clientX - center.x
  const my = clientY - center.y
  const ratio = target / scale.value
  offsetX.value = mx - ratio * (mx - offsetX.value)
  offsetY.value = my - ratio * (my - offsetY.value)
  scale.value = target
  limitOffset()
}

const beginGesture = () => {
  const list = [...pointers.values()]
  animate.value = false
  if (list.length === 1) {
    gesture = { mode: 'pan', startX: list[0].x, startY: list[0].y, baseX: offsetX.value, baseY: offsetY.value }
  } else if (list.length >= 2) {
    const [first, second] = list
    gesture = {
      mode: 'pinch',
      distance: Math.hypot(first.x - second.x, first.y - second.y) || 1,
      midX: (first.x + second.x) / 2,
      midY: (first.y + second.y) / 2,
      baseScale: scale.value,
      baseX: offsetX.value,
      baseY: offsetY.value,
      center: viewportCenter()
    }
  } else {
    gesture = null
  }
}

// 双指捏合：缩放比例由两指间距决定，同时让手势开始时中点下的像素跟随当前中点。
const applyPinch = (first, second) => {
  const distance = Math.hypot(first.x - second.x, first.y - second.y)
  const target = clamp(gesture.baseScale * (distance / gesture.distance), MIN_SCALE, MAX_SCALE)
  const midX = (first.x + second.x) / 2
  const midY = (first.y + second.y) / 2
  const origin = gesture.center
  const imageX = (gesture.midX - origin.x - gesture.baseX) / gesture.baseScale
  const imageY = (gesture.midY - origin.y - gesture.baseY) / gesture.baseScale
  offsetX.value = midX - origin.x - target * imageX
  offsetY.value = midY - origin.y - target * imageY
  scale.value = target
  limitOffset()
}

const onPointerDown = event => {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  // 捕获指针：手指滑出窗口后仍能收到 pointerup，避免残留按下的手指。
  if (!container.value?.hasPointerCapture?.(event.pointerId)) {
    try { container.value?.setPointerCapture?.(event.pointerId) } catch { /* 指针已失效，忽略 */ }
  }
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  if (pointers.size === 1) {
    moved = false
    pressedAt = Date.now()
    // 点在空白遮罩（而非图片或按钮）上时，抬手可关闭。
    pressedBackdrop = event.target === container.value
  }
  beginGesture()
}

const onPointerMove = event => {
  if (!pointers.has(event.pointerId) || !gesture) return
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  const list = [...pointers.values()]
  if (gesture.mode === 'pan' && list.length === 1) {
    const dx = list[0].x - gesture.startX
    const dy = list[0].y - gesture.startY
    if (Math.abs(dx) > 6 || Math.abs(dy) > 6) moved = true
    offsetX.value = gesture.baseX + dx
    offsetY.value = gesture.baseY + dy
    limitOffset()
  } else if (gesture.mode === 'pinch' && list.length >= 2) {
    moved = true
    applyPinch(list[0], list[1])
  }
}

const onPointerUp = event => {
  if (!pointers.has(event.pointerId)) return
  pointers.delete(event.pointerId)
  if (pointers.size > 0) {
    // 双指变单指（或反之）时重新起势，避免画面跳变。
    beginGesture()
    return
  }
  gesture = null
  if (scale.value < MIN_SCALE + 0.02) reset(true)
  else limitOffset()
  const backdrop = pressedBackdrop
  pressedBackdrop = false
  if (moved || Date.now() - pressedAt > 350) return
  if (backdrop) {
    emit('close')
    return
  }
  // 双击（含双指轻点、鼠标双击）：在 1x 与放大倍数之间切换。
  const now = Date.now()
  if (now - lastTapAt < 450) {
    lastTapAt = 0
    if (scale.value > MIN_SCALE + 0.02) reset(true)
    else {
      animate.value = true
      zoomAt(DOUBLE_TAP_SCALE, event.clientX, event.clientY)
    }
  } else {
    lastTapAt = now
  }
}

const onWheel = event => {
  event.preventDefault()
  animate.value = false
  zoomAt(scale.value * (event.deltaY < 0 ? 1.12 : 1 / 1.12), event.clientX, event.clientY)
}

const go = step => {
  if (!hasMultiple.value) return
  index.value = (index.value + step + props.urls.length) % props.urls.length
  reset(false)
}

const onKeydown = event => {
  if (event.key === 'Escape') emit('close')
  else if (event.key === 'ArrowLeft') go(-1)
  else if (event.key === 'ArrowRight') go(1)
}

onMounted(() => {
  index.value = clamp(props.initialIndex, 0, Math.max(0, props.urls.length - 1))
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
  window.addEventListener('keydown', onKeydown)
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
})

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = previousOverflow
})
</script>

<template>
  <teleport to="body">
    <div ref="container" class="image-viewer" @pointerdown="onPointerDown" @wheel="onWheel" @contextmenu.prevent>
      <img ref="imageEl" class="image-viewer-image" :class="{ 'is-animated': animate }" :src="currentUrl" :style="imageStyle" draggable="false" alt="" @load="limitOffset">
      <button v-if="hasMultiple" type="button" class="image-viewer-nav is-prev" @pointerdown.stop @click.stop="go(-1)">‹</button>
      <button v-if="hasMultiple" type="button" class="image-viewer-nav is-next" @pointerdown.stop @click.stop="go(1)">›</button>
      <button type="button" class="image-viewer-close" @pointerdown.stop @click.stop="emit('close')">✕</button>
      <div v-if="hasMultiple" class="image-viewer-counter">{{ index + 1 }} / {{ urls.length }}</div>
      <div class="image-viewer-tip">双指捏合或双击放大，拖动查看细节</div>
    </div>
  </teleport>
</template>

<style scoped>
.image-viewer {
  position: fixed;
  inset: 0;
  z-index: 3000;
  overflow: hidden;
  background: rgba(0, 0, 0, .92);
  touch-action: none;
  -webkit-user-select: none;
  user-select: none;
  cursor: grab;
}
.image-viewer:active { cursor: grabbing }
.image-viewer-image {
  position: absolute;
  left: 50%;
  top: 50%;
  display: block;
  max-width: 92%;
  max-height: 92%;
  width: auto;
  height: auto;
  transform-origin: center center;
  will-change: transform;
  -webkit-user-drag: none;
}
.image-viewer-image.is-animated { transition: transform .28s cubic-bezier(.2, .8, .2, 1) }
.image-viewer-close,
.image-viewer-nav {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, .14);
  color: #fff;
  cursor: pointer;
  font: inherit;
  line-height: 1;
  transition: background .2s;
}
.image-viewer-close:hover,
.image-viewer-nav:hover { background: rgba(255, 255, 255, .28) }
.image-viewer-close {
  top: 16px;
  right: 16px;
  width: 40px;
  height: 40px;
  font-size: 18px;
}
.image-viewer-nav {
  top: 50%;
  width: 44px;
  height: 44px;
  margin-top: -22px;
  font-size: 28px;
  padding-bottom: 4px;
}
.image-viewer-nav.is-prev { left: 14px }
.image-viewer-nav.is-next { right: 14px }
.image-viewer-counter {
  position: absolute;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, .8);
  font-size: 14px;
  letter-spacing: 1px;
}
.image-viewer-tip {
  position: absolute;
  left: 0;
  right: 0;
  bottom: max(18px, env(safe-area-inset-bottom));
  text-align: center;
  color: rgba(255, 255, 255, .55);
  font-size: 13px;
  pointer-events: none;
}
@media (max-width: 720px) {
  .image-viewer-tip { display: none }
  .image-viewer-nav { width: 38px; height: 38px; margin-top: -19px; font-size: 24px }
}
</style>
