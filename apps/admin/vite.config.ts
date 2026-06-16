import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // Один экземпляр React на приложение — иначе хуки в sonner/vaul падают
    // («Invalid hook call · more than one copy of React»).
    dedupe: ['react', 'react-dom'],
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  optimizeDeps: {
    include: ['sonner', 'vaul'],
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: process.env['VITE_API_PROXY_TARGET'] ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
