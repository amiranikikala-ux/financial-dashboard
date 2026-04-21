import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ErrorBoundary from './ErrorBoundary.jsx'

/* Dev-only Service Worker guard.
 *
 * Previously the cleanup ran inside `window.addEventListener('load', ...)`,
 * which is AFTER the React bundle has already executed. By that point the
 * SW had already intercepted the initial navigation request and served a
 * stale `index.html` + chunk set from a previous PROD build. That is
 * exactly the symptom "AI FAB doesn't show and needs a manual refresh" —
 * the cached HTML references chunks that no longer exist in the fresh Vite
 * dev bundle, lazy `ChatAssistant` fetch fails, Suspense fallback={null}
 * renders nothing.
 *
 * Fix: do the cleanup SYNCHRONOUSLY before mounting React. If a SW was
 * actively controlling the page (meaning the current HTML came from cache,
 * not from Vite), force a one-shot reload so the next load goes straight
 * to the dev server with no interception.
 */
const clearDevServiceWorkerState = async () => {
  if (!('serviceWorker' in navigator)) return false

  const hadController = Boolean(navigator.serviceWorker.controller)

  const registrations = await navigator.serviceWorker.getRegistrations().catch(() => [])
  await Promise.all(registrations.map((registration) => registration.unregister()))

  if ('caches' in window) {
    const cacheKeys = await window.caches.keys().catch(() => [])
    await Promise.all(
      cacheKeys
        .filter((key) => key.startsWith('rs-dashboard'))
        .map((key) => window.caches.delete(key))
    )
  }

  /* If the current page was served by an old worker, do a single hard reload
   * so the user gets the fresh dev bundle without any manual Ctrl+Shift+R.
   * The sessionStorage guard prevents an infinite reload loop in the rare
   * case a SW re-registers before the reload completes. */
  if (hadController && !window.sessionStorage.getItem('rs-sw-reset-done')) {
    window.sessionStorage.setItem('rs-sw-reset-done', '1')
    window.location.reload()
    return true
  }

  return false
}

const mountApp = () => {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </StrictMode>,
  )
}

if (import.meta.env.PROD) {
  mountApp()
} else {
  /* Dev: run SW purge first; only mount once we know we're not about to
   * reload. Fail-open — if anything throws, still mount the app. */
  clearDevServiceWorkerState()
    .then((willReload) => {
      if (!willReload) mountApp()
    })
    .catch(() => mountApp())
}

/* Service worker registration + auto-update flow.
 *
 * In production we register /sw.js and then wire up the "a new version is
 * ready" lifecycle:
 *   1. Poll `registration.update()` every 60s while the tab is visible — picks
 *      up a freshly deployed SW without requiring a full tab close.
 *   2. When a new worker reaches `installed` state AND the page is already
 *      controlled by an old worker, post `SKIP_WAITING` so the new one
 *      activates immediately.
 *   3. Listen for `controllerchange` and reload exactly once — the tab then
 *      loads the new HTML + bundles under the new cache name.
 *
 * This is what makes "ძველი ვერსია browser-ში" stop happening: as soon as we
 * deploy new code, the next time the user visits (or the page is open and
 * polls), they get auto-refreshed onto the latest bundle.
 */
const registerServiceWorker = () => {
  navigator.serviceWorker
    .register('/sw.js')
    .then((registration) => {
      /* Periodic update check — cheap; only pings the SW script. */
      const SIXTY_SECONDS = 60 * 1000
      const tick = () => registration.update().catch(() => {})
      setInterval(tick, SIXTY_SECONDS)
      window.addEventListener('focus', tick)

      registration.addEventListener('updatefound', () => {
        const installing = registration.installing
        if (!installing) return
        installing.addEventListener('statechange', () => {
          if (
            installing.state === 'installed' &&
            navigator.serviceWorker.controller
          ) {
            /* New version ready AND an old SW is already controlling this
             * page → ask the new one to activate immediately. The
             * `controllerchange` handler below will then reload the tab. */
            installing.postMessage({ type: 'SKIP_WAITING' })
          }
        })
      })

      let refreshing = false
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (refreshing) return
        refreshing = true
        window.location.reload()
      })
    })
    .catch(() => {})
}

/* PROD-only: register the production service worker after the initial load.
 * Dev-mode cleanup already happened synchronously before mount (see top of
 * file), so we must not run it again here — it would trigger a needless
 * double-unregister and another `sessionStorage` write on every load. */
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', registerServiceWorker)
}
