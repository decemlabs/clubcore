/**
 * Standalone ESLint config for fixtures under src/__fixtures/.
 * Mirrors the real SC4 rules from eslint.config.js but:
 *  - does NOT ignore src/__fixtures/
 *  - adds the fixtures path to the `import/no-restricted-paths` target zone
 *    (so the fixture file is treated as "feature-like" code that may not
 *    reach into ./mock or ./http directly).
 *
 * Used by scripts/assert-eslint-fixtures.mjs to prove every guard-rail fires.
 */
import js from '@eslint/js'
import globals from 'globals'
import tseslint from 'typescript-eslint'
import importPlugin from 'eslint-plugin-import'

const RAW_PALETTE_REGEX =
  /\b(?:bg|text|border|ring|from|to|via|fill|stroke|outline|divide|placeholder|caret|accent|decoration|shadow)-(?:white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b|\b(?:bg|text|border)-(?:white|black)\b/

export default tseslint.config(
  {
    ignores: ['dist', 'node_modules', 'src/routeTree.gen.ts'],
  },
  {
    files: ['src/__fixtures/**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    plugins: { import: importPlugin },
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: { 'import/resolver': { typescript: true, node: true } },
    rules: {
      'import/no-restricted-paths': [
        'error',
        {
          zones: [
            {
              target: ['./src/__fixtures/features/**'],
              from: ['./src/shared/api/services/mock/**', './src/shared/api/services/http/**'],
              message:
                'Go through services container or a TanStack Query hook (do not import mock/http impls directly).',
            },
          ],
        },
      ],
      'no-restricted-syntax': [
        'error',
        {
          selector: `JSXAttribute[name.name='className'] Literal[value=/${RAW_PALETTE_REGEX.source}/]`,
          message:
            'Use semantic shadcn tokens (bg-background, text-foreground, ...) instead of raw palette colors.',
        },
        {
          selector: `JSXAttribute[name.name='className'] TemplateElement[value.raw=/${RAW_PALETTE_REGEX.source}/]`,
          message:
            'Use semantic shadcn tokens (bg-background, text-foreground, ...) instead of raw palette colors.',
        },
        {
          selector: "MemberExpression[property.name='VITE_API_MODE']",
          message: 'Read VITE_API_MODE only via @/shared/api/config/env (single chokepoint).',
        },
        {
          selector: "CallExpression[callee.name='fetch']",
          message:
            'Use @sportzal/api-client.request<P,M> instead of raw fetch(). Direct fetch is allowed only inside src/shared/api/services/http/**.',
        },
      ],
    },
  },
)
