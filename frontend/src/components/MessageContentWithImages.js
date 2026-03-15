import { useMemo } from 'react'
import './MessageContentWithImages.scss'

/**
 * 将内容按「图片 URL」与「普通文本」拆分为片段，用于统一渲染逻辑。
 *
 * 功能描述：
 * 使用正则匹配 content 中的图片 URL（http(s) 且后缀为 png/jpg/jpeg/webp/gif，可带查询参数），
 * 返回 { type: 'text'|'image', value: string } 数组。
 *
 * 入参说明：
 * - content：string，原始文本内容。
 *
 * 返回值说明：
 * - Array<{ type: 'text'|'image', value: string }>，按出现顺序的片段列表。
 *
 * @param {string} content
 * @returns {{ type: string, value: string }[]}
 */
function parseContentSegments(content) {
  if (!content || typeof content !== 'string') {
    return [{ type: 'text', value: '' }]
  }
  const regex = /https?:\/\/[^\s<>"]+\.(?:png|jpg|jpeg|webp|gif)(?:\?[^\s<>"]*)?/gi
  const segments = []
  let lastEnd = 0
  let match
  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastEnd) {
      segments.push({ type: 'text', value: content.slice(lastEnd, match.index) })
    }
    segments.push({ type: 'image', value: match[0] })
    lastEnd = regex.lastIndex
  }
  if (lastEnd < content.length) {
    segments.push({ type: 'text', value: content.slice(lastEnd) })
  }
  if (segments.length === 0) {
    segments.push({ type: 'text', value: content })
  }
  return segments
}

/**
 * 带图片展示的消息内容组件：文本中的图片 URL 渲染为可点击缩略图，点击后通过回调打开预览弹窗。
 *
 * 功能描述：
 * 解析 content 中的图片 URL，将 URL 段渲染为缩略图，非 URL 段按原文展示（保留换行）；
 * 点击缩略图时调用 onPreviewImage({ src, alt })。
 *
 * 入参说明：
 * - content：string，消息正文（可能包含一个或多个图片 URL）。
 * - onPreviewImage：(payload: { src: string, alt?: string }) => void，点击图片时的回调，用于打开预览弹窗。
 *
 * 返回值说明：
 * - JSX.Element，包含文本与内联图片的片段列表。
 */
const MessageContentWithImages = ({ content, onPreviewImage }) => {
  const segments = useMemo(() => parseContentSegments(content || ''), [content])

  if (!segments.length) {
    return <span className="message-content-with-images" />
  }

  return (
    <span className="message-content-with-images">
      {segments.map((seg, index) => {
        if (seg.type === 'text') {
          return (
            <span key={`t-${index}`} className="message-content-with-images__text">
              {seg.value}
            </span>
          )
        }
        return (
          <span
            key={`i-${index}`}
            className="message-content-with-images__inline-image-wrapper"
            role="button"
            tabIndex={0}
            onClick={() => onPreviewImage?.({ src: seg.value, alt: '预览图片' })}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onPreviewImage?.({ src: seg.value, alt: '预览图片' })
              }
            }}
          >
            <img
              src={seg.value}
              alt="预览图片"
              className="message-content-with-images__inline-image"
            />
          </span>
        )
      })}
    </span>
  )
}

export default MessageContentWithImages
