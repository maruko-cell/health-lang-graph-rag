import { useEffect, useRef, useState } from 'react'
import { useAppContext } from '../context'
import { useModalRef } from '../hooks/useModalRef'
import ImagePreviewModal from './ImagePreviewModal'
import MessageContentWithImages from './MessageContentWithImages'

/** 角色头像与展示名配置映射，用于根据消息角色渲染不同头像与名称。 */
const AVATAR_MAP = {
  user: {
    name: '我',
    avatarUrl: ''
  },
  assistant: {
    name: '健康助手',
    avatarUrl: ''
  }
}

/**
 * 聊天内容展示组件，从全局状态按当前会话 id 读取对应消息并以对话形式展示用户与助手的气泡和头像。
 *
 * 功能描述：订阅全局 state.messages，将用户与助手消息渲染为左右对齐的聊天气泡，
 * 每条消息展示对应头像与名称，并在无消息时提示用户开始提问。
 * 入参说明：无入参。
 * 返回值说明：返回包含对话列表的 React JSX 节点。
 * 关键逻辑备注：根据 role 区分左右布局与样式，内容会随流式追加自动更新。
 *
 * @returns {JSX.Element}
 */
const Content = () => {
  const { state } = useAppContext()
  const { currentSessionId, messagesBySession } = state
  /** 当前会话下的消息列表，未选择会话或不存在时回退为空数组 */
  const messages = currentSessionId
    ? messagesBySession?.[currentSessionId] || []
    : []
  const bottomRef = useRef(null)
  const [, setTick] = useState(0)
  const { modalRef: imagePreviewRef, open: openImagePreview } = useModalRef()
  const [thinkingOpenById, setThinkingOpenById] = useState({})

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'end'
      })
    }
  }, [messages])

  useEffect(() => {
    if (!messages || messages.length === 0) {
      return undefined
    }

    const lastMessage = messages[messages.length - 1]
    const shouldTick =
      lastMessage &&
      lastMessage.role === 'assistant' &&
      !lastMessage.thinkingDone &&
      lastMessage.startedAt

    if (!shouldTick) {
      return undefined
    }

    const timerId = setInterval(() => {
      setTick((prev) => prev + 1)
    }, 1000)

    return () => {
      clearInterval(timerId)
    }
  }, [messages])

  /**
   * 切换指定助手消息的“思考过程”折叠状态。
   *
   * 功能描述：仅在用户点击折叠按钮时切换该条消息的思考面板展开/收起状态，避免误触导致内容跳动。
   * 入参说明：
   * - messageId：string，消息唯一 id；
   * 返回值说明：无返回值。
   * 关键逻辑备注：采用按消息 id 存储的局部状态；思考中（thinkingDone=false）时不允许收起。
   *
   * @param {string} messageId
   * @returns {void}
   */
  const toggleThinkingOpen = (messageId) => {
    if (!messageId) return
    setThinkingOpenById((prev) => ({
      ...prev,
      [messageId]: !prev?.[messageId]
    }))
  }

  return (
    <main className="app-content">
      <section className="content-section chat-content">
        {(!messages || messages.length === 0) && (
          <div className="chat-content__empty">开始提问，健康助手会在这里回复你～</div>
        )}

        {messages &&
          messages.map((msg) => {
            const meta = AVATAR_MAP[msg.role] || {}
            const isUser = msg.role === 'user'
            const hasThinking = !!(msg.thinking && String(msg.thinking).trim())
            const hasFinalAnswer = !!(msg.finalAnswer || msg.content)
            const thinkingInProgress = !msg.thinkingDone
            const thinkingSeconds =
              msg.thinkingDurationSec && !thinkingInProgress
                ? msg.thinkingDurationSec
                : msg.startedAt
                  ? Math.max(1, Math.round((Date.now() - msg.startedAt) / 1000))
                  : null
            /** 思考面板默认展开，仅用户手动折叠后才收起；思考中时强制展开 */
            const thinkingOpen = thinkingInProgress ? true : (thinkingOpenById?.[msg.id] ?? true)

            return (
              <div
                key={msg.id}
                className={`chat-message chat-message--${isUser ? 'user' : 'assistant'}`}
              >
                {!isUser && (
                  <div className="chat-message__avatar">
                    {meta.avatarUrl ? (
                      <img src={meta.avatarUrl} alt={meta.name || msg.role} />
                    ) : (
                      <span className="chat-message__avatar-fallback">
                        {meta.name?.[0] || '助'}
                      </span>
                    )}
                  </div>
                )}

                <div className="chat-message__bubble-wrapper">
                  <div className="chat-message__name">{meta.name || msg.role}</div>
                  <div className="chat-message__bubble">
                    {(msg.imageUrl || msg.imageBase64Url) && (
                      <div className="chat-message__image-wrapper">
                        <img
                          src={msg.imageUrl || msg.imageBase64Url}
                          alt="用户上传图片"
                          className="chat-message__image"
                          role="button"
                          tabIndex={0}
                          onClick={() =>
                            openImagePreview({
                              src: msg.imageUrl || msg.imageBase64Url,
                              alt: '用户上传图片'
                            })
                          }
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              openImagePreview({
                                src: msg.imageUrl || msg.imageBase64Url,
                                alt: '用户上传图片'
                              })
                            }
                          }}
                        />
                      </div>
                    )}
                    {/* 助手消息：优先展示思考过程（在上方），再展示最终回答内容；无内容时若正在加载也展示占位（边算边推） */}
                    {!isUser &&
                      (msg.thinking || msg.finalAnswer || msg.content || (msg.startedAt && !msg.thinkingDone)) && (
                      <div className="chat-message__assistant-content">
                        <details
                          className="chat-message__thinking-panel"
                          open={thinkingOpen}
                        >
                          <summary
                            className="chat-message__thinking-summary"
                            onClick={(e) => {
                              /**
                               * 禁用 summary 默认的 details 折叠行为。
                               *
                               * 功能描述：阻止点击 summary 任意区域触发原生折叠/展开，仅允许点击右侧折叠按钮切换思考面板。
                               * 入参说明：
                               * - e：MouseEvent，点击事件对象；
                               * 返回值说明：无返回值。
                               * 关键逻辑备注：调用 preventDefault + stopPropagation，既关闭原生折叠，又避免事件冒泡到外层。
                               *
                               * @returns {void}
                               */
                              e.preventDefault()
                              e.stopPropagation()
                            }}
                          >
                            <span className="chat-message__thinking-main">
                              <span
                                className={`chat-message__thinking-status chat-message__thinking-status--${thinkingInProgress ? 'active' : 'done'
                                  }`}
                              >
                                {thinkingInProgress ? '思考中' : '已思考'}
                              </span>
                              {thinkingSeconds && (
                                <span className="chat-message__thinking-duration">
                                  {thinkingInProgress
                                    ? `已用 ${thinkingSeconds} 秒`
                                    : `用时 ${thinkingSeconds} 秒`}
                                </span>
                              )}
                            </span>
                            <span className="chat-message__thinking-actions">
                              {thinkingInProgress && (
                                <span className="chat-message__thinking-dots" aria-hidden="true">
                                  <span className="dot" />
                                  <span className="dot" />
                                  <span className="dot" />
                                </span>
                              )}
                              <button
                                type="button"
                                className="chat-message__thinking-toggle"
                                aria-label={thinkingOpen ? '收起思考过程' : '展开思考过程'}
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  if (thinkingInProgress) return
                                  toggleThinkingOpen(msg.id)
                                }}
                                disabled={thinkingInProgress}
                              >
                                <span className="chat-message__thinking-toggle-icon" aria-hidden="true">
                                  ▾
                                </span>
                              </button>
                            </span>
                          </summary>
                          <div className="chat-message__thinking-body">
                            {hasThinking
                              ? msg.thinking
                              : '正在结合知识图谱检索并生成回答…'}
                          </div>
                        </details>
                        {hasFinalAnswer ? (
                          <div className="chat-message__answer">
                            <MessageContentWithImages
                              content={msg.finalAnswer || msg.content}
                              onPreviewImage={openImagePreview}
                            />
                          </div>
                        ) : null}
                      </div>
                    )}
                    {/* 用户消息或兼容旧数据的助手消息 */}
                    {(isUser || (!msg.thinking && !msg.finalAnswer)) &&
                      msg.content && <div>{msg.content}</div>}
                  </div>
                </div>

                {isUser && (
                  <div className="chat-message__avatar chat-message__avatar--right">
                    {meta.avatarUrl ? (
                      <img src={meta.avatarUrl} alt={meta.name || msg.role} />
                    ) : (
                      <span className="chat-message__avatar-fallback">
                        {meta.name?.[0] || '我'}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        <div ref={bottomRef} className="chat-content__bottom-anchor" />
      </section>
      <ImagePreviewModal ref={imagePreviewRef} />
    </main>
  )
}

export default Content

