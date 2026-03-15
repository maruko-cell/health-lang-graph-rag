import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import './ImagePreviewModal.scss'

/**
 * 设置页面 body 的滚动锁定状态。
 *
 * 功能描述：
 * 在弹窗打开时禁止背景页面滚动，避免移动端/长列表滚动穿透；关闭时恢复原有 overflow 样式。
 *
 * 入参说明：
 * - locked：boolean，是否锁定滚动；
 *
 * 返回值说明：无返回值。
 *
 * 关键逻辑备注：
 * - 仅修改 document.body.style.overflow，避免影响到其他布局属性；
 * - 调用方需要确保在组件卸载或关闭时恢复状态。
 *
 * @param {boolean} locked
 * @returns {void}
 */
function setBodyScrollLocked(locked) {
  if (typeof document === 'undefined') return
  if (locked) {
    document.body.style.overflow = 'hidden'
    return
  }
  document.body.style.overflow = ''
}

/**
 * 图片预览弹窗（Portal 挂载到 body，仅点击遮罩关闭）。
 *
 * 功能描述：
 * 用于在聊天消息中点击缩略图后，以全屏弹窗展示原图（或 base64 Data URL），提供清晰预览体验。
 *
 * 入参说明：
 * - ref：通过 ref 暴露 open/close 方法（配合 useModalRef 使用）；
 *
 * 返回值说明：
 * - JSX.Element：Portal 内容或 null。
 *
 * 关键逻辑备注：
 * - open({ src, alt }) 会设置当前图片并展示；
 * - 关闭会清空 src，避免下次打开闪烁旧图；
 * - 移动端交互：不提供关闭按钮，不响应 Esc，仅点击遮罩关闭；
 * - 弹窗打开时锁定 body 滚动以避免滚动穿透。
 */
const ImagePreviewModal = forwardRef((_, ref) => {
  const [open, setOpen] = useState(false)
  const [src, setSrc] = useState(null)
  const [alt, setAlt] = useState('预览图片')

  /**
   * 关闭弹窗并清理当前图片信息。
   *
   * 功能描述：将弹窗状态置为关闭，并清空当前图片 src/alt，避免下次打开短暂展示旧图。
   * 入参说明：无入参。
   * 返回值说明：无返回值。
   *
   * @returns {void}
   */
  const close = useCallback(() => {
    setOpen(false)
    setSrc(null)
    setAlt('预览图片')
  }, [])

  /**
   * 打开弹窗并设置要预览的图片。
   *
   * 功能描述：接收 src/alt 并展示弹窗，用于从消息缩略图跳转到大图预览。
   * 入参说明：
   * - payload：{ src: string, alt?: string }，图片地址（可为 base64 Data URL）与可选 alt 文案。
   * 返回值说明：无返回值。
   *
   * @param {{ src: string, alt?: string }} payload
   * @returns {void}
   */
  const openModal = useCallback((payload) => {
    const nextSrc = payload?.src
    if (!nextSrc) return
    setSrc(nextSrc)
    setAlt(payload?.alt || '预览图片')
    setOpen(true)
  }, [])

  useImperativeHandle(
    ref,
    () => ({
      open: openModal,
      close
    }),
    [openModal, close]
  )

  useEffect(() => {
    if (!open) {
      setBodyScrollLocked(false)
      return undefined
    }

    setBodyScrollLocked(true)
    return () => {
      setBodyScrollLocked(false)
    }
  }, [open, close])

  const content = useMemo(() => {
    if (!open || !src) return null

    return (
      <div
        className="image-preview-modal__overlay"
        role="dialog"
        aria-modal="true"
        aria-label="图片预览"
        onClick={close}
      >
        <div className="image-preview-modal__panel" onClick={(e) => e.stopPropagation()}>
          <img className="image-preview-modal__img" src={src} alt={alt} />
        </div>
      </div>
    )
  }, [open, src, alt, close])

  if (!open) return null
  return createPortal(content, document.body)
})

export default ImagePreviewModal

