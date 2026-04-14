import { useState } from 'react';
import { exportToXlsx } from '../lib/exportXlsx.js';

/**
 * Reusable Excel export button.
 *
 * Props:
 *   filename  — output filename (e.g. "report.xlsx")
 *   sheets    — array of { name, rows } or { name, aoa } (see exportXlsx)
 *   label     — button text (default: "Excel ჩამოტვირთვა")
 *   disabled  — force disabled
 *   className — extra CSS class
 */
export default function ExportButton({ filename, sheets, label, disabled, className }) {
  const [busy, setBusy] = useState(false);

  const handleClick = async () => {
    if (busy || disabled) return;
    setBusy(true);
    try {
      const stamp = new Date().toISOString().slice(0, 10);
      const fname = filename || `export_${stamp}.xlsx`;
      await exportToXlsx(fname, sheets);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setBusy(false);
    }
  };

  const hasData = sheets && sheets.some((s) => (s.rows?.length || s.aoa?.length) > 0);

  return (
    <button
      type="button"
      className={`btn-download-xlsx ${className || ''}`}
      onClick={handleClick}
      disabled={disabled || busy || !hasData}
      title={!hasData ? 'ექსპორტისთვის მონაცემები არ არის' : ''}
    >
      {busy ? 'იტვირთება...' : (label || 'Excel ჩამოტვირთვა')}
    </button>
  );
}
