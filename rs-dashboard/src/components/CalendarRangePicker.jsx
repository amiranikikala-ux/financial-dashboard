import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';

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

const MONTHS_KA_SHORT = ['იან', 'თებ', 'მარ', 'აპრ', 'მაი', 'ივნ', 'ივლ', 'აგვ', 'სექ', 'ოქტ', 'ნოე', 'დეკ'];
const MONTHS_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const WEEKDAYS_KA = {
  Sunday: 'კვირა',
  Sun: 'კვირა',
  Monday: 'ორშ.',
  Mon: 'ორშ.',
  Tuesday: 'სამშ.',
  Tue: 'სამშ.',
  Wednesday: 'ოთხშ.',
  Wed: 'ოთხშ.',
  Thursday: 'ხუთშ.',
  Thu: 'ხუთშ.',
  Friday: 'პარ',
  Fri: 'პარ',
  Saturday: 'შაბ',
  Sat: 'შაბ',
  Su: 'კვირა',
  Mo: 'ორშ.',
  Tu: 'სამშ.',
  We: 'ოთხშ.',
  Th: 'ხუთშ.',
  Fr: 'პარ',
  Sa: 'შაბ',
};

function formatWeekDayKa(nameOfDay) {
  return WEEKDAYS_KA[nameOfDay] || nameOfDay;
}

function renderDesktopHeader({
  date,
  changeMonth,
  changeYear,
  decreaseMonth,
  increaseMonth,
  prevMonthButtonDisabled,
  nextMonthButtonDisabled,
}) {
  return (
    <div className="classic-cal__header">
      <div className="classic-cal__month-box">
        <select
          className="classic-cal__month-select"
          value={date.getMonth()}
          onChange={(e) => changeMonth(Number(e.target.value))}
        >
          {MONTHS_EN.map((month, index) => (
            <option key={month} value={index}>{month}</option>
          ))}
        </select>
      </div>
      <div className="classic-cal__spin-group">
        <button
          type="button"
          className="classic-cal__spin-btn"
          onClick={increaseMonth}
          disabled={nextMonthButtonDisabled}
          aria-label="Next month"
        >
          ▲
        </button>
        <button
          type="button"
          className="classic-cal__spin-btn"
          onClick={decreaseMonth}
          disabled={prevMonthButtonDisabled}
          aria-label="Previous month"
        >
          ▼
        </button>
      </div>
      <div className="classic-cal__year-box">{date.getFullYear()}</div>
      <div className="classic-cal__spin-group">
        <button
          type="button"
          className="classic-cal__spin-btn"
          onClick={() => changeYear(date.getFullYear() + 1)}
          aria-label="Next year"
        >
          ▲
        </button>
        <button
          type="button"
          className="classic-cal__spin-btn"
          onClick={() => changeYear(date.getFullYear() - 1)}
          aria-label="Previous year"
        >
          ▼
        </button>
      </div>
    </div>
  );
}

function toStr(date) {
  if (!date) return '';
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function toDate(str) {
  if (!str) return null;
  const [y, m, d] = str.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function formatDateKa(dateStr) {
  if (!dateStr) return '—';
  const [y, m, d] = dateStr.split('-');
  const mi = Number(m) - 1;
  return `${Number(d)} ${MONTHS_KA_SHORT[mi] || m}, ${y}`;
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
  const popRef = useRef(null);

  const sortedDays = useMemo(() => [...availableDays].sort(), [availableDays]);
  const daySet = useMemo(() => new Set(sortedDays), [sortedDays]);

  const firstAvail = sortedDays[0] || '';
  const lastAvail = sortedDays[sortedDays.length - 1] || '';

  const presets = useMemo(() => getPresets(sortedDays), [sortedDays]);

  const effectiveFrom = from || firstAvail;
  const effectiveTo = to || lastAvail;

  const [draftFrom, setDraftFrom] = useState(effectiveFrom);
  const [draftTo, setDraftTo] = useState(effectiveTo);

  const visibleFrom = open ? (draftFrom || effectiveFrom) : effectiveFrom;
  const visibleTo = open ? (draftTo || draftFrom || effectiveTo) : effectiveTo;
  const selectedCount = sortedDays.filter((d) => d >= visibleFrom && d <= visibleTo).length;

  const startDate = toDate(draftFrom || effectiveFrom);
  const endDate = draftTo ? toDate(draftTo) : null;

  // Highlighted available days for react-datepicker
  const highlightDates = useMemo(() => sortedDays.map((d) => toDate(d)), [sortedDays]);

  // Filter: only allow clicking on available days
  const filterDate = useCallback((date) => daySet.has(toStr(date)), [daySet]);

  const activePreset = useMemo(() => {
    for (const p of presets) {
      const targetTo = draftTo || draftFrom || effectiveTo;
      if (p.from === (draftFrom || effectiveFrom) && p.to === targetTo) return p.id;
    }
    return null;
  }, [presets, draftFrom, draftTo, effectiveFrom, effectiveTo]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (popRef.current && !popRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const applyPreset = useCallback(
    (p) => {
      setDraftFrom(p.from);
      setDraftTo(p.to);
    },
    [],
  );

  const handleDateChange = useCallback(
    ([start, end]) => {
      if (!start) {
        setDraftFrom('');
        setDraftTo('');
        return;
      }

      setDraftFrom(toStr(start));
      setDraftTo(end ? toStr(end) : '');
    },
    [],
  );

  const handleTriggerClick = useCallback(() => {
    if (open) {
      setOpen(false);
      return;
    }

    setDraftFrom(effectiveFrom);
    setDraftTo(effectiveTo);
    setOpen(true);
  }, [effectiveFrom, effectiveTo, open]);

  const handleCancel = useCallback(() => {
    setDraftFrom(effectiveFrom);
    setDraftTo(effectiveTo);
    setOpen(false);
  }, [effectiveFrom, effectiveTo]);

  const applyDraft = useCallback(() => {
    const nextFrom = draftFrom || effectiveFrom;
    const nextTo = draftTo || draftFrom || effectiveTo;
    onFromChange(nextFrom);
    onToChange(nextTo);
    setOpen(false);
  }, [draftFrom, draftTo, effectiveFrom, effectiveTo, onFromChange, onToChange]);

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
          onClick={handleTriggerClick}
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

      {/* Calendar popup */}
      {open && (
        <div className="crp-popup crp-popup--classic">
          <button
            type="button"
            className="classic-cal__close"
            onClick={handleCancel}
            aria-label="Close calendar"
          >
            ×
          </button>
          <DatePicker
            selected={startDate}
            onChange={handleDateChange}
            startDate={startDate}
            endDate={endDate}
            selectsRange
            inline
            monthsShown={1}
            filterDate={filterDate}
            highlightDates={highlightDates}
            formatWeekDay={formatWeekDayKa}
            renderCustomHeader={renderDesktopHeader}
            calendarClassName="crp-rdp classic-inline-datepicker"
          />

          <div className="crp-presets crp-presets--classic">
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

          <div className="crp-footer crp-footer--classic">
            <div className="crp-footer-info">
              <span>
                არჩეული: <strong>{formatDateKa(visibleFrom)}</strong> — <strong>{formatDateKa(visibleTo)}</strong>
                {' '}({selectedCount} დღე)
              </span>
            </div>
            <div className="crp-footer-actions">
              <button
                type="button"
                className="crp-cancel-btn"
                onClick={handleCancel}
              >
                არა
              </button>
              <button
                type="button"
                className="crp-done-btn crp-done-btn--classic"
                onClick={applyDraft}
              >
                კი
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
