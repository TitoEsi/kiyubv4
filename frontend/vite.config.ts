import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  envDir: path.resolve(__dirname, '..'),
  test: {
    environment: 'node',
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
        timeout: 300_000,
        proxyTimeout: 300_000,
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            console.error('[KIYUB PROXY] /api error:', err.message)
            if (res && !res.headersSent && typeof (res as { writeHead?: Function }).writeHead === 'function') {
              const r = res as { writeHead: Function; end: Function }
              r.writeHead(502, { 'Content-Type': 'application/json' })
              r.end(JSON.stringify({
                detail: 'Generation API is unreachable. Start the backend on port 8002 and try again.',
              }))
            }
          })
        },
      },
    },
  },
})
