/**
 * 当前用户、会话列表、聊天历史与删除会话的 API 封装。
 */

const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN

/**
 * 获取当前用户 id（占位，后续从登录态解析）。
 * @returns {Promise<{ user_id: string }>}
 */
export async function getCurrentUser() {
  const res = await fetch(`${API_BASE}/user/current`)
  if (!res.ok) throw new Error('获取当前用户失败')
  return res.json()
}

/**
 * 按 user_id 查询会话列表，按最后活动时间倒序。
 * @param {string} [userId]
 * @returns {Promise<Array<{ session_id: string, title?: string, last_activity_ts?: number }>>}
 */
export async function getSessions(userId) {
  const params = new URLSearchParams()
  if (userId) params.set('user_id', userId)
  const url = `${API_BASE}/memory/sessions${params.toString() ? `?${params}` : ''}`
  const res = await fetch(url)
  if (!res.ok) throw new Error('获取会话列表失败')
  return res.json()
}

/**
 * 按 user_id + session_id 查询该会话全量聊天记录。
 * @param {string} [userId]
 * @param {string} sessionId
 * @returns {Promise<Array<{ role: string, content: string, ts?: number }>>}
 */
export async function getChatHistory(userId, sessionId) {
  const params = new URLSearchParams({ session_id: sessionId })
  if (userId) params.set('user_id', userId)
  const res = await fetch(`${API_BASE}/chat/history?${params}`)
  if (!res.ok) throw new Error('获取聊天记录失败')
  return res.json()
}

/**
 * 按 user_id + session_id 删除该会话在服务端的数据。
 * @param {string} [userId]
 * @param {string} sessionId
 * @returns {Promise<{ ok: boolean }>}
 */
export async function deleteChatSession(userId, sessionId) {
  const params = new URLSearchParams({ session_id: sessionId })
  if (userId) params.set('user_id', userId)
  const res = await fetch(`${API_BASE}/chat/sessions?${params}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('删除会话失败')
  return res.json()
}
