import { useState, useMemo, useCallback, useRef, useEffect } from 'react';

/**
 * CalendarRangePicker — ლამაზი კალენდარი დღეების/პერიოდის მოსანიშნად.
 *
 * Props:
 *   availableDays  — string[] of "YYYY-MM-DD" (days that have data)
 *   from           — current start date "YYYY-MM-DD"
 *   to             — current end date "YYYY-MM-DD"
 *   onFromChange(value)
 *   onToChange(value)
 *   label          — optional label
 *   children       — extra actions (export buttons, etc.)
 */

const MONTHS_KA = [
  'იანვარი', 'თებერვალი', 'მარტი', 'აპრილი', 'მაისი', 'ივნისი',
  'ივლისი', 'აგვისტო', 'სექტემბერი', 'ოქტომბერი', 'ნოემბერი', 'დეკემბერი',
];

const WEEKDAYS_KA = ['ორშ', 'სამ', 'ოთხ', 'ხუთ', 'პარ', 'შაბ', 'კვი'];

function formatDateKa(dateStr) {
  if (!dateStr) return '—';
  const [y, m, d] = dateStr.split('-');
  const mi = Number(m) - 1;
  return `${Number(d)} ${MONTHS_KA[mi]?.slice(0, 3) || m}, ${y}`;
}

function daysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate();
}

function firstDayOfWeek(year, month) {
  const d = new Date(year, month, 1).getDay();
  return d === 0 ? 6 : d - 1; // Monday = 0
}

function toDateStr(y, m, d) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

function getPresets(availableDays) {
  if (!availableDays.length) return [];
  const last = availableDays[availableDays.length - 1];
  const first = availableDays[0];

  const goBack = (n) => {
    const d = new Date(last);
    d.setDate(d.getDate() - n + 1);
    const candidate = d.toISOString().slice(0, 10);
    return candidate < first ? first : candidate;
  };

  return [
    { id: '7d', label: '7 დღე', from: goBack(7), to: last },
    { id: '14d', label: '14 დღე', from: goBack(14), to: last },
    { id: '30d', label: '30 დღე', from: goBack(30), to: last },
    { id: '90d', label: '90 დღე', from: goBack(90), to: last },
    { id: 'all', label: 'სრული', from: first, to: last },
  ];
}

export default function CalendarRangePicker({
  availableDays = [],
  from,
  to,
  onFromChange,
  onToChange,
  label,
  children,
}) {
  const [open, setOpen] = useState(false);
  const [selectingEnd, setSelectingEnd] = useState(false);
  const [hoverDay, setHoverDay] = useState(null);
  const popRef = useRef(null);

  const sortedDays = useMemo(() => {
    const s = [...availableDays].sort();
    return s;
  }, [availableDays]);

  const daySet = useMemo(() => new Set(sortedDays), [sortedDays]);

  const firstAvail = sortedDays[0] || '';
  const lastAvail = sortedDays[sortedDays.length - 1] || '';

  // Initialize viewMonth to 'from' or last available
  const initMonth = useMemo(() => {
    const ref = from || lastAvail;
    if (!ref) return { year: new Date().getFullYear(), month: new Date().getMonth() };
    const [y, m] = ref.split('-').map(Number);
    return { year: y, month: m - 1 };
  }, [from, lastAvail]);

  const [viewYear, setViewYear] = useState(initMonth.year);
  const [viewMonth, setViewMonth] = useState(initMonth.month);

  const presets = useMemo(() => getPresets(sortedDays), [sortedDays]);

  const activePreset = useMemo(() => {
    const ef = from || firstAvail;
    const et = to || lastAvail;
    for (const p of presets) {
      if (p.from === ef && p.to === et) return p.id;
    }
    return null;
  }, [presets, from, to, firstAvail, lastAvail]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (popRef.current && !popRef.current.contains(e.target)) {
        setOpen(false);
        setSelectingEnd(false);
        setHoverDay(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const goPrev = useCallback(() => {
    setViewMonth((m) => {
      if (m === 0) {
        setViewYear((y) => y - 1);
        return 11;
      }
      return m - 1;
    });
  }, []);

  const goNext = useCallback(() => {
    setViewMonth((m) => {
      if (m === 11) {
        setViewYear((y) => y + 1);
        return 0;
      }
      return m + 1;
    });
  }, []);

  const handleDayClick = useCallback(
    (dayStr) => {
      if (!selectingEnd) {
        // Selecting start
        onFromChange(dayStr);
        onToChange(dayStr);
        setSelectingEnd(true);
      } else {
        // Selecting end
        if (dayStr < from) {
          onFromChange(dayStr);
          onToChange(from);
        } else {
          onToChange(dayStr);
        }
        setSelectingEnd(false);
        setHoverDay(null);
      }
    },
    [selectingEnd, from, onFromChange, onToChange],
  );

  const applyPreset = useCallback(
    (p) => {
      console.log('[CRP DEBUG] applyPreset called:', p.id, p.from, '→', p.to);
      onFromChange(p.from);
      onToChange(p.to);
      setSelectingEnd(false);
      setHoverDay(null);
    },
    [onFromChange, onToChange],
  );

  // Build calendar grid
  const calendarDays = useMemo(() => {
    const total = daysInMonth(viewYear, viewMonth);
    const startOffset = firstDayOfWeek(viewYear, viewMonth);
    const cells = [];

    // Empty cells before first day
    for (let i = 0; i < startOffset; i++) {
      cells.push({ key: `empty-${i}`, day: null });
    }

    for (let d = 1; d <= total; d++) {
      const dateStr = toDateStr(viewYear, viewMonth, d);
      cells.push({
        key: dateStr,
        day: d,
        dateStr,
        hasData: daySet.has(dateStr),
      });
    }

    return cells;
  }, [viewYear, viewMonth, daySet]);

  // Second month
  const nextMonthYear = viewMonth === 11 ? viewYear + 1 : viewYear;
  const nextMonthIdx = viewMonth === 11 ? 0 : viewMonth + 1;

  const calendarDays2 = useMemo(() => {
    const total = daysInMonth(nextMonthYear, nextMonthIdx);
    const startOffset = firstDayOfWeek(nextMonthYear, nextMonthIdx);
    const cells = [];

    for (let i = 0; i < startOffset; i++) {
      cells.push({ key: `empty2-${i}`, day: null });
    }

    for (let d = 1; d <= total; d++) {
      const dateStr = toDateStr(nextMonthYear, nextMonthIdx, d);
      cells.push({
        key: dateStr,
        day: d,
        dateStr,
        hasData: daySet.has(dateStr),
      });
    }

    return cells;
  }, [nextMonthYear, nextMonthIdx, daySet]);

  const effectiveFrom = from || firstAvail;
  const effectiveTo = to || lastAvail;
  const selectedCount = sortedDays.filter((d) => d >= effectiveFrom && d <= effectiveTo).length;

  const isInRange = (dateStr) => {
    if (!dateStr) return false;
    if (selectingEnd && hoverDay) {
      const lo = from <= hoverDay ? from : hoverDay;
      const hi = from <= hoverDay ? hoverDay : from;
      return dateStr >= lo && dateStr <= hi;
    }
    return dateStr >= effectiveFrom && dateStr <= effectiveTo;
  };

  const isStart = (dateStr) => dateStr === effectiveFrom;
  const isEnd = (dateStr) => dateStr === effectiveTo;

  const renderMonth = (cells, monthIdx, year) => (
    <div className="crp-month">
      <div className="crp-month-title">
        {MONTHS_KA[monthIdx]} {year}
      </div>
      <div className="crp-weekdays">
        {WEEKDAYS_KA.map((w) => (
          <div key={w} className="crp-weekday">{w}</div>
        ))}
      </div>
      <div className="crp-days">
        {cells.map((cell) => {
          if (!cell.day) {
            return <div key={cell.key} className="crp-day crp-day--empty" />;
          }
          const inRange = isInRange(cell.dateStr);
          const start = isStart(cell.dateStr);
          const end = isEnd(cell.dateStr);
          const cls = [
            'crp-day',
            cell.hasData ? 'crp-day--available' : 'crp-day--disabled',
            inRange ? 'crp-day--in-range' : '',
            start ? 'crp-day--start' : '',
            end ? 'crp-day--end' : '',
          ]
            .filter(Boolean)
            .join(' ');

          return (
            <div
              key={cell.key}
              className={cls}
              onClick={cell.hasData ? () => handleDayClick(cell.dateStr) : undefined}
              onMouseEnter={
                cell.hasData && selectingEnd ? () => setHoverDay(cell.dateStr) : undefined
              }
              role={cell.hasData ? 'button' : undefined}
              tabIndex={cell.hasData ? 0 : undefined}
              onKeyDown={
                cell.hasData
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleDayClick(cell.dateStr);
                      }
                    }
                  : undefined
              }
            >
              {cell.day}
              {cell.hasData && <span className="crp-day-dot" />}
            </div>
          );
        })}
      </div>
    </div>
  );

  console.log('[CRP DEBUG] render — sortedDays:', sortedDays.length, 'from:', from, 'to:', to, 'open:', open);
  if (!sortedDays.length) return null;

  return (
    <div className="crp-wrapper" ref={popRef}>
      {/* Summary bar */}
      <div className="crp-bar">
        {label && <div className="crp-label">{label}</div>}

        <div className="crp-presets">
          {presets.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`crp-preset-btn ${activePreset === p.id ? 'crp-preset-active' : ''}`}
              onClick={() => applyPreset(p)}
            >
              {p.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          className="crp-trigger"
          onClick={() => {
            console.log('[CRP DEBUG] trigger button clicked, open:', open);
            setOpen((v) => !v);
            setSelectingEnd(false);
            setHoverDay(null);
          }}
        >
          <span className="crp-trigger-icon">📅</span>
          <span className="crp-trigger-range">
            {formatDateKa(effectiveFrom)} — {formatDateKa(effectiveTo)}
          </span>
          <span className="crp-trigger-count">{selectedCount} დღე</span>
          <span className="crp-trigger-arrow">{open ? '▴' : '▾'}</span>
        </button>

        {children && <div className="crp-actions">{children}</div>}
      </div>

      {/* Hint */}
      {selectingEnd && open && (
        <div className="crp-hint">აირჩიე პერიოდის ბოლო დღე</div>
      )}

      {/* Calendar popup */}
      {open && (
        <div className="crp-popup">
          <div className="crp-nav">
            <button type="button" className="crp-nav-btn" onClick={goPrev}>
              ◀
            </button>
            <div className="crp-nav-title">
              {MONTHS_KA[viewMonth]} {viewYear}
              {' — '}
              {MONTHS_KA[nextMonthIdx]} {nextMonthYear}
            </div>
            <button type="button" className="crp-nav-btn" onClick={goNext}>
              ▶
            </button>
          </div>

          <div className="crp-months-grid">
            {renderMonth(calendarDays, viewMonth, viewYear)}
            {renderMonth(calendarDays2, nextMonthIdx, nextMonthYear)}
          </div>

          <div className="crp-footer">
            <div className="crp-footer-info">
              {selectingEnd ? (
                <span className="crp-footer-selecting">
                  დაწყება: <strong>{formatDateKa(from)}</strong> → აირჩიე ბოლო
                </span>
              ) : (
                <span>
                  არჩეული: <strong>{formatDateKa(effectiveFrom)}</strong> — <strong>{formatDateKa(effectiveTo)}</strong>
                  {' '}({selectedCount} დღე)
                </span>
              )}
            </div>
            <button
              type="button"
              className="crp-done-btn"
              onClick={() => {
                setOpen(false);
                setSelectingEnd(false);
                setHoverDay(null);
              }}
            >
              მზადაა ✓
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
