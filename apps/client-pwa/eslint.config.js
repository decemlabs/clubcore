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
    // D-71-09: the five net-new placeholder screens are excluded from the global
    // ignore so the dedicated no-restricted-paths block (below) can apply to them.
    ignores: [
      'dist',
      'node_modules',
      'coverage',
      // Pre-existing JSX/JS screens and utilities (D-69-06 allowJs ramp)
      // Exceptions: the net-new placeholder screens are NOT ignored here so
      // the D-71-09 import-boundary block can lint them for the restricted-paths rule.
      // GymInfoSheet graduated to a real data-backed screen in Phase 86 — removed
      // from the placeholder zone, now ignored like other real .jsx screens.
      // Phase 87 (INBOX-05): the notifications sheet also graduated — removed from
      // the placeholder zone, now ignored like other real .jsx screens.
      // Phase 88 (TRNR-04): trainer detail sheet graduated — wired to GET /client/trainers/{id}.
      'src/**/*.jsx',
      'src/**/*.js',
      '!src/screens/ChatScreen.jsx',
      '!src/screens/sheets/ReferralSheet.jsx',
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
  // ─── D-71-09: Net-new screen import boundary ────────────────────────────────
  // The five net-new placeholder screens are excluded from the global JSX ignore
  // above (via negated patterns) so this block can apply the no-restricted-paths
  // rule to them. These screens must NEVER import the query layer — they are
  // "В разработке" placeholders (D-71-08) and making real API calls would violate
  // PWA-05 success criterion #5 (net-new screens make zero backend calls).
  {
    files: [
      'src/screens/ChatScreen.jsx',
      'src/screens/sheets/ReferralSheet.jsx',
    ],
    plugins: { import: importPlugin },
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      'import/resolver': { typescript: true, node: true },
    },
    rules: {
      // D-71-09: net-new placeholder screens cannot import the query layer.
      // Enforced structurally — not by review only.
      'import/no-restricted-paths': [
        'error',
        {
          zones: [
            {
              target: [
                './src/screens/ChatScreen.jsx',
                './src/screens/sheets/ReferralSheet.jsx',
              ],
              from: [
                './src/lib/clientFetcher.ts',
                './src/lib/clientQueries.ts',
                './src/data/index.js',
              ],
              message:
                'Net-new screens are placeholders (D-71-09) — no query layer imports.',
            },
          ],
        },
      ],
    },
  },
)
