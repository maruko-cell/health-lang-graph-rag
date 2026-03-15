import { createPortal } from 'react-dom'
import { Button } from 'antd'
import { CloseOutlined, DeleteOutlined } from '@ant-design/icons'
import './SessionListBubble.scss'

/**
 * 会话列表气泡组件（左上角），参考 FileUploadBubble 的实现方式。
 *
 * 功能描述：
 * 在页面左上角以小气泡形式展示用户当前的所有会话列表，
 * 支持点击某条会话进行切换与删除，不负责新增会话。
 * 会话的新增、删除、当前选中等具体数据更新逻辑由父组件负责，本组件仅负责展示和事件回调。
 *
 * 入参说明：
 * - open：boolean，气泡是否显示；
 * - onClose：() => void，关闭气泡回调；
 * - title：string，气泡标题文案，如「会话列表」；
 * - sessions：Array<{ id: string, title: string }>，会话列表数据；
 * - activeSessionId：string | null，当前选中的会话 id，用于高亮；
 * - onSelectSession：(id: string) => void，点击会话项时触发；
 * - onDeleteSession：(id: string) => void，点击删除按钮时触发。
 *
 * 返回值说明：
 * - JSX.Element：通过 createPortal 挂载到 body 的气泡节点或 null。
 */
const SessionListBubble = ({
  open,
  onClose,
  title,
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession
}) => {
  if (!open) return null

  const bubbleClassName = `session-list-bubble${open ? ' session-list-bubble--open' : ''}`
  const canDeleteSessions = (sessions || []).length > 1

  const content = (
    <div
      className="session-list-bubble-overlay"
      onClick={onClose}
      aria-hidden={!open}
    >
      <div
        className={bubbleClassName}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="session-list-bubble__header">
          <div className="session-list-bubble__title">{title}</div>
          <Button
            type="text"
            size="small"
            icon={<CloseOutlined />}
            onClick={onClose}
            className="session-list-bubble__close"
            aria-label="关闭"
          />
        </div>

        <div className="session-list-bubble__body">
          <ul className="session-list-bubble__list">
            {(sessions || []).map((session) => {
              const isActive = session.id === activeSessionId
              const itemClassName = `session-list-bubble__item${
                isActive ? ' session-list-bubble__item--active' : ''
              }`

              return (
                <li key={session.id} className={itemClassName}>
                  <button
                    type="button"
                    className="session-list-bubble__item-main"
                    onClick={() => onSelectSession?.(session.id)}
                  >
                    <span className="session-list-bubble__item-title">
                      {session.title}
                    </span>
                  </button>
                  {canDeleteSessions && (
                    <Button
                      type="text"
                      size="small"
                      icon={<DeleteOutlined />}
                      onClick={() => onDeleteSession?.(session.id)}
                      className="session-list-bubble__item-delete"
                      aria-label="删除会话"
                    />
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </div>
  )

  return createPortal(content, document.body)
}

export default SessionListBubble

