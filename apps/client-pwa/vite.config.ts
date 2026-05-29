import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'node:path'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      // PWA-07: NEVER cache /api/* — no stale authed data in SW cache (T-69-07)
      navigateFallbackDenylist: [/^\/api\//],
      workbox: {
        // No runtime caching rules for the API origin
        runtimeCaching: [],
      },
      manifest: {
        name: 'Sportzal',
        short_name: 'Sportzal',
        display: 'standalone',
        start_url: '/',
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5174, // avoid conflict with admin-web on 5173
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
  build: {
    target: 'es2022',
  },
  esbuild: {
    target: 'es2022',
  },
})
