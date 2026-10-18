import js from '@eslint/js'
import globals from 'globals'
export default [
  { ignores: ['node_modules/**', 'test-results/**', 'playwright-report/**', 'design/**'] },
  {
    files: ['src/**/*.js'],
    ...js.configs.recommended,
    languageOptions: { ecmaVersion: 'latest', sourceType: 'module', globals: { ...globals.browser, ...globals.worker } },
    rules: { ...js.configs.recommended.rules, 'no-unused-vars': ['error', { argsIgnorePattern: '^_' }] },
  },
]
