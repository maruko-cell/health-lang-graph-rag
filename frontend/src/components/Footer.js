import ChatInput from './ChatInput'
import InputQuickBar from './InputQuickBar'

/**
 * 页面底部容器组件，承载聊天输入框和快捷技能栏。
 * 无入参。
 * @returns {JSX.Element} 返回包含聊天输入与快捷栏的 React 组件节点。
 */
const Footer = () => {
  return (
    <footer className="app-footer">
      <ChatInput />
      <InputQuickBar />
    </footer>
  )
}

export default Footer

