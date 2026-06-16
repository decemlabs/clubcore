import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// `test` is a vitest-only key. Extracting the config to a const avoids TS's
// object-literal excess-property check (vite's UserConfig has no `test`), while
// the extra `test` property rides along structurally and vitest reads it at
// runtime. This is deterministic — no reliance on the flaky `/// <reference>`
// UserConfig augmentation, which is non-deterministic under `tsc -b` with the
// vite@6 / vitest@2 split (see Phase 105 admin-web-retirement notes).
const config = {
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx,jsx}'],
    exclude: ['node_modules', 'dist'],
  },
}

export default defineConfig(config)
