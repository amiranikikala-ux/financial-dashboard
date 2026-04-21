import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';

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

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export default function DateTimeCalendarPicker({
  fromDate,
  fromTime = '00:00',
  toDate: toDateProp,
  toTime = '23:59',
  onFromDateChange,
  onFromTimeChange,
  onToDateChange,
  onToTimeChange,
  label,
}) {
  const [open, setOpen] = useState(false);
  const popRef = useRef(null);

  const hasAppliedRange = Boolean(fromDate || toDateProp);
  const effectiveFromDate = fromDate || '';
  const effectiveToDate = toDateProp || '';
  const fallbackCalendarDate = todayStr();

  const [draftFromDate, setDraftFromDate] = useState(effectiveFromDate);
  const [draftToDate, setDraftToDate] = useState(effectiveToDate);
  const [draftFromTime, setDraftFromTime] = useState(fromTime);
  const [draftToTime, setDraftToTime] = useState(toTime);

  const calendarOpenDate = toDate(draftFromDate || effectiveFromDate || fallbackCalendarDate);
  const selectedStartDate = draftFromDate ? toDate(draftFromDate) : null;
  const selectedEndDate = draftToDate ? toDate(draftToDate) : null;

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

  // Quick presets
  const quickPresets = useMemo(() => {
    const t = todayStr();
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
      setDraftFromDate(p.from);
      setDraftToDate(p.to);
      setDraftFromTime(p.ft);
      setDraftToTime(p.tt);
    },
    [],
  );

  const activeQuickPreset = useMemo(() => {
    const nextToDate = draftToDate || draftFromDate;
    for (const preset of quickPresets) {
      if (
        preset.from === draftFromDate
        && preset.to === nextToDate
        && preset.ft === draftFromTime
        && preset.tt === draftToTime
      ) {
        return preset.id;
      }
    }
    return null;
  }, [quickPresets, draftFromDate, draftToDate, draftFromTime, draftToTime]);

  const handleDateChange = useCallback(
    ([start, end]) => {
      if (!start) {
        setDraftFromDate('');
        setDraftToDate('');
        return;
      }

      setDraftFromDate(toStr(start));
      setDraftToDate(end ? toStr(end) : '');
    },
    [],
  );

  const applyDraft = useCallback(() => {
    const nextFromDate = draftFromDate || draftToDate || '';
    const nextToDate = draftToDate || draftFromDate || '';

    onFromDateChange(nextFromDate);
    onToDateChange(nextToDate);
    onFromTimeChange(nextFromDate ? (draftFromTime || '00:00') : '00:00');
    onToTimeChange(nextToDate ? (draftToTime || '23:59') : '23:59');
    setOpen(false);
  }, [
    draftFromDate,
    draftToDate,
    draftFromTime,
    draftToTime,
    onFromDateChange,
    onFromTimeChange,
    onToDateChange,
    onToTimeChange,
  ]);

  const handleClear = useCallback(() => {
    setDraftFromDate('');
    setDraftToDate('');
    setDraftFromTime('00:00');
    setDraftToTime('23:59');
    onFromDateChange('');
    onToDateChange('');
    onFromTimeChange('00:00');
    onToTimeChange('23:59');
    setOpen(false);
  }, [onFromDateChange, onFromTimeChange, onToDateChange, onToTimeChange]);

  const handleTriggerClick = useCallback(() => {
    if (open) {
      setOpen(false);
      return;
    }

    setDraftFromDate(effectiveFromDate);
    setDraftToDate(effectiveToDate);
    setDraftFromTime(fromTime);
    setDraftToTime(toTime);
    setOpen(true);
  }, [effectiveFromDate, effectiveToDate, fromTime, open, toTime]);

  const handleCancel = useCallback(() => {
    setDraftFromDate(effectiveFromDate);
    setDraftToDate(effectiveToDate);
    setDraftFromTime(fromTime);
    setDraftToTime(toTime);
    setOpen(false);
  }, [effectiveFromDate, effectiveToDate, fromTime, toTime]);

  // Generate hour options
  const hourOptions = useMemo(() => {
    const opts = [];
    for (let h = 0; h < 24; h++) {
      for (let m = 0; m < 60; m += 15) {
        opts.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
      }
    }
    opts.push('23:59');
    return opts;
  }, []);

  const triggerRangeText = hasAppliedRange
    ? `${formatDateKa(effectiveFromDate || effectiveToDate)} ${fromTime} — ${formatDateKa(effectiveToDate || effectiveFromDate)} ${toTime}`
    : 'ყველა პერიოდი';

  const footerSelectionText = (draftFromDate || draftToDate)
    ? (
      <>
        არჩეული: <strong>{formatDateKa(draftFromDate || draftToDate)}</strong> {draftFromTime || '00:00'}
        {' — '}
        <strong>{formatDateKa(draftToDate || draftFromDate)}</strong> {draftToTime || '23:59'}
      </>
    )
    : 'ფილტრი გამორთულია';

  return (
    <div className="dtcp-wrapper" ref={popRef}>
      {/* Trigger bar */}
      <div className="dtcp-bar">
        {label && <div className="dtcp-label">{label}</div>}

        <button
          type="button"
          className="dtcp-trigger"
          onClick={handleTriggerClick}
        >
          <span className="dtcp-trigger-icon">📅</span>
          <span className="dtcp-trigger-range">
            {triggerRangeText}
          </span>
          <span className="dtcp-trigger-arrow">{open ? '▴' : '▾'}</span>
        </button>
      </div>

      {/* Calendar popup */}
      {open && (
        <div className="dtcp-popup dtcp-popup--classic">
          <button
            type="button"
            className="classic-cal__close"
            onClick={handleCancel}
            aria-label="Close calendar"
          >
            ×
          </button>
          {/* Quick presets */}
          <div className="dtcp-calendar-panel dtcp-calendar-panel--classic">
            <DatePicker
              selected={selectedStartDate}
              onChange={handleDateChange}
              startDate={selectedStartDate}
              endDate={selectedEndDate}
              openToDate={selectedStartDate || selectedEndDate || calendarOpenDate}
              selectsRange
              inline
              monthsShown={1}
              formatWeekDay={formatWeekDayKa}
              renderCustomHeader={renderDesktopHeader}
              calendarClassName="dtcp-rdp classic-inline-datepicker"
            />
          </div>

          <div className="dtcp-presets dtcp-presets--classic">
            {quickPresets.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`dtcp-preset-btn ${activeQuickPreset === p.id ? 'dtcp-preset-active' : ''}`}
                onClick={() => applyPreset(p)}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Time selectors */}
          <div className="dtcp-time-row dtcp-time-row--classic">
            <div className="dtcp-time-field">
              <label className="dtcp-time-label">დაწყება</label>
              <div className="dtcp-time-inputs">
                <div className="dtcp-date-pill">{draftFromDate ? formatDateKa(draftFromDate) : 'არ არის არჩეული'}</div>
                <select
                  className="dtcp-time-select"
                  value={draftFromTime}
                  onChange={(e) => setDraftFromTime(e.target.value)}
                >
                  {hourOptions.map((t) => (
                    <option key={`from-${t}`} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="dtcp-time-sep">→</div>

            <div className="dtcp-time-field">
              <label className="dtcp-time-label">დასრულება</label>
              <div className="dtcp-time-inputs">
                <div className="dtcp-date-pill">{draftToDate || draftFromDate ? formatDateKa(draftToDate || draftFromDate) : 'არ არის არჩეული'}</div>
                <select
                  className="dtcp-time-select"
                  value={draftToTime}
                  onChange={(e) => setDraftToTime(e.target.value)}
                >
                  {hourOptions.map((t) => (
                    <option key={`to-${t}`} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="dtcp-footer dtcp-footer--classic">
            <div className="dtcp-footer-info">
              {footerSelectionText}
            </div>
            <div className="dtcp-footer-actions">
              <button
                type="button"
                className="dtcp-cancel-btn"
                onClick={handleClear}
              >
                გასუფთავება
              </button>
              <button
                type="button"
                className="dtcp-cancel-btn"
                onClick={handleCancel}
              >
                არა
              </button>
              <button
                type="button"
                className="dtcp-done-btn dtcp-done-btn--classic"
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
