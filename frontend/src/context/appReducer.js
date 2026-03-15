import { ACTION_TYPES } from './actionTypes'

/**
 * 应用全局状态的 reducer，根据 action 类型不可变地更新 state。
 *
 * @param {Object} state - 当前状态
 * @param {Object} action - { type: string, payload?: any }
 * @returns {Object} 新状态（不可变）
 *
 * 关键逻辑：所有分支均返回新对象，不直接修改 state；
 * 消息按会话维度存储在 state.messagesBySession 中，通过 sessionId 定位。
 */
const appReducer = (state, action) => {
  switch (action.type) {
    case ACTION_TYPES.SET_SESSIONS:
      return { ...state, sessions: action.payload }

    case ACTION_TYPES.ADD_SESSION: {
      const session = action.payload
      const messagesBySession = state.messagesBySession || {}

      return {
        ...state,
        sessions: [session, ...(state.sessions || [])],
        // 新增会话时为其初始化消息数组（如已存在则沿用原值，避免覆盖）
        messagesBySession: {
          ...messagesBySession,
          [session.id]: messagesBySession[session.id] || []
        }
      }
    }

    case ACTION_TYPES.DELETE_SESSION: {
      const sessionId = action.payload
      const currentSessions = state.sessions || []
      if (currentSessions.length <= 1) {
        return state
      }

      const nextSessions = currentSessions.filter(
        (session) => session.id !== sessionId
      )

      const nextMessagesBySession = { ...(state.messagesBySession || {}) }
      // 删除会话时同步移除该会话下的消息列表
      delete nextMessagesBySession[sessionId]

      const isDeletingCurrent = state.currentSessionId === sessionId

      return {
        ...state,
        sessions: nextSessions,
        messagesBySession: nextMessagesBySession,
        currentSessionId: isDeletingCurrent
          ? nextSessions[0]?.id || null
          : state.currentSessionId
      }
    }

    case ACTION_TYPES.SET_CURRENT_SESSION_ID:
      return { ...state, currentSessionId: action.payload }

    case ACTION_TYPES.SET_CURRENT_USER_ID:
      return { ...state, currentUserId: action.payload }

    case ACTION_TYPES.SET_PENDING_AGENT_TYPE:
      return { ...state, pendingAgentType: action.payload ?? null }

    case ACTION_TYPES.SET_SESSIONS_LOADED:
      return { ...state, sessionsLoaded: action.payload }

    case ACTION_TYPES.SET_MESSAGES: {
      /** payload 形态：{ sessionId?: string, messages: Array }，未传 sessionId 时默认使用 currentSessionId */
      const { sessionId, messages } = action.payload || {}
      const targetSessionId = sessionId || state.currentSessionId
      if (!targetSessionId) return state

      return {
        ...state,
        messagesBySession: {
          ...(state.messagesBySession || {}),
          [targetSessionId]: messages || []
        }
      }
    }

    case ACTION_TYPES.ADD_MESSAGE: {
      /** payload 形态：{ sessionId?: string, ...msg }，未传 sessionId 时默认使用 currentSessionId */
      const { sessionId, ...msg } = action.payload || {}
      const targetSessionId = sessionId || state.currentSessionId
      if (!targetSessionId) return state

      const prevMessages = (state.messagesBySession || {})[targetSessionId] || []

      /** 根据角色设置默认的思考与最终回答区分字段 */
      const isAssistant = msg.role === 'assistant'
      const baseMessage = {
        ...msg,
        content: msg.content || '',
        imagePath: msg.imagePath || null,
        imageBase64Url: msg.imageBase64Url || null,
        imageUrl: msg.imageUrl ?? msg.imageBase64Url ?? null,
        thinking: msg.thinking || '',
        finalAnswer: msg.finalAnswer || (isAssistant ? '' : msg.content || ''),
        thinkingDone:
          typeof msg.thinkingDone === 'boolean'
            ? msg.thinkingDone
            : !isAssistant,
        answerDone:
          typeof msg.answerDone === 'boolean'
            ? msg.answerDone
            : !isAssistant
      }

      return {
        ...state,
        messagesBySession: {
          ...(state.messagesBySession || {}),
          [targetSessionId]: [...prevMessages, baseMessage]
        }
      }
    }

    case ACTION_TYPES.APPEND_MESSAGE_CONTENT: {
      /** payload 形态：{ messageId: string, chunk: string, sessionId?: string } */
      const { messageId, chunk, sessionId } = action.payload || {}
      const targetSessionId = sessionId || state.currentSessionId
      if (!targetSessionId || !messageId) return state

      const prevMessages = (state.messagesBySession || {})[targetSessionId] || []
      const nextMessages = prevMessages.map((m) =>
        m.id === messageId ? { ...m, content: (m.content || '') + chunk } : m
      )

      return {
        ...state,
        messagesBySession: {
          ...(state.messagesBySession || {}),
          [targetSessionId]: nextMessages
        }
      }
    }

    case ACTION_TYPES.APPEND_MESSAGE_THINKING: {
      /** payload 形态：{ messageId: string, chunk: string, sessionId?: string } */
      const { messageId, chunk, sessionId } = action.payload || {}
      const targetSessionId = sessionId || state.currentSessionId
      if (!targetSessionId || !messageId) return state

      const prevMessages = (state.messagesBySession || {})[targetSessionId] || []
      const nextMessages = prevMessages.map((m) =>
        m.id === messageId
          ? { ...m, thinking: (m.thinking || '') + (chunk || '') }
          : m
      )

      return {
        ...state,
        messagesBySession: {
          ...(state.messagesBySession || {}),
          [targetSessionId]: nextMessages
        }
      }
    }

    case ACTION_TYPES.SET_MESSAGE_THINKING_DONE: {
      /** payload 形态：{ messageId: string, sessionId?: string } */
      const { messageId, sessionId } = action.payload || {}
      const targetSessionId = sessionId || state.currentSessionId
      if (!targetSessionId || !messageId) return state

      const prevMessages = (state.messagesBySession || {})[targetSessionId] || []
      const nextMessages = prevMessages.map((m) =>
        m.id === messageId ? { ...m, thinkingDone: true } : m
      )

      return {
        ...state,
        messagesBySession: {
          ...(state.messagesBySession || {}),
          [targetSessionId]: nextMessages
        }
      }
    }

    case ACTION_TYPES.SET_MESSAGE_THINKING_DURATION: {
      /** payload 形态：{ messageId: string, durationSec: number, sessionId?: string } */
      const { messageId, durationSec, sessionId } = action.payload || {}
      const targetSessionId = sessionId || state.currentSessionId
      if (!targetSessionId || !messageId) return state

      const prevMessages = (state.messagesBySession || {})[targetSessionId] || []
      const nextMessages = prevMessages.map((m) =>
        m.id === messageId
          ? {
              ...m,
              thinkingDurationSec:
                typeof durationSec === 'number' && Number.isFinite(durationSec) && durationSec > 0
                  ? durationSec
                  : m.thinkingDurationSec
            }
          : m
      )

      return {
        ...state,
        messagesBySession: {
          ...(state.messagesBySession || {}),
          [targetSessionId]: nextMessages
        }
      }
    }

    case ACTION_TYPES.APPEND_MESSAGE_FINAL_ANSWER: {
      /** payload 形态：{ messageId: string, chunk: string, sessionId?: string } */
      const { messageId, chunk, sessionId } = action.payload || {}
      const targetSessionId = sessionId || state.currentSessionId
      if (!targetSessionId || !messageId) return state

      const prevMessages = (state.messagesBySession || {})[targetSessionId] || []
      const nextMessages = prevMessages.map((m) =>
        m.id === messageId
          ? {
              ...m,
              finalAnswer: (m.finalAnswer || '') + (chunk || ''),
              // 为兼容旧版 Content 渲染逻辑，同时更新 content 字段
              content: (m.finalAnswer || '') + (chunk || '')
            }
          : m
      )

      return {
        ...state,
        messagesBySession: {
          ...(state.messagesBySession || {}),
          [targetSessionId]: nextMessages
        }
      }
    }

    case ACTION_TYPES.SET_MESSAGE_ANSWER_DONE: {
      /** payload 形态：{ messageId: string, sessionId?: string } */
      const { messageId, sessionId } = action.payload || {}
      const targetSessionId = sessionId || state.currentSessionId
      if (!targetSessionId || !messageId) return state

      const prevMessages = (state.messagesBySession || {})[targetSessionId] || []
      const nextMessages = prevMessages.map((m) =>
        m.id === messageId ? { ...m, answerDone: true } : m
      )

      return {
        ...state,
        messagesBySession: {
          ...(state.messagesBySession || {}),
          [targetSessionId]: nextMessages
        }
      }
    }

    case ACTION_TYPES.SET_MESSAGES_LOADING:
      return { ...state, messagesLoading: action.payload }

    case ACTION_TYPES.SET_CURRENT_IMAGE: {
      const { path, base64Url, imageUrl } = action.payload || {}
      const displayUrl = imageUrl ?? base64Url ?? null
      return {
        ...state,
        currentImagePath: path || null,
        currentImageBase64Url: base64Url || null,
        currentImageUrl: displayUrl
      }
    }

    case ACTION_TYPES.SET_INPUT_VALUE:
      return { ...state, inputValue: action.payload }

    default:
      return state
  }
}

export default appReducer
