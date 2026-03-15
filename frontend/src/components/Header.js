import KbFileUploader from './KbFileUploader'
import AddSessionBtn from './AddSessionBtn'

/**
 * 页面头部组件，展示应用标题、品牌信息及快捷操作按钮。
 * 无入参。
 * @returns {JSX.Element} 返回包含标题栏与操作区域的 React 组件节点。
 */
const Header = () => {
  return (
    <header className="app-header">
      <div className="app-header__left">
        <AddSessionBtn />
      </div>
      <h1 className="app-title">健康小管家</h1>
      <div className="app-header__right">
        <KbFileUploader />
      </div>
    </header>
  )
}

export default Header


