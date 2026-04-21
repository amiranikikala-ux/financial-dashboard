import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import process from 'node:process'
import fs from 'node:fs'
import path from 'node:path'

const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'
const analyze = process.env.ANALYZE === 'true' || process.env.npm_lifecycle_event === 'build:analyze'

/**
 * sw-cache-bust: stamps a unique BUILD_ID into dist/sw.js after every build.
 *
 * Background: the service worker keys its cache on `CACHE_NAME`. If that name
 * doesn't change, redeploying a new bundle leaves every returning user stuck
 * on the previous cached shell (since the old `activate` hook didn't find any
 * "old" cache to purge).  Replacing the literal `__BUILD_ID__` token at build
 * time yields `rs-dashboard-<unique>` per deploy — the activate hook then
 * evicts ALL prior `rs-dashboard-*` caches automatically.
 */
const swCacheBust = () => ({
  name: 'sw-cache-bust',
  apply: 'build',
  closeBundle() {
    const swPath = path.resolve('dist', 'sw.js')
    if (!fs.existsSync(swPath)) return
    const buildId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
    const src = fs.readFileSync(swPath, 'utf-8')
    const next = src.replace(/__BUILD_ID__/g, buildId)
    fs.writeFileSync(swPath, next, 'utf-8')
    console.log(`[sw-cache-bust] CACHE_NAME → rs-dashboard-${buildId}`)
  },
})

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    swCacheBust(),
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
