import { useCallback, useState } from 'react'
import constants from '../../common/constant.json'
import FileUploadBubble from './FileUploadBubble'
import { uploadImage } from '../api/upload_image'
import { useAppContext } from '../context'
import { ACTION_TYPES } from '../context/actionTypes'

const { agentList = [] } = constants

/**
 * 输入框下方的快捷技能栏组件，展示常用功能入口标签。
 * 无入参。
 * @returns {JSX.Element} 返回快捷技能入口按钮列表及 Multi-Moda 上传能力。
 */
const InputQuickBar = () => {
  const [multiModaOpen, setMultiModaOpen] = useState(false)
  const { state, dispatch } = useAppContext()
  const multiModaAgent = agentList.find((agent) => agent.type === 'multi-moda')
  const multiModaTitle = multiModaAgent?.guidance || '请上传图片：'

  /**
   * 为多模态快捷入口生成唯一消息 ID。
   *
   * 功能描述：
   * 生成在 reducer 与 Content 组件中可唯一标识的消息 id，供追加流式内容时使用。
   *
   * 入参说明：
   * - 无入参。
   *
   * 返回值说明：
   * - string：消息唯一 id。
   */
  const createMessageId = useCallback(() => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID()
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`
  }, [])

  /**
   * 处理快捷技能标签点击。
   *
   * 功能描述：
   * - 当点击 multi-moda 类型标签时，打开图片上传弹窗；
   * - 当点击其他类型标签时，将预设问题写入全局输入框，由 ChatInput 组件监听并自动发送。
   *
   * 入参说明：
   * - agent：从常量配置中读取的技能对象。
   *
   * 返回值说明：
   * - 无返回值。
   */
  const handleAgentClick = (agent) => {
    if (agent.type === 'multi-moda') {
      setMultiModaOpen(true)
      return
    }

    dispatch({
      type: ACTION_TYPES.SET_INPUT_VALUE,
      payload: agent.message || ''
    })
    if (agent.type === 'selfie') {
      dispatch({ type: ACTION_TYPES.SET_PENDING_AGENT_TYPE, payload: 'selfie' })
    }
  }

  /**
   * 处理多模态图片上传成功事件。
   *
   * 功能描述：
   * 将后端返回的图片路径与 base64 Data URL 写入全局状态，供后续 chatStream 调用时使用，
   * 同时关闭上传弹窗。
   *
   * 入参说明：
   * - result：后端 /upload/image/oss 返回的结果，包含 url（完整 OSS 地址）、path、base64_url（兼容）、filename、content_type。
   *
   * 返回值说明：
   * - 无返回值。
   */
  const handleUploaded = async (result) => {
    const multiModaAgent = agentList.find((agent) => agent.type === 'multi-moda')
    const prompt = multiModaAgent?.message || '帮我看一下这张病例图片'

    const userId = createMessageId()
    const assistantId = createMessageId()

    /** 当前会话 id，用于将多模态消息归属到正确的会话 */
    const sessionId = state.currentSessionId
    if (!sessionId) {
      return
    }

    /** 展示用地址优先 url，兼容 base64_url；path 供后端多模态使用 */
    const imageUrl = result?.imageUrl ?? result?.url ?? result?.base64_url ?? null
    const imagePath = result?.path ?? result?.url ?? null
    const imageBase64Url = result?.base64_url ?? result?.url ?? null

    // 写入一条同时包含默认提示词和图片的用户消息
    dispatch({
      type: ACTION_TYPES.ADD_MESSAGE,
      payload: {
        sessionId,
        id: userId,
        role: 'user',
        content: prompt,
        imagePath,
        imageBase64Url,
        imageUrl
      }
    })

    // 创建一条空的助手消息，用于承接流式返回（包含思考与最终回答两个区块）
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
        answerDone: false
      }
    })

    // 关闭弹窗并标记 loading
    setMultiModaOpen(false)
    dispatch({ type: ACTION_TYPES.SET_MESSAGES_LOADING, payload: true })

    try {
      const { chatStreamWithThinking } = await import('../api/chat_stream')

      await chatStreamWithThinking({
        message: prompt,
        imagePath,
        imageBase64Url,
        imageUrl,
        userId: state.currentUserId,
        sessionId,
        signal: null,
        onThinkingDelta: (chunk) => {
          dispatch({
            type: ACTION_TYPES.APPEND_MESSAGE_THINKING,
            payload: { sessionId, messageId: assistantId, chunk }
          })
        },
        onThinkingDone: () => {
          dispatch({
            type: ACTION_TYPES.SET_MESSAGE_THINKING_DONE,
            payload: { sessionId, messageId: assistantId }
          })
        },
        onAnswerDelta: (chunk) => {
          dispatch({
            type: ACTION_TYPES.APPEND_MESSAGE_FINAL_ANSWER,
            payload: { sessionId, messageId: assistantId, chunk }
          })
        },
        onAnswerDone: () => {
          dispatch({
            type: ACTION_TYPES.SET_MESSAGE_ANSWER_DONE,
            payload: { sessionId, messageId: assistantId }
          })
          dispatch({ type: ACTION_TYPES.SET_MESSAGES_LOADING, payload: false })
        },
        onMeta: () => { },
        onError: () => {
          dispatch({ type: ACTION_TYPES.SET_MESSAGES_LOADING, payload: false })
        }
      })
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error(error)
      dispatch({ type: ACTION_TYPES.SET_MESSAGES_LOADING, payload: false })
    }
  }

  return (
    <>
      <nav className="input-quick-bar" aria-label="快捷技能">
        {agentList.map((agent) => (
          <button
            key={agent.type}
            type="button"
            className="input-quick-bar__item"
            aria-label={`使用技能：${agent.name}`}
            onClick={() => handleAgentClick(agent)}
          >
            {agent.name}
          </button>
        ))}
      </nav>

      <FileUploadBubble
        open={multiModaOpen}
        onClose={() => setMultiModaOpen(false)}
        title={multiModaTitle}
        uploadFn={uploadImage}
        onUploaded={handleUploaded}
        accept="image/*"
        allowedMimePrefixes={['image/']}
        buttonText="选择图片"
        successMessage="图片上传成功"
        rejectMessage="仅支持上传图片文件"
        uploadErrorMessage="图片上传失败"
      />
    </>
  )
}

export default InputQuickBar

