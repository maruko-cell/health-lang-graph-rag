import React from 'react'
import ReactDOM from 'react-dom/client'
import { AppProvider } from './context'
import App from './App'
import './index.scss'

const root = ReactDOM.createRoot(document.getElementById('root'))

/**
 * 应用入口渲染函数，将根组件挂载到 DOM 容器中。
 * 无入参。
 * 无返回值。
 */
const renderApp = () => {
  root.render(
    <React.StrictMode>
      <AppProvider>
        <App />
      </AppProvider>
    </React.StrictMode>
  )
}

renderApp()

