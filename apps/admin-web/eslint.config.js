import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import importPlugin from 'eslint-plugin-import'

const RAW_PALETTE_REGEX =
  /\b(?:bg|text|border|ring|from|to|via|fill|stroke|outline|divide|placeholder|caret|accent|decoration|shadow)-(?:white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b|\b(?:bg|text|border)-(?:white|black)\b/

export default tseslint.config(
  {
    ignores: [
      'dist',
      'node_modules',
      'src/routeTree.gen.ts',
      'src/__fixtures/**',
      'coverage',
      '.planning/**',
      '.claude/**',
      '.omc/**',
      'scripts/**',
    ],
  },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    plugins: {
      import: importPlugin,
    },
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    settings: {
      'import/resolver': {
        typescript: true,
        node: true,
      },
    },
    rules: {
      // SC4: prevent UI/feature/route/entity/shared.ui code from importing service impls directly
      'import/no-restricted-paths': [
        'error',
        {
          zones: [
            {
              target: [
                './src/features/**',
                './src/routes/**',
                './src/entities/**',
                './src/shared/ui/**',
                './src/app/**',
              ],
              from: [
                './src/shared/api/services/mock/**',
                './src/shared/api/services/http/**',
              ],
              message:
                'Go through services container or a TanStack Query hook (do not import mock/http impls directly).',
            },
            {
              // Phase 22 D-22-12 — Pattern α: composition lives at the route layer only.
              target: ['./src/features/clients/**'],
              from: ['./src/features/memberships/**', './src/features/visits/**'],
              message:
                'Pattern α: features/clients must not import features/memberships or features/visits. Compose at the route level (clients.$clientId.tsx).',
            },
          ],
        },
      ],
      // SC4: ban raw Tailwind palette colors in JSX className strings
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
      ],
      'react/no-danger': 'off',
    },
  },
  {
    // VITE_API_MODE access only allowed inside src/shared/api/**
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/shared/api/**'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector:
            "MemberExpression[property.name='VITE_API_MODE']",
          message:
            'Read VITE_API_MODE only via @/shared/api/config/env (single chokepoint).',
        },
      ],
    },
  },
  {
    // FE-07: raw fetch() banned outside the http transport layer
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/shared/api/services/http/**'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: "CallExpression[callee.name='fetch']",
          message:
            'Use @sportzal/api-client.request<P,M> instead of raw fetch(). Direct fetch is allowed only inside src/shared/api/services/http/**.',
        },
      ],
    },
  },
  {
    files: ['**/*.test.{ts,tsx}', 'src/test/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-syntax': 'off',
      // Test setup code may need direct access to mock DB and service impls for fixtures/resets
      'import/no-restricted-paths': 'off',
    },
  },
  {
    // shadcn primitives (copied into src/shared/ui) co-locate variant exports with components.
    // react-refresh/only-export-components would flag every one; disable for these files only.
    files: [
      'src/shared/ui/button.tsx',
      'src/shared/ui/sidebar.tsx',
      'src/shared/ui/sonner.tsx',
      'src/shared/ui/dropdown-menu.tsx',
      'src/shared/ui/sheet.tsx',
      'src/shared/ui/tooltip.tsx',
      'src/shared/ui/avatar.tsx',
      'src/shared/ui/separator.tsx',
      'src/shared/ui/skeleton.tsx',
      'src/shared/ui/input.tsx',
      // ReUI primitives installed in Phase 10 (D-16)
      'src/shared/ui/form.tsx',
      'src/shared/ui/label.tsx',
      'src/shared/ui/dialog.tsx',
      'src/shared/ui/alert-dialog.tsx',
      'src/shared/ui/data-grid.tsx',
      'src/shared/ui/input-otp.tsx',
      'src/shared/ui/tabs.tsx',
      // Phase 22 new shadcn primitives
      'src/shared/ui/badge.tsx',
      'src/shared/ui/textarea.tsx',
      'src/shared/ui/alert.tsx',
      'src/shared/ui/card.tsx',
      // ReUI DataGrid multi-file component (radix-nova style, co-locates variant exports)
      'src/components/reui/**/*.tsx',
    ],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
)
