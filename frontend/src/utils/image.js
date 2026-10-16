// 上传前用 Canvas 压缩：长边缩放到 maxSide、JPEG 质量 quality。
// 手机相机原图往往有几 MB 到十几 MB，直接上传慢且容易超限；iPhone 的 HEIC 也
// 不在后端白名单内，这里统一转成 JPEG。解码失败时回退原始文件交由后端校验。
//
// maxSide 必须与后端 settings.default_max_side 保持一致（见 config.py）。这个值直接
// 影响识别精度：examples/ 的实测样本长边都是 1920，缩到 1600 会让 MAE 从 1.29 退化到
// 1.64、完全正确的张数从 7/14 掉到 6/14 —— 精度损失就是这次下采样造成的。2200 保证
// 常见的 1080x1920 手机竖拍图完全不缩放，同时给 iPhone 原图（4032 长边）留出余量。
const MAX_SIDE = 2200

const loadImage = file => new Promise((resolve, reject) => {
  const url = URL.createObjectURL(file)
  const img = new Image()
  img.onload = () => { URL.revokeObjectURL(url); resolve(img) }
  img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('图片解码失败')) }
  img.src = url
})

export async function compressImage(file, { maxSide = MAX_SIDE, quality = 0.8 } = {}) {
  if (!file || !file.type || !file.type.startsWith('image/') || file.type === 'image/gif') return file
  try {
    let source
    if (typeof createImageBitmap === 'function') {
      source = await createImageBitmap(file, { imageOrientation: 'from-image' })
    } else {
      source = await loadImage(file)
    }
    const width = source.width || source.naturalWidth
    const height = source.height || source.naturalHeight
    const scale = Math.min(1, maxSide / Math.max(width, height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(width * scale))
    canvas.height = Math.max(1, Math.round(height * scale))
    canvas.getContext('2d').drawImage(source, 0, 0, canvas.width, canvas.height)
    if (source.close) source.close()
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', quality))
    return blob || file
  } catch {
    return file
  }
}
