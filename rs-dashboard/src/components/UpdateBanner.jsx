import { useEffect, useState } from 'react';

/* Soft "new version available" toast.
 *
 * Wired in `main.jsx`: when the service worker installs a new version, instead
 * of reloading the tab automatically (which destroys the user's expanded rows,
 * filters, scroll position), a `rs-update-available` CustomEvent fires. This
 * component listens for it and shows a fixed-position banner. Clicking the
 * "განახლება" button dispatches `rs-apply-update` which `main.jsx` translates
 * into `SKIP_WAITING` → controllerchange → page reload.
 *
 * Same UX pattern as Gmail / GitHub — user keeps full control of when to
 * refresh.
 */
export default function UpdateBanner() {
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    const handler = () => setAvailable(true);
    window.addEventListener('rs-update-available', handler);
    return () => window.removeEventListener('rs-update-available', handler);
  }, []);

  if (!available) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        bottom: 20,
        left: 20,
        zIndex: 9999,
        background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        color: '#fff',
        padding: '12px 16px',
        borderRadius: 10,
        boxShadow: '0 8px 24px rgba(16, 185, 129, 0.35)',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        fontSize: 14,
        fontWeight: 500,
        maxWidth: 360,
      }}
    >
      <span style={{ fontSize: 18 }}>🟢</span>
      <span>ახალი ვერსია მზადაა</span>
      <button
        type="button"
        onClick={() => window.dispatchEvent(new CustomEvent('rs-apply-update'))}
        style={{
          marginLeft: 'auto',
          background: '#fff',
          color: '#059669',
          border: 'none',
          borderRadius: 6,
          padding: '6px 12px',
          fontWeight: 600,
          fontSize: 13,
          cursor: 'pointer',
        }}
      >
        განახლება
      </button>
    </div>
  );
}
