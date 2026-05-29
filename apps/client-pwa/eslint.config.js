import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import importPlugin from 'eslint-plugin-import'

export default tseslint.config(
  {
    // D-69-06: existing .jsx/.js screens are in the allowJs ramp — do not lint them
    // until they are migrated to TypeScript in later phases.
    ignores: [
      'dist',
      'node_modules',
      'coverage',
      // Pre-existing JSX/JS screens and utilities (D-69-06 allowJs ramp)
      'src/**/*.jsx',
      'src/**/*.js',
    ],
  },
  {
    // Enforce linting only on new TypeScript code
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    plugins: { import: importPlugin },
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    settings: {
      'import/resolver': { typescript: true, node: true },
    },
    rules: {
      // No import boundary zones configured yet — clientFetcher layer enforcement
      // will be added in Phase 71 once screen wiring begins.
    },
  },
  {
    files: ['**/*.test.{ts,tsx}', 'src/test/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-syntax': 'off',
      '@typescript-eslint/no-require-imports': 'off',
    },
  },
)
