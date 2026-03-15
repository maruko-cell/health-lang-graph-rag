/** 后端 API 基础地址，优先使用 env */
const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN

/**
 * 上传图片到后端 OSS（/upload/image/oss），返回可公网访问的完整 URL。
 *
 * 功能描述：
 * 将图片以 multipart/form-data 上传到后端，后端转存至阿里云 OSS，返回完整图片地址。
 *
 * 入参说明：
 * - file：File，浏览器文件对象（图片）。
 *
 * 返回值说明：
 * - Promise<{url: string, filename: string, content_type: string}>：
 *   url 为 OSS 完整访问地址，可直接用于多模态或前端展示。
 *
 * 关键逻辑备注：
 * - FormData 字段名与后端一致（file）；
 * - 为兼容调用方，返回对象同时提供 path（与 url 一致）与 base64_url（留空，以 url 为准）。
 */
export async function uploadImage(file) {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}/upload/image/oss`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body.detail || body.message || ''
    } catch {
      detail = await res.text().catch(() => '') || ''
    }
    const msg = detail ? `图片上传失败：${detail}` : `图片上传失败：${res.status} ${res.statusText}`
    throw new Error(msg)
  }

  const data = await res.json()
  /** 展示用地址优先 url，兼容旧逻辑保留 path / base64_url */
  const imageUrl = data.url || data.base64_url || null
  return {
    url: data.url,
    path: data.path ?? data.url,
    base64_url: data.base64_url ?? data.url,
    imageUrl,
    filename: data.filename,
    content_type: data.content_type
  }
}

