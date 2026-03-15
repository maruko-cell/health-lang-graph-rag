import React, { createContext, useReducer } from 'react'
import appReducer from './appReducer'

/** 全局状态初始值：当前用户、会话列表、当前会话 id、按会话分组的消息、加载态、多模态图片上下文 */
const defaultSessionId = 'default-session-1'

const initialState = {
  /** 当前用户 id，占位从 /user/current 读取，后续登录后从 token 解析 */
  currentUserId: null,
  /** 是否已从服务端加载过会话列表与历史（用于刷新恢复） */
  sessionsLoaded: false,
  sessions: [
    {
      id: defaultSessionId,
      title: '新会话 1'
    }
  ],
  currentSessionId: defaultSessionId,
  /** 按会话维度存储消息列表，键为 sessionId，值为该会话的消息数组 */
  messagesBySession: {
    [defaultSessionId]: []
  },
  messagesLoading: false,
  currentImagePath: null,
  currentImageBase64Url: null,
  /** 展示用图片地址（优先 URL，兼容 base64 Data URL） */
  currentImageUrl: null,
  inputValue: '',
  /** 点击 Self 等快捷按钮时设为对应 type（如 'selfie'），发送时带给后端强制路由，发送后清除 */
  pendingAgentType: null
}

/**
 * 全局状态 Context，默认值为 initialState 与空 dispatch，仅作类型/兜底用。
 * 实际值由 AppProvider 注入。
 */
export const AppContext = createContext({
  state: initialState,
  dispatch: () => {}
})

/**
 * 全局状态 Provider，使用 useReducer 驱动 state，并将 state 与 dispatch 注入 Context。
 *
 * @param {Object} props - React 组件 props
 * @param {React.ReactNode} props.children - 子节点
 * @returns {JSX.Element}
 */
export const AppProvider = ({ children }) => {
  const [state, dispatch] = useReducer(appReducer, initialState)

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  )
}
