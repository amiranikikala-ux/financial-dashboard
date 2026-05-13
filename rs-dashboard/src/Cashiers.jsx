import { useMemo, useState, useEffect, useRef } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';

const N = new Intl.NumberFormat('ka-GE');
const fmtN = (v) => N.format(Number(v) || 0);
const fmt2 = (v) => {
  const n = Number(v);
  if (!isFinite(n)) return '0.00';
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const MONTHS_EN = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const WK_KA = {
  Su:'კვ', Mo:'ორშ', Tu:'სამშ', We:'ოთხშ', Th:'ხუთშ', Fr:'პარ', Sa:'შაბ',
  Sun:'კვ', Mon:'ორშ', Tue:'სამშ', Wed:'ოთხშ', Thu:'ხუთშ', Fri:'პარ', Sat:'შაბ',
  Sunday:'კვ', Monday:'ორშ', Tuesday:'სამშ', Wednesday:'ოთხშ', Thursday:'ხუთშ', Friday:'პარ', Saturday:'შაბ',
};

function toIso(date, time, fallback) {
  if (!date) return null;
  return `${date}T${time || fallback}:00`;
}
function inRange(iso, fromIso, toIso) {
  if (!iso) return false;
  if (fromIso && iso < fromIso) return false;
  if (toIso && iso > toIso) return false;
  return true;
}
function dateToStr(d) {
  if (!d) return '';
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
function strToDate(s) {
  if (!s) return null;
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}
function fmtToolbarDate(date, time) {
  if (!date) return '';
  const [y, m, d] = date.split('-');
  return `${y.slice(2)}/${m}/${d} ${time || '00:00'}`;
}
function hourOptions() {
  const opts = [];
  for (let h = 0; h < 24; h++) {
    for (let mi = 0; mi < 60; mi += 15) {
      opts.push(`${String(h).padStart(2,'0')}:${String(mi).padStart(2,'0')}`);
    }
  }
  opts.push('23:59');
  return opts;
}

function lastFullyLoadedDay(retailSales) {
  // Latest day in cashier_day_breakdown (calendar-day, MegaPlus-aligned).
  const cdb = Array.isArray(retailSales?.cashier_day_breakdown) ? retailSales.cashier_day_breakdown : [];
  let maxDate = '';
  cdb.forEach((r) => {
    const d = (r.day || '').slice(0, 10);
    if (d && d > maxDate) maxDate = d;
  });
  return maxDate;
}

export default function Cashiers({ retailSales, fromDate, fromTime, toDate, toTime }) {
  const defaultDay = useMemo(() => lastFullyLoadedDay(retailSales), [retailSales]);
  const [localFrom, setLocalFrom] = useState(fromDate || defaultDay || '');
  const [localFromT, setLocalFromT] = useState(fromTime || '00:00');
  const [localTo, setLocalTo] = useState(toDate || defaultDay || '');
  const [localToT, setLocalToT] = useState(toTime || '23:59');
  const [cashierFilter, setCashierFilter] = useState('all');
  const [storeFilter, setStoreFilter] = useState('all');
  const [pickerOpen, setPickerOpen] = useState(false);

  const popRef = useRef(null);
  const toolbarRef = useRef(null);

  useEffect(() => {
    if (!pickerOpen) return;
    const handler = (e) => {
      if (popRef.current && !popRef.current.contains(e.target) &&
          toolbarRef.current && !toolbarRef.current.contains(e.target)) {
        setPickerOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [pickerOpen]);

  useEffect(() => {
    setCashierFilter('all');
  }, [storeFilter]);

  const periodActive = !!(localFrom || localTo);
  const fromIso = periodActive ? toIso(localFrom || localTo, localFromT, '00:00') : null;
  const toIsoStr = periodActive ? toIso(localTo || localFrom, localToT, '23:59') : null;

  const cashiersLifetime = useMemo(() => {
    return Array.isArray(retailSales?.cashiers_per_object) ? retailSales.cashiers_per_object : [];
  }, [retailSales]);
  const cashierDays = useMemo(() => {
    return Array.isArray(retailSales?.cashier_day_breakdown) ? retailSales.cashier_day_breakdown : [];
  }, [retailSales]);
  const cashierHours = useMemo(() => {
    return Array.isArray(retailSales?.cashier_hour_breakdown) ? retailSales.cashier_hour_breakdown : [];
  }, [retailSales]);
  const paymentLifetime = useMemo(() => {
    const pb = Array.isArray(retailSales?.payment_breakdown) ? retailSales.payment_breakdown : [];
    let cash = 0, card = 0;
    pb.forEach((r) => {
      if (r.pay_typ === 0) cash += Number(r.revenue_ge) || 0;
      else if (r.pay_typ === 1) card += Number(r.revenue_ge) || 0;
    });
    return { cash, card };
  }, [retailSales]);

  const rows = useMemo(() => {
    let raw;
    if (periodActive) {
      const fromDay = (localFrom || localTo).slice(0, 10);
      const toDay = (localTo || localFrom).slice(0, 10);
      const filtered = cashierDays.filter((r) => {
        const d = (r.day || '').slice(0, 10);
        return d && d >= fromDay && d <= toDay;
      });
      const byKey = new Map();
      filtered.forEach((r) => {
        const key = `${r.user_id}|${r.object}`;
        if (!byKey.has(key)) {
          byKey.set(key, {
            user_id: r.user_id,
            cashier_name: r.cashier_name || null,
            object: r.object || '—',
            cash: 0, card: 0, revenue: 0, receipts: 0, lines: 0,
          });
        }
        const acc = byKey.get(key);
        if (!acc.cashier_name && r.cashier_name) acc.cashier_name = r.cashier_name;
        acc.cash += Number(r.cash) || 0;
        acc.card += Number(r.card) || 0;
        acc.revenue += Number(r.revenue) || 0;
        acc.receipts += Number(r.receipts) || 0;
        acc.lines += Number(r.lines) || 0;
      });
      raw = Array.from(byKey.values());
    } else {
      raw = cashiersLifetime.map((c) => ({
        user_id: c.user_id,
        cashier_name: c.cashier_name || null,
        object: c.object || '—',
        cash: null,
        card: null,
        revenue: Number(c.revenue) || 0,
        receipts: Number(c.receipts) || 0,
        lines: Number(c.lines) || 0,
      }));
    }
    return raw
      .filter((r) => (storeFilter === 'all' || r.object === storeFilter))
      .filter((r) => (cashierFilter === 'all' || String(r.user_id) === cashierFilter))
      .sort((a, b) => b.revenue - a.revenue);
  }, [periodActive, localFrom, localTo, cashierDays, cashiersLifetime, cashierFilter, storeFilter]);

  // Per-cashier active-hour count + 24-hour distribution. Driven by
  // cashier_hour_breakdown (last 180 days). Outside that window TPH falls back
  // to a per-row "—" marker.
  const tphByKey = useMemo(() => {
    const map = new Map();
    if (!periodActive) return map;
    const fromDay = (localFrom || localTo).slice(0, 10);
    const toDay = (localTo || localFrom).slice(0, 10);
    cashierHours.forEach((r) => {
      const d = (r.day || '').slice(0, 10);
      if (!d || d < fromDay || d > toDay) return;
      if (storeFilter !== 'all' && r.object !== storeFilter) return;
      if (cashierFilter !== 'all' && String(r.user_id) !== cashierFilter) return;
      const key = `${r.user_id}|${r.object}`;
      const acc = map.get(key) || { hours: 0, receipts: 0 };
      acc.hours += 1;
      acc.receipts += Number(r.receipts) || 0;
      map.set(key, acc);
    });
    return map;
  }, [cashierHours, periodActive, localFrom, localTo, storeFilter, cashierFilter]);

  const hourlyDistribution = useMemo(() => {
    const buckets = Array(24).fill(0);
    const receiptsB = Array(24).fill(0);
    if (!periodActive) return { buckets, receiptsB, anyData: false };
    const fromDay = (localFrom || localTo).slice(0, 10);
    const toDay = (localTo || localFrom).slice(0, 10);
    let any = false;
    cashierHours.forEach((r) => {
      const d = (r.day || '').slice(0, 10);
      if (!d || d < fromDay || d > toDay) return;
      if (storeFilter !== 'all' && r.object !== storeFilter) return;
      if (cashierFilter !== 'all' && String(r.user_id) !== cashierFilter) return;
      const h = Number(r.hour);
      if (h < 0 || h > 23) return;
      buckets[h] += Number(r.revenue) || 0;
      receiptsB[h] += Number(r.receipts) || 0;
      any = true;
    });
    return { buckets, receiptsB, anyData: any };
  }, [cashierHours, periodActive, localFrom, localTo, storeFilter, cashierFilter]);

  const analysisRows = useMemo(() => {
    return rows.map((r, idx) => {
      const key = `${r.user_id}|${r.object}`;
      const aov = r.receipts > 0 ? r.revenue / r.receipts : 0;
      const cashTotal = (Number(r.cash) || 0) + (Number(r.card) || 0);
      const cashPct = cashTotal > 0 ? (Number(r.cash) || 0) / cashTotal * 100 : null;
      const tph = tphByKey.get(key);
      const tphVal = tph && tph.hours > 0 ? tph.receipts / tph.hours : null;
      return {
        ...r,
        rank: idx + 1,
        aov,
        cashPct,
        tph: tphVal,
      };
    });
  }, [rows, tphByKey]);

  const maxHourRev = useMemo(() => {
    return Math.max(0, ...hourlyDistribution.buckets);
  }, [hourlyDistribution]);

  const stores = useMemo(() => {
    const s = new Set();
    cashiersLifetime.forEach((c) => c.object && s.add(c.object));
    cashierDays.forEach((r) => r.object && s.add(r.object));
    return Array.from(s).sort();
  }, [cashiersLifetime, cashierDays]);

  const cashierIds = useMemo(() => {
    const m = new Map();
    const matchStore = (obj) => storeFilter === 'all' || obj === storeFilter;
    cashiersLifetime.forEach((c) => {
      if (c.user_id != null && matchStore(c.object)) {
        m.set(String(c.user_id), c.cashier_name || null);
      }
    });
    cashierDays.forEach((r) => {
      if (r.user_id != null && matchStore(r.object) && r.cashier_name) {
        if (!m.get(String(r.user_id))) m.set(String(r.user_id), r.cashier_name);
      }
    });
    return Array.from(m.entries())
      .sort((a, b) => Number(a[0]) - Number(b[0]))
      .map(([id, name]) => ({ id, name }));
  }, [cashiersLifetime, cashierDays, storeFilter]);

  const totals = useMemo(() => {
    const revenue = rows.reduce((a, r) => a + r.revenue, 0);
    const receipts = rows.reduce((a, r) => a + r.receipts, 0);
    const cash = rows.reduce((a, r) => a + (Number(r.cash) || 0), 0);
    const card = rows.reduce((a, r) => a + (Number(r.card) || 0), 0);
    return { revenue, receipts, cash, card, aov: receipts > 0 ? revenue / receipts : 0 };
  }, [rows]);

  const lifetimeShare = useMemo(() => {
    const total = paymentLifetime.cash + paymentLifetime.card;
    return total > 0 ? { cashPct: paymentLifetime.cash / total, cardPct: paymentLifetime.card / total } : null;
  }, [paymentLifetime]);

  // Period: use actual per-row cash/card sums. Lifetime: use payment_breakdown.
  const kpiCash = periodActive ? totals.cash : paymentLifetime.cash;
  const kpiCard = periodActive ? totals.card : paymentLifetime.card;
  const kpiTotal = periodActive ? totals.revenue : (paymentLifetime.cash + paymentLifetime.card);

  const handleCalendarRange = (range) => {
    const [start, end] = range || [];
    setLocalFrom(start ? dateToStr(start) : '');
    setLocalTo(end ? dateToStr(end) : '');
  };

  const clearRange = () => {
    setLocalFrom('');
    setLocalTo('');
    setLocalFromT('00:00');
    setLocalToT('23:59');
    setPickerOpen(false);
  };

  const opts = hourOptions();
  const fromDisplay = fmtToolbarDate(localFrom, localFromT);
  const toDisplay = fmtToolbarDate(localTo || localFrom, localToT);

  return (
    <div className="salaro-page">
      <style>{`
        .salaro-page { font-family: inherit; color: var(--text-primary); }
        .salaro-page .sl-titlebar { display:flex; align-items:center; gap:8px; padding: 4px 0 10px; font-size: 14px; color: var(--text-secondary); }
        .salaro-page .sl-icon { width:18px; height:18px; border-radius:4px; background: linear-gradient(135deg,#7a73ff,#4f46e5); display:inline-block; }
        .salaro-page .sl-toolbar {
          background: rgba(15,23,42,0.6);
          border: 1px solid var(--border-color);
          border-radius: 10px;
          padding: 10px 12px;
          display: flex; align-items: center; gap: 8px;
          margin-bottom: 12px;
          flex-wrap: wrap; position: relative;
        }
        .salaro-page .sl-btn {
          width: 32px; height: 32px;
          border: 1px solid var(--border-color);
          border-radius: 8px;
          background: rgba(255,255,255,0.04);
          cursor: pointer; flex-shrink:0;
          display:flex; align-items:center; justify-content:center;
          color: var(--text-secondary); font-size: 14px;
          transition: background 0.15s;
        }
        .salaro-page .sl-btn:hover { background: rgba(255,255,255,0.08); }
        .salaro-page .sl-btn-play { color: #6366f1; }
        .salaro-page .sl-btn-up { color: #22c55e; }
        .salaro-page .sl-date {
          background: rgba(0,0,0,0.25);
          border: 1px solid var(--border-color);
          color: var(--text-primary);
          padding: 0 10px; height: 32px;
          font-family: inherit; font-size: 13px;
          width: 150px; border-radius: 8px;
          cursor: pointer; font-variant-numeric: tabular-nums;
        }
        .salaro-page .sl-date:hover { background: rgba(255,255,255,0.04); }
        .salaro-page .sl-date::placeholder { color: var(--text-tertiary); }
        .salaro-page .sl-select {
          background: rgba(0,0,0,0.25);
          border: 1px solid var(--border-color);
          color: var(--text-primary);
          padding: 0 28px 0 10px; height: 32px;
          font-family: inherit; font-size: 13px;
          min-width: 140px; border-radius: 8px;
          cursor: pointer; appearance: none;
          background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><polygon points='0,0 10,0 5,6' fill='%2394a3b8'/></svg>");
          background-repeat: no-repeat;
          background-position: right 10px center;
          margin-left: auto;
        }

        .salaro-page .sl-tablewrap {
          background: rgba(15,23,42,0.5);
          border: 1px solid var(--border-color);
          border-radius: 10px;
          overflow: hidden; margin-bottom: 12px;
          min-height: 220px;
        }
        .salaro-page table.sl-table {
          width: 100%; border-collapse: collapse; font-size: 13px;
        }
        .salaro-page .sl-table thead th {
          background: rgba(15,23,42,0.8) !important;
          color: var(--text-tertiary) !important;
          text-align: left; padding: 10px 14px;
          font-size: 11px; font-weight: 600;
          text-transform: uppercase; letter-spacing: 0.05em;
          border-bottom: 1px solid var(--border-subtle);
          position: static !important;
        }
        .salaro-page .sl-table tbody td {
          padding: 11px 14px;
          color: var(--text-primary);
          font-variant-numeric: tabular-nums;
          border-bottom: 1px solid var(--border-subtle);
        }
        .salaro-page .sl-table tbody tr:last-child td { border-bottom: none; }
        .salaro-page .sl-table tbody tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
        .salaro-page .sl-table tbody tr:hover td { background: rgba(99,102,241,0.06); }
        .salaro-page .sl-name { color: var(--text-primary); font-weight: 500; }
        .salaro-page .sl-num { font-variant-numeric: tabular-nums; }
        .salaro-page .sl-muted { color: var(--text-tertiary); }

        .salaro-page .sl-empty { text-align:center; padding: 50px 10px; color: var(--text-tertiary); }

        .salaro-page .sl-boxes {
          display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px;
          background: rgba(15,23,42,0.4);
          border: 1px solid var(--border-color);
          border-radius: 10px;
          padding: 10px;
        }
        .salaro-page .sl-box {
          background: rgba(0,0,0,0.25);
          border: 1px solid var(--border-subtle);
          border-radius: 8px;
          padding: 10px 8px; text-align: center;
        }
        .salaro-page .sl-box-val {
          font-size: 16px; font-weight: 600;
          color: var(--text-primary);
          font-variant-numeric: tabular-nums;
          letter-spacing: -0.01em;
        }
        .salaro-page .sl-box-lbl {
          font-size: 10.5px; color: var(--text-tertiary);
          margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;
        }
        .salaro-page .sl-box-total .sl-box-val { color: #a5b4fc; }
        .salaro-page .sl-box-total { background: rgba(99,102,241,0.08); border-color: rgba(99,102,241,0.25); }

        .salaro-page .sl-note {
          margin-top: 10px; padding: 8px 12px;
          font-size: 11.5px; color: var(--text-tertiary);
          background: rgba(245,158,11,0.06);
          border: 1px solid rgba(245,158,11,0.18);
          border-radius: 8px; line-height: 1.5;
        }

        .salaro-page .sl-section { margin-top: 18px; }
        .salaro-page .sl-section-title {
          font-size: 13px; font-weight: 600; color: var(--text-secondary);
          padding: 4px 0 8px; letter-spacing: 0.01em;
          display: flex; align-items: center; gap: 8px;
        }
        .salaro-page .sl-section-title .sl-icon { width: 14px; height: 14px; }
        .salaro-page .sl-section-sub {
          font-size: 11px; color: var(--text-tertiary); font-weight: 400; margin-left: 6px;
        }

        .salaro-page .sl-table .sl-rank {
          color: var(--text-tertiary); font-weight: 600; width: 36px; text-align: center;
        }
        .salaro-page .sl-table .sl-rank-1 { color: #fbbf24; }
        .salaro-page .sl-table .sl-rank-2 { color: #cbd5e1; }
        .salaro-page .sl-table .sl-rank-3 { color: #d97706; }
        .salaro-page .sl-delta-up { color: #22c55e; }
        .salaro-page .sl-delta-down { color: #ef4444; }
        .salaro-page .sl-delta-new { color: #818cf8; font-size: 11.5px; }
        .salaro-page .sl-pct-bar {
          display: inline-block; position: relative; width: 60px; height: 6px;
          background: rgba(255,255,255,0.05); border-radius: 3px; vertical-align: middle;
          margin-left: 6px; overflow: hidden;
        }
        .salaro-page .sl-pct-bar-fill {
          position: absolute; left: 0; top: 0; bottom: 0; background: #6366f1; border-radius: 3px;
        }

        .salaro-page .sl-hourchart {
          background: rgba(15,23,42,0.5); border: 1px solid var(--border-color);
          border-radius: 10px; padding: 14px 12px 10px;
        }
        .salaro-page .sl-hour-row { display: flex; align-items: flex-end; gap: 3px; height: 100px; }
        .salaro-page .sl-hour-bar {
          flex: 1; background: rgba(99,102,241,0.65); border-radius: 3px 3px 0 0;
          min-height: 2px; position: relative; transition: background 0.15s;
        }
        .salaro-page .sl-hour-bar:hover { background: rgba(99,102,241,0.95); }
        .salaro-page .sl-hour-bar-empty {
          flex: 1; background: rgba(255,255,255,0.03); border-radius: 3px 3px 0 0; min-height: 2px;
        }
        .salaro-page .sl-hour-labels {
          display: flex; gap: 3px; margin-top: 4px;
          font-size: 10px; color: var(--text-tertiary); font-variant-numeric: tabular-nums;
        }
        .salaro-page .sl-hour-labels span { flex: 1; text-align: center; }
        .salaro-page .sl-hour-empty {
          text-align: center; color: var(--text-tertiary); padding: 30px 10px; font-size: 12px;
        }

        /* Calendar popup */
        .salaro-page .sl-pop {
          position: absolute; top: calc(100% + 6px); left: 12px; z-index: 50;
          background: #0f172a;
          border: 1px solid var(--border-color);
          border-radius: 10px;
          box-shadow: 0 8px 28px rgba(0,0,0,0.45);
          padding: 10px; min-width: 320px;
        }
        .salaro-page .sl-pop .react-datepicker {
          background: transparent !important;
          border: none !important;
          font-family: inherit !important;
          color: var(--text-primary) !important;
        }
        .salaro-page .sl-pop .react-datepicker__month-container { background: transparent; }
        .salaro-page .sl-pop .react-datepicker__header {
          background: rgba(255,255,255,0.04) !important;
          border-bottom: 1px solid var(--border-subtle) !important;
          padding-top: 6px !important;
        }
        .salaro-page .sl-pop .react-datepicker__current-month {
          color: var(--text-secondary) !important;
        }
        .salaro-page .sl-pop .react-datepicker__day-names {
          display: flex; justify-content: space-between; padding: 4px 0;
        }
        .salaro-page .sl-pop .react-datepicker__day-name {
          color: var(--text-tertiary) !important;
          width: 36px !important; font-size: 11px !important; font-weight: 600 !important;
          text-transform: uppercase; letter-spacing: 0.03em;
        }
        .salaro-page .sl-pop .react-datepicker__week {
          display: flex; justify-content: space-between;
        }
        .salaro-page .sl-pop .react-datepicker__day {
          width: 36px !important; height: 32px !important; line-height: 32px !important;
          margin: 1px !important;
        }
        .salaro-page .sl-pop .react-datepicker__day {
          color: var(--text-primary) !important;
          border-radius: 6px !important;
        }
        .salaro-page .sl-pop .react-datepicker__day:hover {
          background: rgba(99,102,241,0.15) !important;
        }
        .salaro-page .sl-pop .react-datepicker__day--outside-month {
          color: var(--text-muted, #475569) !important;
        }
        .salaro-page .sl-pop .react-datepicker__day--selected,
        .salaro-page .sl-pop .react-datepicker__day--in-selecting-range,
        .salaro-page .sl-pop .react-datepicker__day--in-range,
        .salaro-page .sl-pop .react-datepicker__day--range-start,
        .salaro-page .sl-pop .react-datepicker__day--range-end {
          background: #6366f1 !important;
          color: #fff !important;
        }
        .salaro-page .sl-pop .react-datepicker__day--keyboard-selected {
          background: rgba(99,102,241,0.25) !important;
          color: var(--text-primary) !important;
        }
        .salaro-page .sl-cal-header {
          display:flex; align-items:center; justify-content:center; gap:6px; padding: 4px 6px 6px;
        }
        .salaro-page .sl-cal-nav {
          width:24px; height:24px; border:1px solid var(--border-color); border-radius:6px;
          background: rgba(255,255,255,0.04); color: var(--text-secondary);
          cursor: pointer; font-size: 14px;
        }
        .salaro-page .sl-cal-select, .salaro-page .sl-cal-year {
          background: rgba(0,0,0,0.3); border: 1px solid var(--border-color);
          color: var(--text-primary); padding: 2px 6px; font-size: 12px; height: 24px; border-radius: 6px;
        }
        .salaro-page .sl-cal-year { width: 64px; }

        .salaro-page .sl-time-row {
          display:flex; gap: 10px; padding: 10px 4px 4px;
          border-top: 1px solid var(--border-subtle); margin-top: 8px;
        }
        .salaro-page .sl-time-field { flex: 1; display: flex; flex-direction: column; gap: 4px; }
        .salaro-page .sl-time-lbl {
          font-size: 10.5px; color: var(--text-tertiary);
          text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;
        }
        .salaro-page .sl-time-sel {
          background: rgba(0,0,0,0.3); border: 1px solid var(--border-color);
          color: var(--text-primary); padding: 5px 8px; font-size: 12px; height: 28px; border-radius: 6px;
        }
        .salaro-page .sl-pop-footer {
          display: flex; justify-content: flex-end; gap: 6px;
          padding: 10px 4px 2px; border-top: 1px solid var(--border-subtle); margin-top: 8px;
        }
        .salaro-page .sl-btn-cancel {
          padding: 6px 12px; border: 1px solid var(--border-color); border-radius: 6px;
          background: rgba(255,255,255,0.04); color: var(--text-secondary); cursor: pointer; font-size: 12px;
        }
        .salaro-page .sl-btn-ok {
          padding: 6px 14px; border: 1px solid #6366f1; border-radius: 6px;
          background: #6366f1; color: #fff; cursor: pointer; font-size: 12px; font-weight: 500;
        }
        .salaro-page .sl-btn-ok:hover { background: #4f46e5; }
      `}</style>

      <div className="sl-titlebar">
        <span className="sl-icon" />
        <span>სალარო</span>
      </div>

      <div className="sl-toolbar" ref={toolbarRef}>
        <div className="sl-btn sl-btn-play" title="გაშვება" onClick={() => setPickerOpen(true)}>▶</div>
        <input
          className="sl-date"
          value={fromDisplay}
          readOnly
          placeholder="დაწყება"
          onClick={() => setPickerOpen(true)}
        />
        <div className="sl-btn" title="კალენდარი" onClick={() => setPickerOpen(true)}>📅</div>
        <div className="sl-btn" title="დრო" onClick={() => setPickerOpen(true)}>🕐</div>
        <input
          className="sl-date"
          value={toDisplay}
          readOnly
          placeholder="დასრულება"
          onClick={() => setPickerOpen(true)}
        />
        <select
          className="sl-select"
          value={storeFilter}
          onChange={(e) => setStoreFilter(e.target.value)}
          style={{ marginLeft: 'auto', minWidth: 130 }}
        >
          <option value="all">ყველა მაღაზია</option>
          {stores.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          className="sl-select"
          value={cashierFilter}
          onChange={(e) => setCashierFilter(e.target.value)}
          style={{ marginLeft: 0 }}
        >
          <option value="all">
            {storeFilter === 'all' ? 'ყველა მოლარე' : `ყველა მოლარე — ${storeFilter}`}
          </option>
          {cashierIds.map(({ id, name }) => (
            <option key={id} value={id}>{name || `მოლარე #${id}`}</option>
          ))}
        </select>
        <div className="sl-btn sl-btn-up" title="გასუფთავება" onClick={clearRange}>▲</div>

        {pickerOpen && (
          <div className="sl-pop" ref={popRef}>
            <DatePicker
              selected={strToDate(localFrom)}
              startDate={strToDate(localFrom)}
              endDate={strToDate(localTo)}
              onChange={handleCalendarRange}
              selectsRange
              inline
              monthsShown={1}
              formatWeekDay={(d) => WK_KA[d] || d}
              renderCustomHeader={({ date, changeMonth, changeYear, decreaseMonth, increaseMonth }) => (
                <div className="sl-cal-header">
                  <button type="button" className="sl-cal-nav" onClick={decreaseMonth}>‹</button>
                  <select className="sl-cal-select" value={date.getMonth()} onChange={(e) => changeMonth(Number(e.target.value))}>
                    {MONTHS_EN.map((m, i) => <option key={m} value={i}>{m}</option>)}
                  </select>
                  <input
                    type="number"
                    className="sl-cal-year"
                    value={date.getFullYear()}
                    onChange={(e) => changeYear(Number(e.target.value))}
                  />
                  <button type="button" className="sl-cal-nav" onClick={increaseMonth}>›</button>
                </div>
              )}
            />
            <div className="sl-time-row">
              <div className="sl-time-field">
                <div className="sl-time-lbl">დაწყების საათი</div>
                <select className="sl-time-sel" value={localFromT} onChange={(e) => setLocalFromT(e.target.value)}>
                  {opts.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="sl-time-field">
                <div className="sl-time-lbl">დასრულების საათი</div>
                <select className="sl-time-sel" value={localToT} onChange={(e) => setLocalToT(e.target.value)}>
                  {opts.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </div>
            <div className="sl-pop-footer">
              <button type="button" className="sl-btn-cancel" onClick={clearRange}>გასუფთავება</button>
              <button type="button" className="sl-btn-ok" onClick={() => setPickerOpen(false)}>კარგი</button>
            </div>
          </div>
        )}
      </div>

      <div className="sl-tablewrap">
        <table className="sl-table">
          <thead>
            <tr>
              <th style={{ width: '32%' }}>მოლარე</th>
              <th>ნაღდი</th>
              <th>უნაღდო</th>
              <th>მიმდინარე</th>
              <th>ჯამი</th>
              <th>რაოდენობა</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="sl-empty">
                  {periodActive ? 'ამ პერიოდში მოლარე არ მუშაობდა' : 'მონაცემი არ მოიძებნა'}
                </td>
              </tr>
            ) : rows.map((r) => {
              // Period mode: use actual per-cashier cash/card from cashier_day_breakdown.
              // Lifetime mode: approximate via overall payment share (no per-cashier split available).
              const cash = r.cash != null
                ? r.cash
                : (lifetimeShare ? r.revenue * lifetimeShare.cashPct : 0);
              const card = r.card != null
                ? r.card
                : (lifetimeShare ? r.revenue * lifetimeShare.cardPct : 0);
              const label = r.cashier_name || `მოლარე #${r.user_id ?? '—'}`;
              return (
                <tr key={`${r.user_id}-${r.object}`}>
                  <td className="sl-name">{label} · <span className="sl-muted">{r.object}</span></td>
                  <td className="sl-num">{fmt2(cash)}</td>
                  <td className="sl-num">{fmt2(card)}</td>
                  <td className="sl-num sl-muted">0.00</td>
                  <td className="sl-num" style={{ fontWeight: 600 }}>{fmt2(r.revenue)}</td>
                  <td className="sl-num">{fmtN(r.receipts)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="sl-boxes">
        <Box val={fmt2(kpiCash)} label="ნაღდი" />
        <Box val={fmt2(kpiCard)} label="უნაღდო" />
        <Box val="0.00" label="მიმდინარე" />
        <Box val={fmt2(kpiTotal)} label="ჯამი" highlight />
        <Box val={fmtN(totals.receipts)} label="კლიენტები" />
        <Box val={fmt2(totals.aov)} label="საშუალო" />
      </div>

      {periodActive && (
        <div className="sl-note">
          <strong>შენიშვნა:</strong> ნაღდი/უნაღდო per-მოლარე — ცხოვრების ფარდობით გათვლილია (approximate).
          per-period ცალკე SQL როცა გამოვა, ეს ცარიელი slot გასწორდება.
        </div>
      )}

      <div className="sl-section">
        <div className="sl-section-title">
          <span className="sl-icon" />
          მოლარეების ანალიზი
        </div>
        <div className="sl-tablewrap">
          <table className="sl-table">
            <thead>
              <tr>
                <th style={{ width: '40px' }}>#</th>
                <th style={{ width: '34%' }}>მოლარე</th>
                <th>საშუალო კალათა</th>
                <th>ჩეკი / საათში</th>
                <th>ნაღდის წილი</th>
              </tr>
            </thead>
            <tbody>
              {analysisRows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="sl-empty">მონაცემი არ მოიძებნა</td>
                </tr>
              ) : analysisRows.map((r) => {
                const label = r.cashier_name || `მოლარე #${r.user_id ?? '—'}`;
                const rankCls = r.rank === 1 ? 'sl-rank-1' : r.rank === 2 ? 'sl-rank-2' : r.rank === 3 ? 'sl-rank-3' : '';
                let tphCell;
                if (r.tph === null) {
                  tphCell = <span className="sl-muted">{periodActive ? '—' : 'პერიოდი მონიშნე'}</span>;
                } else {
                  tphCell = <span className="sl-num">{fmt2(r.tph)}</span>;
                }
                let cashCell;
                if (r.cashPct === null) {
                  cashCell = <span className="sl-muted">—</span>;
                } else {
                  cashCell = (
                    <>
                      <span className="sl-num">{fmt2(r.cashPct)}%</span>
                      <span className="sl-pct-bar">
                        <span className="sl-pct-bar-fill" style={{ width: `${Math.max(0, Math.min(100, r.cashPct))}%` }} />
                      </span>
                    </>
                  );
                }
                return (
                  <tr key={`an-${r.user_id}-${r.object}`}>
                    <td className={`sl-rank ${rankCls}`}>{r.rank}</td>
                    <td className="sl-name">{label} · <span className="sl-muted">{r.object}</span></td>
                    <td className="sl-num">{fmt2(r.aov)}</td>
                    <td>{tphCell}</td>
                    <td>{cashCell}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="sl-section">
        <div className="sl-section-title">
          <span className="sl-icon" />
          საათობრივი აქტივობა
          <span className="sl-section-sub">
            {periodActive ? '24-საათობრივი განაწილება — შემოსავალი ლარში' : 'პერიოდი მონიშნე chart-ის სანახავად'}
          </span>
        </div>
        <div className="sl-hourchart">
          {!periodActive || !hourlyDistribution.anyData ? (
            <div className="sl-hour-empty">
              {periodActive ? 'ამ პერიოდში საათობრივი მონაცემი ცარიელია' : 'საათობრივი data ბოლო 180 დღეშია (პერიოდი მონიშნე)'}
            </div>
          ) : (
            <>
              <div className="sl-hour-row">
                {hourlyDistribution.buckets.map((v, h) => {
                  const pct = maxHourRev > 0 ? (v / maxHourRev) * 100 : 0;
                  const title = `${String(h).padStart(2,'0')}:00 — ${fmt2(v)} ₾ / ${fmtN(hourlyDistribution.receiptsB[h])} ჩეკი`;
                  return v > 0 ? (
                    <div key={h} className="sl-hour-bar" style={{ height: `${Math.max(2, pct)}%` }} title={title} />
                  ) : (
                    <div key={h} className="sl-hour-bar-empty" title={title} />
                  );
                })}
              </div>
              <div className="sl-hour-labels">
                {Array.from({ length: 24 }, (_, h) => (
                  <span key={h}>{h % 3 === 0 ? String(h).padStart(2,'0') : ''}</span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Box({ val, label, highlight = false }) {
  return (
    <div className={`sl-box ${highlight ? 'sl-box-total' : ''}`}>
      <div className="sl-box-val">{val}</div>
      <div className="sl-box-lbl">{label}</div>
    </div>
  );
}
