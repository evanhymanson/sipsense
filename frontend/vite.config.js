import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync, writeFileSync } from 'fs'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    react(),
    // Inject build timestamp into sw.js so the cache name rotates on each deploy
    {
      name: 'sw-build-id',
      writeBundle(options) {
        const swPath = resolve(options.dir, 'sw.js')
        try {
          const content = readFileSync(swPath, 'utf-8')
          writeFileSync(swPath, content.replace('__BUILD_ID__', Date.now().toString()))
        } catch { /* sw.js not present in dev */ }
      },
    },
  ],
  test: {
    environment: 'jsdom',
    globals: true,
  },
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
      // Forward /uploads/* for bottle images and other static assets
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Split heavy vendor libraries into separate cacheable chunks
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // Leaflet is NOT included here — it stays in its own lazy-loaded
          // chunk so it only downloads when the map sidebar is opened.
        },
      },
    },
    // Enable CSS code splitting for route-level styles
    cssCodeSplit: true,
  },
})
