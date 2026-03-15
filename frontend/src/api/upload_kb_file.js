/** 后端 API 基础地址，优先使用 env */
const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN

/**
 * 获取当前用户 id，用于上传时的 X-User-Id 请求头（与后端 Redis 登记、列表查询一致）。
 * 优先级：环境变量 VITE_USER_ID > localStorage.user_id > 'default_user'。
 */
function getUserId() {
  return (
    (import.meta.env.VITE_USER_ID && String(import.meta.env.VITE_USER_ID).trim()) ||
    (typeof localStorage !== 'undefined' && localStorage.getItem('user_id')) ||
    'default_user'
  )
}

/**
 * 上传知识库文件到后端 /upload/kb-file（OSS 上传）。
 *
 * 功能描述：
 * 将 PDF、Word、文本等知识库文件以 multipart/form-data 方式上传到后端，
 * 后端上传至阿里云 OSS，返回可下载的 url、file_id 及状态，并登记到 Redis。
 *
 * 入参说明：
 * - file：File，浏览器文件对象（知识库文件，如 .pdf、.docx、.txt 等）。
 *
 * 返回值说明：
 * - Promise<{ filename: string, content_type: string, path: string, file_id: string, status: string, url: string }>：
 *   path 与 url 均为 OSS 公网可下载地址；file_id 为内容哈希。
 *
 * 关键逻辑备注：
 * - 请求头 X-User-Id 必填，用于后端按用户存储上传记录；
 * - 上传成功后需轮询 getKbFileStatus(file_id) 获取向量化进度。
 */
export async function uploadKbFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}/upload/kb-file`, {
    method: 'POST',
    headers: {
      'X-User-Id': getUserId()
    },
    body: formData
  })

  if (!res.ok) {
    throw new Error(`知识库文件上传失败：${res.status} ${res.statusText}`)
  }

  return res.json()
}

/**
 * 查询知识库文件向量化任务状态与进度，供轮询使用。
 *
 * 功能描述：
 * 根据上传接口返回的 file_id 请求 GET /upload/kb-file/{file_id}/status，
 * 获取当前状态（processing | done | failed）与进度百分比。
 *
 * 入参说明：
 * - fileId：string，上传接口返回的文件唯一标识（file_id）。
 *
 * 返回值说明：
 * - Promise<{ status: string, progress: number }>：状态与 0–100 的进度；未找到时请求 404。
 *
 * 关键逻辑备注：
 * - 用于 KbFileUploader 在上传成功后轮询，直到 status 为 done 或 failed。
 */
export async function getKbFileStatus(fileId) {
  const res = await fetch(`${API_BASE}/upload/kb-file/${encodeURIComponent(fileId)}/status`)
  if (!res.ok) {
    if (res.status === 404) throw new Error('未找到该文件的向量化状态')
    throw new Error(`查询状态失败：${res.status} ${res.statusText}`)
  }
  return res.json()
}

