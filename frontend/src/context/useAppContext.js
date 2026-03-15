import { useContext } from 'react'
import { AppContext } from './AppContext'

/**
 * 获取全局 state 与 dispatch，供子组件读写全局状态。
 * 必须在 AppProvider 子树内使用，否则抛错。
 *
 * @returns {{ state: Object, dispatch: Function }} 当前 state 与 dispatch 函数
 */
export const useAppContext = () => {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useAppContext 必须在 AppProvider 内部使用')
  }
  return context
}
