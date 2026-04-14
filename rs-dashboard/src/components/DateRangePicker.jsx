import { useMemo, useCallback } from 'react';

/**
 * DateRangePicker — reusable month-range picker with presets.
 *
 * Props:
 *   allMonths   — sorted array of "YYYY-MM" strings (the full available range)
 *   from        — current "from" value ('' = first)
 *   to          — current "to" value   ('' = last)
 *   onFromChange(value)
 *   onToChange(value)
 *   label       — optional label text (default: "პერიოდი")
 *   children    — extra buttons (e.g. Excel export) rendered at the end
 */

function monthLabel(m) {
  if (!m) return '—';
  const [y, mo] = m.split('-');
  if (!y || !mo) return m;
  const MONTHS_KA = ['იან', 'თებ', 'მარ', 'აპრ', 'მაი', 'ივნ', 'ივლ', 'აგვ', 'სექ', 'ოქტ', 'ნოე', 'დეკ'];
  const idx = Number(mo) - 1;
  const label = MONTHS_KA[idx] || mo;
  return `${label} ${y}`;
}

function getPresets(allMonths) {
  if (!allMonths.length) return [];
  const last = allMonths[allMonths.length - 1];
  const first = allMonths[0];

  // helper: go back N months from last
  const goBack = (n) => {
    const [y, m] = last.split('-').map(Number);
    let targetMonth = m - n;
    let targetYear = y;
    while (targetMonth < 1) {
      targetMonth += 12;
      targetYear -= 1;
    }
    const candidate = `${targetYear}-${String(targetMonth).padStart(2, '0')}`;
    // clamp to first available
    return candidate < first ? first : candidate;
  };

  // current year start
  const [lastY] = last.split('-');
  const yearStart = `${lastY}-01`;
  const yearStartClamped = yearStart < first ? first : yearStart;

  return [
    { id: '3m', label: '3 თვე', from: goBack(2), to: last },
    { id: '6m', label: '6 თვე', from: goBack(5), to: last },
    { id: '12m', label: '12 თვე', from: goBack(11), to: last },
    { id: 'ytd', label: `${lastY} წელი`, from: yearStartClamped, to: last },
    { id: 'all', label: 'სრული', from: '', to: '' },
  ];
}

export default function DateRangePicker({
  allMonths,
  from,
  to,
  onFromChange,
  onToChange,
  label,
  children,
}) {
  const months = useMemo(
    () => (Array.isArray(allMonths) ? allMonths : []),
    [allMonths],
  );

  const presets = useMemo(() => getPresets(months), [months]);

  const effectiveFrom = from || months[0] || '';
  const effectiveTo = to || months[months.length - 1] || '';

  // detect active preset
  const activePreset = useMemo(() => {
    for (const p of presets) {
      const pFrom = p.from || months[0] || '';
      const pTo = p.to || months[months.length - 1] || '';
      if (pFrom === effectiveFrom && pTo === effectiveTo) return p.id;
    }
    return null;
  }, [presets, effectiveFrom, effectiveTo, months]);

  const applyPreset = useCallback(
    (p) => {
      onFromChange(p.from);
      onToChange(p.to);
    },
    [onFromChange, onToChange],
  );

  if (!months.length) return null;

  const selectedCount =
    effectiveFrom && effectiveTo
      ? months.filter((m) => m >= effectiveFrom && m <= effectiveTo).length
      : months.length;

  return (
    <div className="drp-bar">
      <div className="drp-label">{label || 'პერიოდი'}</div>

      <div className="drp-presets">
        {presets.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`drp-preset-btn ${activePreset === p.id ? 'drp-preset-active' : ''}`}
            onClick={() => applyPreset(p)}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="drp-selects">
        <label className="drp-field">
          <span className="drp-field-label">დან</span>
          <select
            value={from}
            onChange={(e) => onFromChange(e.target.value)}
            className="drp-select"
          >
            <option value="">პირველი</option>
            {months.map((m) => (
              <option key={m} value={m}>
                {monthLabel(m)}
              </option>
            ))}
          </select>
        </label>
        <span className="drp-sep">—</span>
        <label className="drp-field">
          <span className="drp-field-label">მდე</span>
          <select
            value={to}
            onChange={(e) => onToChange(e.target.value)}
            className="drp-select"
          >
            <option value="">ბოლო</option>
            {months.map((m) => (
              <option key={m} value={m}>
                {monthLabel(m)}
              </option>
            ))}
          </select>
        </label>
        <span className="drp-count">{selectedCount} თვე</span>
      </div>

      {children && <div className="drp-actions">{children}</div>}
    </div>
  );
}
