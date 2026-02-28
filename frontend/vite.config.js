import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Forward /api/* to FastAPI backend to avoid CORS issues in dev
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        // Disable proxy timeout so SSE streams don't get cut off
        proxyTimeout: 0,
        timeout: 0,
      },
    },
  },
})
