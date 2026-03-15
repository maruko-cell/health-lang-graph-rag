/**
 * 全局状态 action 类型常量，供 reducer 与组件 dispatch 使用，避免魔法字符串。
 */

/**
 * 功能描述：统一导出全局状态 action type，集中管理并避免魔法字符串与拼写错误。
 * 入参说明：无入参。
 * 返回值说明：导出一个对象，key 为常量名，value 为 action type 字符串。
 * 关键逻辑备注：建议 value 与 key 保持一致，便于排查与全局搜索。
 */
export const ACTION_TYPES = {
  /** 功能：设置会话列表（全量替换）。 */
  SET_SESSIONS: 'SET_SESSIONS',
  /** 功能：新增一个会话（插入到列表头部）。 */
  ADD_SESSION: 'ADD_SESSION',
  /** 功能：删除一个会话。 */
  DELETE_SESSION: 'DELETE_SESSION',
  /** 功能：设置当前选中的会话 ID。 */
  SET_CURRENT_SESSION_ID: 'SET_CURRENT_SESSION_ID',
  /** 功能：设置消息列表（全量替换）。 */
  SET_MESSAGES: 'SET_MESSAGES',
  /** 功能：新增一条消息。 */
  ADD_MESSAGE: 'ADD_MESSAGE',
  /** 功能：向指定消息追加旧版纯文本流式内容片段（兼容保留）。 */
  APPEND_MESSAGE_CONTENT: 'APPEND_MESSAGE_CONTENT',
  /** 功能：向指定助手消息追加思考过程增量文本。 */
  APPEND_MESSAGE_THINKING: 'APPEND_MESSAGE_THINKING',
  /** 功能：标记指定助手消息的思考过程已结束。 */
  SET_MESSAGE_THINKING_DONE: 'SET_MESSAGE_THINKING_DONE',
  /** 功能：设置指定助手消息的思考耗时秒数，用于前端展示“已思考（用时 X 秒）”。 */
  SET_MESSAGE_THINKING_DURATION: 'SET_MESSAGE_THINKING_DURATION',
  /** 功能：向指定助手消息追加最终回答增量文本。 */
  APPEND_MESSAGE_FINAL_ANSWER: 'APPEND_MESSAGE_FINAL_ANSWER',
  /** 功能：标记指定助手消息的最终回答已结束。 */
  SET_MESSAGE_ANSWER_DONE: 'SET_MESSAGE_ANSWER_DONE',
  /** 功能：设置消息加载中状态。 */
  SET_MESSAGES_LOADING: 'SET_MESSAGES_LOADING',
  /** 功能：设置当前会话关联的多模态图片信息（路径与 base64 Data URL）。 */
  SET_CURRENT_IMAGE: 'SET_CURRENT_IMAGE',
  /** 功能：设置当前输入框内容，用于在快捷入口点击时预填消息文本。 */
  SET_INPUT_VALUE: 'SET_INPUT_VALUE',
  /** 功能：设置待发送的 agent 类型（如 selfie），发送后由 ChatInput 清除；用于点击 Self 等按钮时强制走对应子图。 */
  SET_PENDING_AGENT_TYPE: 'SET_PENDING_AGENT_TYPE',
  /** 功能：设置当前用户 id（占位，后续登录后从 token 解析）。 */
  SET_CURRENT_USER_ID: 'SET_CURRENT_USER_ID',
  /** 功能：标记会话/历史是否已从服务端加载完成，用于刷新恢复。 */
  SET_SESSIONS_LOADED: 'SET_SESSIONS_LOADED'
}
