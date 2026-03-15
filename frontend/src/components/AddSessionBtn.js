import { useCallback, useState } from 'react'
import SessionListBubble from './SessionListBubble'
import { useAppContext } from '../context'
import { ACTION_TYPES } from '../context/actionTypes'
import { getChatHistory, deleteChatSession } from '../api/sessions'

/**
 * 新建会话按钮与会话列表入口组件。
 *
 * 功能描述：
 * 提供「新建会话」与「会话列表」两个按钮：
 * - 点击「新建会话」：在全局 sessions 中新增一条会话并将其设为当前会话；
 * - 点击「会话列表」：在页面左上角弹出会话列表气泡，仅展示并管理已有会话（切换/删除）。
 *
 * 入参说明：
 * - 无入参。
 *
 * 返回值说明：
 * - JSX.Element：返回一个包含两个按钮及会话列表气泡的复合组件。
 */
const AddSessionBtn = () => {
  const { state, dispatch } = useAppContext()
  const { sessions = [], currentSessionId } = state || {}
  const [listOpen, setListOpen] = useState(false)

  /**
   * 生成新会话的唯一 id。
   *
   * 入参说明：
   * - 无入参。
   *
   * 返回值说明：
   * - string：新会话 id。
   */
  const createSessionId = useCallback(() => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID()
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`
  }, [])

  /**
   * 新建会话。
   *
   * 功能描述：
   * 创建一条新的会话记录插入到全局 sessions 列表头部，并将其设为当前会话。
   *
   * 入参说明：
   * - 无入参。
   *
   * 返回值说明：
   * - 无返回值。
   */
  const handleAddSession = useCallback(() => {
    const id = createSessionId()
    const index = (sessions?.length || 0) + 1
    const session = {
      id,
      title: `新会话 ${index}`
    }

    dispatch({ type: ACTION_TYPES.ADD_SESSION, payload: session })
    dispatch({ type: ACTION_TYPES.SET_CURRENT_SESSION_ID, payload: id })
  }, [createSessionId, dispatch, sessions])

  /**
   * 删除会话：先调服务端删除该会话数据，再从本地 state 移除。
   */
  const handleDeleteSession = useCallback(
    async (sessionId) => {
      const userId = state?.currentUserId
      try {
        await deleteChatSession(userId, sessionId)
      } catch (e) {
      }
      dispatch({ type: ACTION_TYPES.DELETE_SESSION, payload: sessionId })
    },
    [dispatch, state?.currentUserId]
  )

  /**
   * 切换当前会话；若该会话尚无本地消息则从服务端拉取历史并写入 state。
   */
  const handleSelectSession = useCallback(
    async (sessionId) => {
      dispatch({ type: ACTION_TYPES.SET_CURRENT_SESSION_ID, payload: sessionId })
      const messages = state?.messagesBySession?.[sessionId]
      if (messages != null && messages.length > 0) return
      const userId = state?.currentUserId
      try {
        const history = await getChatHistory(userId, sessionId)
        const list = Array.isArray(history) ? history : []
        const mapped = list.map((h, i) => ({
          id: `hist-${sessionId}-${i}-${h.ts ?? i}`,
          role: h.role || 'user',
          content: h.content || '',
          thinking: '',
          finalAnswer: h.role === 'assistant' ? h.content || '' : '',
          thinkingDone: true,
          answerDone: true
        }))
        dispatch({ type: ACTION_TYPES.SET_MESSAGES, payload: { sessionId, messages: mapped } })
      } catch (e) {
      }
    },
    [dispatch, state?.currentUserId, state?.messagesBySession]
  )

  return (
    <>
      <button
        className="add-session-btn"
        type="button"
        onClick={handleAddSession}
        aria-label="新建会话"
      >
        新建会话
      </button>
      <button
        className="add-session-btn"
        type="button"
        onClick={() => setListOpen(true)}
        aria-label="会话列表"
      >
        会话列表
      </button>

      <SessionListBubble
        open={listOpen}
        onClose={() => setListOpen(false)}
        title="会话列表"
        sessions={sessions}
        activeSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
      />
    </>
  )
}

export default AddSessionBtn

