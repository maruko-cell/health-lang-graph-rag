import { useEffect, useRef } from 'react'

/**
 * 流式聊天接口封装与通用事件流工具。
 */

/** 后端 API 基础地址，优先使用 env */
const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN

/**
 * 通用事件流消费工具，使用 fetch + ReadableStream 读取 JSONL / 文本事件流。
 *
 * 功能描述：
 * - 发送 POST 请求到给定 url；
 * - 按 chunk 读取响应体，将文本缓冲按行拆分；
 * - 每解析出一行非空 JSON 字符串即调用 onEvent。
 *
 * 入参说明：
 * - url：string，请求地址；
 * - body：any，请求体，将通过 JSON.stringify 发送；
 * - signal：AbortSignal | undefined，可选中断信号；
 * - onEvent：(event: any) => void，每个事件对象的回调；
 * - onError：(error: Error) => void，错误回调；
 * - onDone：() => void，流正常结束回调。
 *
 * 返回值说明：
 * - Promise<void>，无直接返回值，事件通过回调抛出。
 *
 * @param {Object} params - 参数对象
 * @param {string} params.url
 * @param {any} params.body
 * @param {AbortSignal} [params.signal]
 * @param {(event: any) => void} [params.onEvent]
 * @param {(error: Error) => void} [params.onError]
 * @param {() => void} [params.onDone]
 * @returns {Promise<void>}
 */
export async function streamEvents({ url, body, signal, onEvent, onError, onDone }) {
  let buffer = ''

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      signal,
      body: JSON.stringify(body ?? {})
    })

    if (!response.ok) {
      const err = new Error(`事件流请求失败: ${response.status} ${response.statusText}`)
      onError?.(err)
      throw err
    }

    const reader = response.body?.getReader()
    if (!reader) {
      const err = new Error('事件流响应体不可读')
      onError?.(err)
      throw err
    }

    const decoder = new TextDecoder('utf-8')

    while (true) {
      if (signal?.aborted) break
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (signal?.aborted) break
        const trimmed = line.trim()
        if (!trimmed) continue
        try {
          const event = JSON.parse(trimmed)
          if (!signal?.aborted) onEvent?.(event)
        } catch (e) {
        }
      }
    }

    if (!signal?.aborted) onDone?.()
  } catch (error) {
    onError?.(error)
    throw error
  }
}

/**
 * React Hook 形式的通用事件流消费封装。
 *
 * 功能描述：
 * - 在 enabled 为 true 时自动发起事件流请求；
 * - 内部管理 AbortController，组件卸载或依赖变化时自动中断当前流；
 * - 其余行为与 streamEvents 一致，通过回调向外抛出事件。
 *
 * 入参说明：
 * - params：对象，包含以下字段；
 * - params.enabled：boolean，是否立即发起请求；
 * - params.url：string，请求地址；
 * - params.body：any，请求体，将通过 JSON.stringify 发送；
 * - params.onEvent：(event: any) => void，每个事件对象的回调；
 * - params.onError：(error: Error) => void，错误回调；
 * - params.onDone：() => void，流正常结束回调；
 * - params.deps：any[]，可选，触发重新请求的依赖数组（除 enabled 外的额外依赖）。
 *
 * 返回值说明：
 * - { abort: () => void }：提供手动中断当前流的函数。
 *
 * @param {Object} params
 * @returns {{ abort: () => void }}
 */
export function useStreamEvents({
  enabled,
  url,
  body,
  onEvent,
  onError,
  onDone,
  deps = []
}) {
  const abortRef = useRef(null)

  useEffect(() => {
    if (!enabled) return undefined

    const controller = new AbortController()
    abortRef.current = controller

    streamEvents({
      url,
      body,
      signal: controller.signal,
      onEvent,
      onError,
      onDone
    }).catch((error) => {
      // eslint-disable-next-line no-console
      console.error('useStreamEvents 内部流式请求异常', error)
    })

    return () => {
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, url, ...deps])

  /**
   * 手动中断当前事件流。
   *
   * 功能描述：调用时如果存在有效的 AbortController，则触发 abort。
   * 入参说明：无入参。
   * 返回值说明：无返回值。
   *
   * @returns {void}
   */
  const abort = () => {
    abortRef.current?.abort?.()
  }

  return { abort }
}

/**
 * 健康助手专用流式聊天封装：区分思考事件与最终回答事件。
 *
 * 功能描述：
 * - 调用后端 /chat/stream 接口，消费 JSONL 事件流；
 * - 根据事件 type 将内容分发到不同回调（thinking_delta / answer_delta / meta 等）；
 * - 适用于前端聊天框中同时展示「思考过程（可折叠）」与「最终输出」。
 *
 * 入参说明：
 * - message：string，用户输入；
 * - imagePath：string | undefined，图片路径；
 * - imageBase64Url：string | undefined，图片 base64 或 Data URL；
 * - imageUrl：string | undefined，图片公网 URL（优先用于展示与后端多模态）；
 * - signal：AbortSignal | undefined，中断信号；
 * - onThinkingDelta：(delta: string) => void，思考文本增量；
 * - onThinkingDone：() => void，思考阶段结束；
 * - onAnswerDelta：(delta: string) => void，回答文本增量；
 * - onAnswerDone：() => void，回答结束；
 * - onMeta：(meta: any) => void，元事件；
 * - onError：(error: Error) => void，错误回调。
 *
 * 返回值说明：
 * - Promise<void>，无直接返回值，通过回调获取数据。
 *
 * @param {Object} params
 * @returns {Promise<void>}
 */
export async function chatStreamWithThinking({
  message,
  imagePath,
  imageBase64Url,
  imageUrl,
  userId,
  sessionId,
  agentType,
  signal,
  onThinkingDelta,
  onThinkingDone,
  onAnswerDelta,
  onAnswerDone,
  onMeta,
  onError
}) {
  const url = `${API_BASE}/chat/stream`
  const body = {
    message,
    image_path: imagePath || null,
    image_base64_url: imageBase64Url || null,
    image_url: imageUrl || null,
    user_id: userId || null,
    session_id: sessionId || null
  }
  if (agentType && typeof agentType === 'string') {
    body.agent_type = agentType.trim()
  }

  return streamEvents({
    url,
    body,
    signal,
    onEvent: (event) => {
      if (!event || typeof event !== 'object') return
      switch (event.type) {
        case 'thinking_delta':
          onThinkingDelta?.(event.content || '')
          break
        case 'thinking_done':
          onThinkingDone?.()
          break
        case 'answer_delta':
          onAnswerDelta?.(event.content || '')
          break
        case 'answer_done':
          onAnswerDone?.()
          break
        case 'meta':
          onMeta?.(event)
          break
        default:
          break
      }
    },
    onDone: () => onAnswerDone?.(),
    onError
  })
}

