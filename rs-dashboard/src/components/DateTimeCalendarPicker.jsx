import { useState, useMemo, useCallback, useRef, useEffect } from 'react';

/**
 * DateTimeCalendarPicker — ლამაზი კალენდარი თარიღის + დროის (საათი:წუთი) არჩევით.
 *
 * Props:
 *   fromDate       — "YYYY-MM-DD" start date
 *   fromTime       — "HH:MM" start time (default "00:00")
 *   toDate         — "YYYY-MM-DD" end date
 *   toTime         — "HH:MM" end time (default "23:59")
 *   onFromDateChange(value)
 *   onFromTimeChange(value)
 *   onToDateChange(value)
 *   onToTimeChange(value)
 *   label          — optional label
 */

const MONTHS_KA = [
  'იანვარი', 'თებერვალი', 'მარტი', 'აპრილი', 'მაისი', 'ივნისი',
  'ივლისი', 'აგვისტო', 'სექტემბერი', 'ოქტომბერი', 'ნოემბერი', 'დეკემბერი',
];
const MONTHS_KA_SHORT = ['იან', 'თებ', 'მარ', 'აპრ', 'მაი', 'ივნ', 'ივლ', 'აგვ', 'სექ', 'ოქტ', 'ნოე', 'დეკ'];
const WEEKDAYS_KA = ['ორშ', 'სამ', 'ოთხ', 'ხუთ', 'პარ', 'შაბ', 'კვი'];

function daysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate();
}

function firstDayOfWeek(year, month) {
  const d = new Date(year, month, 1).getDay();
  return d === 0 ? 6 : d - 1;
}

function toDateStr(y, m, d) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

function formatDateKa(dateStr) {
  if (!dateStr) return '—';
  const [y, m, d] = dateStr.split('-');
  const mi = Number(m) - 1;
  return `${Number(d)} ${MONTHS_KA_SHORT[mi] || m}, ${y}`;
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function DateTimeCalendarPicker({
  fromDate,
  fromTime = '00:00',
  toDate,
  toTime = '23:59',
  onFromDateChange,
  onFromTimeChange,
  onToDateChange,
  onToTimeChange,
  label,
}) {
  const [open, setOpen] = useState(false);
  const [selectingEnd, setSelectingEnd] = useState(false);
  const [hoverDay, setHoverDay] = useState(null);
  const popRef = useRef(null);

  const effectiveFromDate = fromDate || today();
  const effectiveToDate = toDate || today();

  const initMonth = useMemo(() => {
    const ref = fromDate || today();
    const [y, m] = ref.split('-').map(Number);
    return { year: y, month: m - 1 };
  }, [fromDate]);

  const [viewYear, setViewYear] = useState(initMonth.year);
  const [viewMonth, setViewMonth] = useState(initMonth.month);

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
        onFromDateChange(dayStr);
        onToDateChange(dayStr);
        setSelectingEnd(true);
      } else {
        if (dayStr < fromDate) {
          onFromDateChange(dayStr);
          onToDateChange(fromDate);
        } else {
          onToDateChange(dayStr);
        }
        setSelectingEnd(false);
        setHoverDay(null);
      }
    },
    [selectingEnd, fromDate, onFromDateChange, onToDateChange],
  );

  // Quick presets
  const quickPresets = useMemo(() => {
    const t = today();
    const back = (n) => {
      const d = new Date(t);
      d.setDate(d.getDate() - n);
      return d.toISOString().slice(0, 10);
    };
    return [
      { id: 'today', label: 'დღეს', from: t, to: t, ft: '00:00', tt: '23:59' },
      { id: 'yesterday', label: 'გუშინ', from: back(1), to: back(1), ft: '00:00', tt: '23:59' },
      { id: '7d', label: '7 დღე', from: back(6), to: t, ft: '00:00', tt: '23:59' },
      { id: '30d', label: '30 დღე', from: back(29), to: t, ft: '00:00', tt: '23:59' },
      { id: '90d', label: '90 დღე', from: back(89), to: t, ft: '00:00', tt: '23:59' },
    ];
  }, []);

  const applyPreset = useCallback(
    (p) => {
      onFromDateChange(p.from);
      onToDateChange(p.to);
      onFromTimeChange(p.ft);
      onToTimeChange(p.tt);
      setSelectingEnd(false);
      setHoverDay(null);
    },
    [onFromDateChange, onToDateChange, onFromTimeChange, onToTimeChange],
  );

  // Build calendar grid
  const calendarDays = useMemo(() => {
    const total = daysInMonth(viewYear, viewMonth);
    const startOffset = firstDayOfWeek(viewYear, viewMonth);
    const cells = [];

    for (let i = 0; i < startOffset; i++) {
      cells.push({ key: `empty-${i}`, day: null });
    }
    for (let d = 1; d <= total; d++) {
      const dateStr = toDateStr(viewYear, viewMonth, d);
      cells.push({ key: dateStr, day: d, dateStr });
    }
    return cells;
  }, [viewYear, viewMonth]);

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
      cells.push({ key: dateStr, day: d, dateStr });
    }
    return cells;
  }, [nextMonthYear, nextMonthIdx]);

  const isInRange = (dateStr) => {
    if (!dateStr) return false;
    if (selectingEnd && hoverDay) {
      const lo = fromDate <= hoverDay ? fromDate : hoverDay;
      const hi = fromDate <= hoverDay ? hoverDay : fromDate;
      return dateStr >= lo && dateStr <= hi;
    }
    return dateStr >= effectiveFromDate && dateStr <= effectiveToDate;
  };

  const isStart = (dateStr) => dateStr === effectiveFromDate;
  const isEnd = (dateStr) => dateStr === effectiveToDate;
  const isToday = (dateStr) => dateStr === today();

  const renderMonth = (cells, monthIdx, year) => (
    <div className="dtcp-month">
      <div className="dtcp-month-title">
        {MONTHS_KA[monthIdx]} {year}
      </div>
      <div className="dtcp-weekdays">
        {WEEKDAYS_KA.map((w) => (
          <div key={w} className="dtcp-weekday">{w}</div>
        ))}
      </div>
      <div className="dtcp-days">
        {cells.map((cell) => {
          if (!cell.day) {
            return <div key={cell.key} className="dtcp-day dtcp-day--empty" />;
          }
          const inRange = isInRange(cell.dateStr);
          const start = isStart(cell.dateStr);
          const end = isEnd(cell.dateStr);
          const todayMark = isToday(cell.dateStr);
          const cls = [
            'dtcp-day',
            inRange ? 'dtcp-day--in-range' : '',
            start ? 'dtcp-day--start' : '',
            end ? 'dtcp-day--end' : '',
            todayMark ? 'dtcp-day--today' : '',
          ]
            .filter(Boolean)
            .join(' ');

          return (
            <div
              key={cell.key}
              className={cls}
              onClick={() => handleDayClick(cell.dateStr)}
              onMouseEnter={selectingEnd ? () => setHoverDay(cell.dateStr) : undefined}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleDayClick(cell.dateStr);
                }
              }}
            >
              {cell.day}
            </div>
          );
        })}
      </div>
    </div>
  );

  // Generate hour options
  const hourOptions = [];
  for (let h = 0; h < 24; h++) {
    for (let m = 0; m < 60; m += 15) {
      hourOptions.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
    }
  }
  hourOptions.push('23:59');

  return (
    <div className="dtcp-wrapper" ref={popRef}>
      {/* Trigger bar */}
      <div className="dtcp-bar">
        {label && <div className="dtcp-label">{label}</div>}

        <button
          type="button"
          className="dtcp-trigger"
          onClick={() => {
            setOpen((v) => !v);
            setSelectingEnd(false);
            setHoverDay(null);
          }}
        >
          <span className="dtcp-trigger-icon">📅</span>
          <span className="dtcp-trigger-range">
            {formatDateKa(effectiveFromDate)} {fromTime} — {formatDateKa(effectiveToDate)} {toTime}
          </span>
          <span className="dtcp-trigger-arrow">{open ? '▴' : '▾'}</span>
        </button>
      </div>

      {/* Calendar popup */}
      {open && (
        <div className="dtcp-popup">
          {/* Quick presets */}
          <div className="dtcp-presets">
            {quickPresets.map((p) => (
              <button
                key={p.id}
                type="button"
                className="dtcp-preset-btn"
                onClick={() => applyPreset(p)}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Navigation */}
          <div className="dtcp-nav">
            <button type="button" className="dtcp-nav-btn" onClick={goPrev}>◀</button>
            <div className="dtcp-nav-title">
              {MONTHS_KA[viewMonth]} {viewYear} — {MONTHS_KA[nextMonthIdx]} {nextMonthYear}
            </div>
            <button type="button" className="dtcp-nav-btn" onClick={goNext}>▶</button>
          </div>

          {/* Calendar grids */}
          <div className="dtcp-months-grid">
            {renderMonth(calendarDays, viewMonth, viewYear)}
            {renderMonth(calendarDays2, nextMonthIdx, nextMonthYear)}
          </div>

          {/* Hint */}
          {selectingEnd && (
            <div className="dtcp-hint">აირჩიე პერიოდის ბოლო თარიღი</div>
          )}

          {/* Time selectors */}
          <div className="dtcp-time-row">
            <div className="dtcp-time-field">
              <label className="dtcp-time-label">
                <span className="dtcp-time-icon">🕐</span> დაწყება
              </label>
              <div className="dtcp-time-inputs">
                <input
                  type="date"
                  className="dtcp-date-input"
                  value={effectiveFromDate}
                  onChange={(e) => onFromDateChange(e.target.value)}
                />
                <select
                  className="dtcp-time-select"
                  value={fromTime}
                  onChange={(e) => onFromTimeChange(e.target.value)}
                >
                  {hourOptions.map((t) => (
                    <option key={`from-${t}`} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="dtcp-time-sep">→</div>

            <div className="dtcp-time-field">
              <label className="dtcp-time-label">
                <span className="dtcp-time-icon">🕐</span> დასრულება
              </label>
              <div className="dtcp-time-inputs">
                <input
                  type="date"
                  className="dtcp-date-input"
                  value={effectiveToDate}
                  onChange={(e) => onToDateChange(e.target.value)}
                />
                <select
                  className="dtcp-time-select"
                  value={toTime}
                  onChange={(e) => onToTimeChange(e.target.value)}
                >
                  {hourOptions.map((t) => (
                    <option key={`to-${t}`} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="dtcp-footer">
            <div className="dtcp-footer-info">
              <strong>{formatDateKa(effectiveFromDate)}</strong> {fromTime}
              {' — '}
              <strong>{formatDateKa(effectiveToDate)}</strong> {toTime}
            </div>
            <button
              type="button"
              className="dtcp-done-btn"
              onClick={() => {
                setOpen(false);
                setSelectingEnd(false);
                setHoverDay(null);
              }}
            >
              გამოყენება ✓
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
