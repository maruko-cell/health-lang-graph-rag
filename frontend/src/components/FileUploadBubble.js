import { useCallback, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { Upload, Button, message } from 'antd'
import { UploadOutlined, CloseOutlined } from '@ant-design/icons'
import './FileUploadBubble.scss'

/**
 * 通用文件上传气泡组件（基于 Ant Design Upload）。
 *
 * 功能描述：
 * 提供右下角气泡形式的文件选择与上传 UI，通过传入的上传函数与校验规则支持图片、文档等各类文件上传，
 * 上传成功后通过回调向调用方透传结果，样式统一可复用。
 *
 * 入参说明：
 * - open：boolean，气泡是否显示；
 * - onClose：() => void，关闭气泡回调；
 * - title：string，气泡标题文案；
 * - uploadFn：(file: File) => Promise<any>，实际上传函数（如 uploadImage、uploadKbFile）；
 * - onUploaded：(result: any) => void，上传成功回调；
 * - accept：string，可选，input accept 属性，如 "image/*" 或 ".pdf,.doc,.md"；
 * - allowedMimePrefixes：string[]，可选，MIME 类型前缀白名单，如 ['image/']，用于 beforeUpload 校验；
 * - buttonText：string，可选，上传按钮文案，默认「选择文件」；
 * - successMessage：string，可选，上传成功时的 message 文案，默认「上传成功」；
 * - rejectMessage：string，可选，文件类型不合法时的提示，默认「文件类型不支持」。
 * - closeOnUploaded：boolean，可选，上传成功后是否自动关闭气泡，默认 true；
 * - placement：'bottom-right' | 'top-left'，可选，气泡定位角落，默认 'bottom-right'。
 *
 * 返回值说明：
 * - JSX.Element：通过 createPortal 挂载到 body 的气泡节点或 null。
 *
 * 关键逻辑备注：
 * - 使用 customRequest 接管 Upload，内部调用 uploadFn；beforeUpload 根据 allowedMimePrefixes 校验；
 * - 成功：message.success + onUploaded，是否关闭由 closeOnUploaded 控制；失败：message.error + onError。
 */
const FileUploadBubble = ({
  open,
  onClose,
  title,
  uploadFn,
  onUploaded,
  body = null,
  accept,
  allowedMimePrefixes = [],
  buttonText = '选择文件',
  successMessage = '上传成功',
  rejectMessage = '文件类型不支持',
  uploadErrorMessage = '上传失败',
  closeOnUploaded = true,
  placement = 'bottom-right'
}) => {
  const [uploading, setUploading] = useState(false)

  /**
   * 上传前按 MIME 类型前缀白名单校验。
   *
   * 功能描述：
   * 仅当 file.type 匹配 allowedMimePrefixes 中某一前缀时允许上传，避免无效请求。
   *
   * 入参说明：
   * - file：File，用户选择的本地文件对象。
   *
   * 返回值说明：
   * - boolean | typeof Upload.LIST_IGNORE：是否允许继续上传。
   *
   * 关键逻辑备注：
   * - allowedMimePrefixes 为空时不校验；否则要求 file.type 以某一前缀开头。
   */
  const beforeUpload = useCallback(
    (file) => {
      if (!allowedMimePrefixes.length) return true
      const ok = allowedMimePrefixes.some(
        (prefix) => file.type && file.type.startsWith(prefix)
      )
      if (!ok) {
        message.error(rejectMessage)
        return Upload.LIST_IGNORE
      }
      return true
    },
    [allowedMimePrefixes, rejectMessage]
  )

  /**
   * 接管 Upload 的上传流程，调用外部 uploadFn 并在成功后回调、关闭气泡。
   *
   * 功能描述：
   * customRequest 内执行 uploadFn(file)，成功则提示、onUploaded、onClose，失败则提示并 onError。
   *
   * 入参说明：
   * - options：{ file: File, onSuccess: (result) => void, onError: (err) => void }。
   *
   * 返回值说明：
   * - 无返回值。
   */
  const customRequest = useCallback(
    async ({ file, onSuccess, onError }) => {
      try {
        setUploading(true)
        const result = await uploadFn(file)
        onSuccess?.(result)
        message.success(successMessage)
        onUploaded?.(result)
        if (closeOnUploaded) {
          onClose?.()
        }
      } catch (e) {
        console.error(e)
        message.error(uploadErrorMessage)
        onError?.(e)
      } finally {
        setUploading(false)
      }
    },
    [uploadFn, onClose, onUploaded, successMessage, uploadErrorMessage, closeOnUploaded]
  )

  const uploadProps = useMemo(
    () => ({
      name: 'file',
      multiple: false,
      maxCount: 1,
      showUploadList: false,
      accept: accept || undefined,
      beforeUpload,
      customRequest
    }),
    [accept, beforeUpload, customRequest]
  )

  const bubbleClassName = useMemo(
    () => `file-upload-bubble${open ? ' file-upload-bubble--open' : ''}`,
    [open]
  )

  /**
   * 根据 placement 生成 overlay 的 className。
   *
   * 功能描述：
   * 将定位枚举（如 bottom-right / top-left）映射到样式修饰类，复用同一套组件结构实现不同角落展示。
   *
   * 入参说明：
   * - 无入参，依赖 props.placement。
   *
   * 返回值说明：
   * - string：overlay 的 className。
   */
  const overlayClassName = useMemo(() => {
    if (placement === 'top-left') return 'file-upload-bubble-overlay file-upload-bubble-overlay--tl'
    return 'file-upload-bubble-overlay'
  }, [placement])

  /**
   * 使用 React Portal 将气泡挂载至 document.body，避免被父级 overflow 裁剪。
   *
   * 功能描述：
   * 仅当 open 为 true 时渲染 overlay + 气泡，点击 overlay 触发 onClose。
   *
   * 入参说明：
   * - 无入参，依赖组件 props。
   *
   * 返回值说明：
   * - JSX.Element | null：Portal 内容或 null。
   */
  const renderContent = () => {
    if (!open) return null

    return (
      <div
        className={overlayClassName}
        onClick={onClose}
        aria-hidden={!open}
      >
        <div
          className={bubbleClassName}
          onClick={(event) => event.stopPropagation()}
        >
          <div className="file-upload-bubble__header">
            <div className="file-upload-bubble__title">{title}</div>
            <div className="file-upload-bubble__actions">
              <Upload {...uploadProps} className="file-upload-bubble__upload">
                <Button
                  type="primary"
                  icon={<UploadOutlined />}
                  loading={uploading}
                  size="small"
                  className="file-upload-bubble__upload-btn"
                >
                  {buttonText}
                </Button>
              </Upload>
              <Button
                type="text"
                size="small"
                icon={<CloseOutlined />}
                onClick={onClose}
                className="file-upload-bubble__close"
                aria-label="关闭"
              />
            </div>
          </div>

          {body ? <div className="file-upload-bubble__body">{body}</div> : null}
        </div>
      </div>
    )
  }

  return createPortal(renderContent(), document.body)
}

export default FileUploadBubble
