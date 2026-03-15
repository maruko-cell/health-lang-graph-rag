/**
 * 聊天输入组件，包含附件按钮、文本输入框和发送按钮。
 * 无入参。
 * @returns {JSX.Element} 返回底部主输入区域组件。
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { chatStreamWithThinking } from '../api/chat_stream'
import { useAppContext } from '../context'
import { ACTION_TYPES } from '../context/actionTypes'

/**
 * 生成功能性唯一消息 ID，优先使用浏览器原生 randomUUID。
 *
 * 功能描述：为消息生成可用于 reducer 定位与追加内容的 id，避免流式追加时找不到目标消息。
 * 入参说明：无入参。
 * 返回值说明：返回 {string} 消息唯一标识。
 * 关键逻辑备注：优先使用 crypto.randomUUID；在不支持的环境下回退到时间戳+随机数方案。
 *
 * @returns {string}
 */
const createMessageId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const ChatInput = () => {
  const { state, dispatch } = useAppContext()
  const [value, setValue] = useState('')
  const abortRef = useRef(null)
  /** 用户主动停止后置为 true，用于在回调中不再 dispatch，避免停止后仍更新 UI */
  const abortedRef = useRef(false)

  const canSend = useMemo(() => {
    return value.trim().length > 0 && !state.messagesLoading
  }, [value, state.messagesLoading])

  /**
   * 发送当前输入内容到后端流式接口，并把用户消息与助手消息写入全局 messages。
   *
   * 功能描述：将输入框内容或外部传入文本作为用户消息插入消息列表，随后创建一条空的助手消息用于承接流式输出，
   * 调用 chatStream 按 chunk 追加到助手消息内容；发送中会设置 messagesLoading 以避免重复触发。
   * 入参说明：
   * - externalText：可选，外部传入的消息文本（例如快捷入口预设问题）；为空时使用当前输入框内容。
   * 返回值说明：无返回值。
   * 关键逻辑备注：使用 AbortController 支持中断上一次未完成的流；异常时会解除 loading，并在控制台输出错误。
   */
  const handleSend = async (externalText) => {
    const text = (typeof externalText === 'string' ? externalText : value).trim()
    if (!text || state.messagesLoading) return

    /** 当前会话 id，用于将消息与流式追加内容绑定到指定会话 */
    const sessionId = state.currentSessionId
    if (!sessionId) {
      return
    }

    abortRef.current?.abort?.()
    const controller = new AbortController()
    abortRef.current = controller
    abortedRef.current = false

    const userId = createMessageId()
    const assistantId = createMessageId()
    const startedAt = Date.now()

    dispatch({
      type: ACTION_TYPES.ADD_MESSAGE,
      payload: {
        sessionId,
        id: userId,
        role: 'user',
        content: text
      }
    })
    dispatch({
      type: ACTION_TYPES.ADD_MESSAGE,
      payload: {
        sessionId,
        id: assistantId,
        role: 'assistant',
        content: '',
        thinking: '',
        finalAnswer: '',
        thinkingDone: false,
        answerDone: false,
        startedAt,
        thinkingDurationSec: null
      }
    })
    dispatch({ type: ACTION_TYPES.SET_MESSAGES_LOADING, payload: true })

    setValue('')
    dispatch({ type: ACTION_TYPES.SET_INPUT_VALUE, payload: '' })
    const agentTypeToSend = state.pendingAgentType || null
    dispatch({ type: ACTION_TYPES.SET_PENDING_AGENT_TYPE, payload: null })

    try {
      await chatStreamWithThinking({
        message: text,
        imagePath: state.currentImagePath,
        imageBase64Url: state.currentImageBase64Url,
        imageUrl: state.currentImageUrl ?? state.currentImageBase64Url,
        userId: state.currentUserId,
        sessionId,
        agentType: agentTypeToSend,
        signal: controller.signal,
        onThinkingDelta: (chunk) => {
          if (abortedRef.current) return
          dispatch({
            type: ACTION_TYPES.APPEND_MESSAGE_THINKING,
            payload: { sessionId, messageId: assistantId, chunk }
          })
        },
        onThinkingDone: () => {
          if (abortedRef.current) return
          const elapsedMs = Date.now() - startedAt
          const durationSec = Math.max(1, Math.round(elapsedMs / 1000))
          dispatch({
            type: ACTION_TYPES.SET_MESSAGE_THINKING_DONE,
            payload: { sessionId, messageId: assistantId }
          })
          dispatch({
            type: ACTION_TYPES.SET_MESSAGE_THINKING_DURATION,
            payload: { sessionId, messageId: assistantId, durationSec }
          })
        },
        onAnswerDelta: (chunk) => {
          if (abortedRef.current) return
          dispatch({
            type: ACTION_TYPES.APPEND_MESSAGE_FINAL_ANSWER,
            payload: { sessionId, messageId: assistantId, chunk }
          })
        },
        onAnswerDone: () => {
          if (abortedRef.current) return
          dispatch({
            type: ACTION_TYPES.SET_MESSAGE_ANSWER_DONE,
            payload: { sessionId, messageId: assistantId }
          })
          dispatch({ type: ACTION_TYPES.SET_MESSAGES_LOADING, payload: false })
        },
        onMeta: () => { },
        onError: (err) => {
          dispatch({ type: ACTION_TYPES.SET_MESSAGES_LOADING, payload: false })
          if (err?.name === 'AbortError') {
            const durationSec = Math.max(1, Math.round((Date.now() - startedAt) / 1000))
            dispatch({
              type: ACTION_TYPES.SET_MESSAGE_THINKING_DONE,
              payload: { sessionId, messageId: assistantId }
            })
            dispatch({
              type: ACTION_TYPES.SET_MESSAGE_THINKING_DURATION,
              payload: { sessionId, messageId: assistantId, durationSec }
            })
            return
          }
          // eslint-disable-next-line no-console
          console.error(err)
        }
      })
    } catch (err) {
      dispatch({ type: ACTION_TYPES.SET_MESSAGES_LOADING, payload: false })
      // eslint-disable-next-line no-console
      console.error(err)
    }
  }

  /**
   * 监听全局输入值变化，支持从快捷入口预填并自动发送消息。
   *
   * 功能描述：当全局 state.inputValue 有内容且当前未在加载中时，将其写入本地输入框，并调用发送逻辑。
   * 入参说明：无入参，依赖全局 state。
   * 返回值说明：无返回值。
   */
  useEffect(() => {
    const preset = (state.inputValue || '').trim()
    if (!preset || state.messagesLoading) return
    setValue(state.inputValue || '')
    // 显式传入 preset，避免依赖异步 setState
    // eslint-disable-next-line react-hooks/exhaustive-deps
    handleSend(preset)
  }, [state.inputValue, state.messagesLoading])

  /**
   * 用户点击停止时中断当前流式请求，并标记已中止以便回调不再更新 UI。
   *
   * 功能描述：设置 abortedRef 后调用 AbortController.abort，使 fetch 与 stream 停止；
   * onError 会收到 AbortError 并仅关闭 loading，不再处理后续接口数据。
   * 入参说明：无入参。
   * 返回值说明：无返回值。
   */
  const handleStop = () => {
    if (!state.messagesLoading) return
    abortedRef.current = true
    abortRef.current?.abort?.()
  }

  /**
   * 处理输入框键盘事件，实现回车发送与输入体验。
   *
   * 功能描述：在输入框内按 Enter 触发发送；按 Shift+Enter 保留默认行为（便于后续扩展多行输入）。
   * 入参说明：event {React.KeyboardEvent<HTMLInputElement>} 键盘事件对象。
   * 返回值说明：无返回值。
   * 关键逻辑备注：发送前会阻止默认提交行为，避免触发浏览器表单提交或换行等副作用。
   *
   * @param {import('react').KeyboardEvent<HTMLInputElement>} event
   */
  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (state.messagesLoading) return
      handleSend()
    }
  }

  useEffect(() => {
    return () => abortRef.current?.abort?.()
  }, [])

  return (
    <div className="chat-input" role="group" aria-label="发送消息">
      <div className="chat-input__field-wrapper">
      <input
        className="chat-input__field"
        type="text"
        placeholder="发送消息或输入「/」选择技能"
        aria-label="消息内容"
        autoComplete="off"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={state.messagesLoading}
      />
      </div>
      <button
        type="button"
        className={`chat-input__icon-button chat-input__icon-button--${state.messagesLoading ? 'stop' : 'primary'}`}
        aria-label={state.messagesLoading ? '停止' : '发送'}
        onClick={state.messagesLoading ? handleStop : handleSend}
        disabled={!state.messagesLoading && !canSend}
      >
        {state.messagesLoading ? '停止' : '发送'}
      </button>
    </div>
  )
}

export default ChatInput


