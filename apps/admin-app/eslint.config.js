import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import importPlugin from 'eslint-plugin-import'

export default tseslint.config(
  { ignores: ['dist', 'node_modules', '.claude/**'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      import: importPlugin,
    },
    settings: {
      'import/resolver': {
        typescript: { project: './tsconfig.app.json' },
      },
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/consistent-type-imports': 'warn',
      // Import boundary: pages/features/components/layouts must not import api/client.ts directly
      // (except the auth domain which owns the transport seam).
      'import/no-restricted-paths': [
        'error',
        {
          zones: [
            {
              target: [
                './src/features/**',
                './src/pages/**',
                './src/layouts/**',
                './src/components/**',
              ],
              from: ['./src/api/client.ts'],
              except: ['./src/features/auth/**'],
              message:
                'Use TanStack Query hooks from features/*/api.ts, not staffRequest directly.',
            },
          ],
        },
      ],
    },
  },
  {
    // Vendored shadcn/ui primitives: a component plus its variants/helpers
    // intentionally live in one file, which trips react-refresh's HMR rule.
    files: ['src/components/ui/**/*.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    // VITE_API_MODE chokepoint: only the per-domain swap-seam api.ts files are
    // allowed to read import.meta.env.VITE_API_MODE. All other src files must not.
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/features/auth/**'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: "MemberExpression[property.name='VITE_API_MODE']",
          message:
            'Read VITE_API_MODE only inside src/features/*/api.ts swap-seam files.',
        },
      ],
    },
  },
)
