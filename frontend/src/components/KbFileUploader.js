import { useCallback, useEffect, useRef, useState } from 'react'
import { message, Progress } from 'antd'
import FileUploadBubble from './FileUploadBubble'
import { uploadKbFile, getKbFileStatus } from '../api/upload_kb_file'
import './KbFileUploader.scss'

/** 轮询间隔（毫秒） */
const POLL_INTERVAL_MS = 1500

/** 终态：轮询结束 */
const TERMINAL_STATUSES = ['done', 'failed']

/**
 * 将向量化状态映射为 antd Progress 的状态字段。
 *
 * 功能描述：
 * 将后端返回的 status（processing | done | failed）转换为 Progress 需要的状态（active | success | exception），
 * 便于在气泡中统一展示进度条样式。
 *
 * 入参说明：
 * - status：string，后端状态。
 *
 * 返回值说明：
 * - 'active' | 'success' | 'exception'：antd Progress 状态。
 */
const mapProgressStatus = (status) => {
  if (status === 'done') return 'success'
  if (status === 'failed') return 'exception'
  return 'active'
}

/**
 * 知识库文件上传按钮组件。
 *
 * 功能描述：
 * 提供「上传知识库文件」按钮与上传气泡，支持 PDF、Word、文本等格式；
 * 上传成功后根据 file_id 轮询向量化状态 API，在气泡弹窗中展示文件名与进度条，
 * 进度完成或失败后自动关闭气泡并停止轮询，同时给出提示。
 *
 * 入参说明：
 * - 无入参。
 *
 * 返回值说明：
 * - JSX.Element：包含按钮、进度列表与 FileUploadBubble 的复合组件。
 */
const KbFileUploader = () => {
  const [open, setOpen] = useState(false)
  /** 当前气泡正在展示的向量化任务：{ fileId, filename, status, progress } */
  const [activeTask, setActiveTask] = useState(null)
  const pollTimerRef = useRef(null)

  /**
   * 处理知识库上传按钮点击，打开上传气泡。
   *
   * 入参说明：
   * - 无入参。
   *
   * 返回值说明：
   * - 无返回值。
   */
  const handleClick = useCallback(() => {
    setOpen(true)
  }, [])

  /**
   * 停止当前轮询定时器。
   *
   * 功能描述：
   * 在关闭气泡、任务结束或组件卸载时清理定时器，避免内存泄漏与重复轮询。
   *
   * 入参说明：
   * - 无入参。
   *
   * 返回值说明：
   * - 无返回值。
   */
  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  /**
   * 对单个 file_id 启动轮询，直到状态为 done 或 failed，并同步更新气泡进度。
   *
   * 入参说明：
   * - fileId：string，上传返回的文件唯一标识；
   * - filename：string，展示用文件名。
   *
   * 返回值说明：
   * - 无返回值。
   *
   * 关键逻辑备注：
   * - 使用 setInterval 轮询 getKbFileStatus，更新 uploads 中对应项；
   * - 终态时清除定时器并提示成功/失败。
   */
  const startPolling = useCallback(
    (fileId, filename) => {
      stopPolling()

      pollTimerRef.current = setInterval(async () => {
      try {
        const data = await getKbFileStatus(fileId)
        setActiveTask((prev) => ({
          ...(prev || { fileId, filename }),
          fileId,
          filename,
          status: data.status,
          progress: data.progress ?? 0
        }))
        if (TERMINAL_STATUSES.includes(data.status)) {
          stopPolling()
          if (data.status === 'done') {
            message.success(`「${filename}」向量化完成`)
          } else {
            message.error(`「${filename}」向量化失败`)
          }
          setOpen(false)
        }
      } catch (e) {
        console.error('轮询向量化状态失败', e)
        stopPolling()
        setActiveTask((prev) => ({
          ...(prev || { fileId, filename }),
          fileId,
          filename,
          status: 'failed',
          progress: 0
        }))
        message.error(`「${filename}」状态查询失败`)
        setOpen(false)
      }
      }, POLL_INTERVAL_MS)
    },
    [stopPolling]
  )

  /**
   * 上传成功回调：将任务加入列表并开始轮询。
   *
   * 入参说明：
   * - result：object，上传接口返回的 { file_id, filename } 等。
   *
   * 返回值说明：
   * - 无返回值。
   */
  const handleUploaded = useCallback(
    (result) => {
      const fileId = result?.file_id
      const filename = result?.filename ?? '未知文件'
      if (!fileId) return
      setActiveTask({ fileId, filename, status: 'processing', progress: 0 })
      startPolling(fileId, filename)
    },
    [startPolling]
  )

  /**
   * 关闭气泡并停止轮询。
   *
   * 功能描述：
   * 用户手动关闭时，结束轮询并清理当前任务展示状态。
   *
   * 入参说明：
   * - 无入参。
   *
   * 返回值说明：
   * - 无返回值。
   */
  const handleClose = useCallback(() => {
    stopPolling()
    setActiveTask(null)
    setOpen(false)
  }, [stopPolling])

  /** 组件卸载时清除轮询定时器。 */
  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [stopPolling])

  return (
    <>
      <div>
        <button
          className="kb-file-uploader-btn"
          type="button"
          onClick={handleClick}
          aria-label="上传知识库文件"
        >
          上传知识库文件
        </button>
      </div>

      <FileUploadBubble
        open={open}
        onClose={handleClose}
        title="上传知识库文件："
        uploadFn={uploadKbFile}
        onUploaded={handleUploaded}
        placement="top-left"
        accept=".pdf,.doc,.docx,.txt,.md"
        allowedMimePrefixes={[
          'application/pdf',
          'application/msword',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'text/'
        ]}
        buttonText="选择文件"
        successMessage="知识库文件上传成功，正在向量化…"
        rejectMessage="仅支持上传文档或文本文件"
        uploadErrorMessage="知识库文件上传失败"
        closeOnUploaded={false}
        body={
          activeTask ? (
            <div className="kb-vectorize-bubble">
              <div className="kb-vectorize-bubble__filename" title={activeTask.filename}>
                {activeTask.filename}
              </div>
              <Progress
                percent={Math.min(100, Math.max(0, activeTask.progress ?? 0))}
                size="small"
                status={mapProgressStatus(activeTask.status)}
                showInfo
                strokeColor="var(--primary)"
              />
            </div>
          ) : null
        }
      />
    </>
  )
}

export default KbFileUploader

