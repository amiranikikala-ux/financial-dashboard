import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import process from 'node:process'

const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'
const analyze = process.env.ANALYZE === 'true' || process.env.npm_lifecycle_event === 'build:analyze'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    analyze && (await import('rollup-plugin-visualizer')).visualizer({
      open: true,
      filename: 'dist/bundle-report.html',
      gzipSize: true,
      brotliSize: true,
      template: 'treemap',
    }),
  ].filter(Boolean),
  build: {
    target: 'esnext',
    reportCompressedSize: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react-dom') || id.includes('node_modules/react/')) {
            return 'vendor-react'
          }
          if (id.includes('node_modules/recharts')) {
            return 'vendor-recharts'
          }
        },
      },
    },
  },
  server: {
    host: true,
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
})
