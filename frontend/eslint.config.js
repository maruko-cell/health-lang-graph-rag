import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import importPlugin from 'eslint-plugin-import'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    plugins: {
      import: importPlugin,
    },
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      /** 所有 import 必须在文件顶部，禁止在其它语句之后写 import */
      'import/first': 'error',
      /** import 块后保留空行，便于与其它代码区分 */
      'import/newline-after-import': 'error',
      /** import 排序（可自动修复）：先内置/外部包，再内部模块，同组内按字母序 */
      'import/order': [
        'error',
        {
          groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
          'newlines-between': 'always',
          alphabetize: { order: 'asc', caseInsensitive: true },
          pathGroups: [
            { pattern: 'react', group: 'external', position: 'before' },
          ],
          pathGroupsExcludedImportTypes: ['react'],
        },
      ],
    },
  },
])
