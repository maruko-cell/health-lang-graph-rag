import { useEffect, useRef } from 'react'
import Header from './components/Header'
import Content from './components/Content'
import Footer from './components/Footer'
import { useAppContext } from './context'
import { ACTION_TYPES } from './context/actionTypes'
import { getCurrentUser, getSessions, getChatHistory } from './api/sessions'
import './App.scss'

/**
 * 生成唯一 id，用于从服务端历史还原的消息。
 */
function createMessageId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

/**
 * 应用根组件，负责组合头部、内容区和底部输入区域；
 * 挂载时根据 currentUserId 拉取会话列表与当前会话历史并恢复 state，实现刷新不丢数据。
 */
const App = () => {
  const { state, dispatch } = useAppContext()
  const { sessionsLoaded, currentUserId, currentSessionId } = state || {}
  const bootstrapped = useRef(false)

  useEffect(() => {
    if (bootstrapped.current || sessionsLoaded) return
    bootstrapped.current = true

    const load = async () => {
      try {
        const userRes = await getCurrentUser()
        const userId = userRes?.user_id || ''
        if (userId) dispatch({ type: ACTION_TYPES.SET_CURRENT_USER_ID, payload: userId })

        const sessionsRes = await getSessions(userId)
        const sessions = Array.isArray(sessionsRes) ? sessionsRes : []
        const mappedSessions = sessions.map((s) => ({
          id: s.session_id,
          title: s.title || '新会话'
        }))

        if (mappedSessions.length > 0) {
          dispatch({ type: ACTION_TYPES.SET_SESSIONS, payload: mappedSessions })
          const firstId = mappedSessions[0].id
          dispatch({ type: ACTION_TYPES.SET_CURRENT_SESSION_ID, payload: firstId })

          const historyRes = await getChatHistory(userId, firstId)
          const history = Array.isArray(historyRes) ? historyRes : []
          const messages = history.map((h, i) => ({
            id: createMessageId(),
            role: h.role || 'user',
            content: h.content || '',
            thinking: '',
            finalAnswer: h.role === 'assistant' ? h.content || '' : '',
            thinkingDone: true,
            answerDone: true
          }))
          dispatch({
            type: ACTION_TYPES.SET_MESSAGES,
            payload: { sessionId: firstId, messages }
          })
        }
        dispatch({ type: ACTION_TYPES.SET_SESSIONS_LOADED, payload: true })
      } catch (e) {
        dispatch({ type: ACTION_TYPES.SET_SESSIONS_LOADED, payload: true })
      }
    }

    load()
  }, [dispatch, sessionsLoaded])

  return (
    <div className="app">
      <Header />
      <Content />
      <Footer />
    </div>
  )
}

export default App
