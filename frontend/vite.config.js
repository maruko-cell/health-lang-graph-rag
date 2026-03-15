import { defineConfig, transformWithEsbuild } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    {
      name: 'treat-js-files-as-jsx',
      /** 将 src 下的 .js 按 JSX 解析，避免 Vite import-analysis 报错。 */
      async transform(code, id) {
        if (!id.match(/src\/.*\.js$/)) return null
        return transformWithEsbuild(code, id, {
          loader: 'jsx',
          jsx: 'automatic',
        })
      },
    },
    react(),
  ],
  /** 让依赖扫描与构建阶段对 .js 使用 JSX 解析，否则入口/依赖扫描会报 JSX syntax is not enabled */
  esbuild: {
    loader: 'jsx',
    include: /src\/.*\.jsx?$/,
  },
  optimizeDeps: {
    esbuildOptions: {
      loader: { '.js': 'jsx' },
    },
  },
  server: {
    port: 3000,
  },
})
