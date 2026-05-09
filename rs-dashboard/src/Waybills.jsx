import { useState, useEffect, useMemo } from 'react';
import {
  ResponsiveContainer,
  LineChart, Line,
  BarChart, Bar,
  AreaChart, Area,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { fetchApiJson } from './lib/api.js';
import TrustBanner from './components/TrustBanner.jsx';

const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#a855f7', '#06b6d4', '#84cc16', '#ec4899'];
const STORE_COLOR = {
  'დვაბზუ': '#3b82f6',
  'ოზურგეთი': '#10b981',
  'თბილისი': '#f59e0b',
  'გაუნაწილებელი': '#64748b',
  'უცნობი': '#94a3b8',
};

function InfoTip({ text }) {
  const [show, setShow] = useState(false);
  if (!text) return null;
  return (
    <span
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      style={{ position: 'relative', display: 'inline-block', marginLeft: 6, lineHeight: 1 }}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 15,
          height: 15,
          borderRadius: '50%',
          background: '#475569',
          color: '#cbd5e1',
          fontSize: 10,
          fontWeight: 600,
          cursor: 'help',
          userSelect: 'none',
        }}
      >
        i
      </span>
      {show && (
        <span
          style={{
            position: 'absolute',
            bottom: '120%',
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#0f172a',
            border: '1px solid #475569',
            borderRadius: 6,
            padding: '8px 10px',
            fontSize: 12,
            color: '#e2e8f0',
            width: 260,
            zIndex: 1000,
            boxShadow: '0 4px 14px rgba(0,0,0,0.5)',
            textTransform: 'none',
            letterSpacing: 0,
            fontWeight: 400,
            lineHeight: 1.45,
            whiteSpace: 'normal',
            textAlign: 'left',
            pointerEvents: 'none',
          }}
        >
          {text}
        </span>
      )}
    </span>
  );
}

function CalendarHeatmap({ days, formatNumber }) {
  // Group days into weeks (Monday-first columns)
  const cellSize = 12;
  const cellGap = 2;
  const columnWidth = cellSize + cellGap;
  const dayLabels = ['ორშ', 'სამ', 'ოთხ', 'ხუთ', 'პარ', 'შაბ', 'კვი'];

  // Compute max count for color scale
  const maxCount = days.reduce((m, d) => Math.max(m, d.count || 0), 0);

  // Group into columns by weekday position relative to first day
  const columns = [];
  let currentWeek = [];
  days.forEach((d, i) => {
    if (i === 0 && d.weekday > 0) {
      // Pad start with empty cells
      for (let p = 0; p < d.weekday; p += 1) currentWeek.push(null);
    }
    currentWeek.push(d);
    if (d.weekday === 6) {
      columns.push(currentWeek);
      currentWeek = [];
    }
  });
  if (currentWeek.length > 0) {
    while (currentWeek.length < 7) currentWeek.push(null);
    columns.push(currentWeek);
  }

  const colorFor = (count) => {
    if (!count) return '#1e293b';
    const intensity = Math.min(1, count / Math.max(maxCount, 1));
    // Green scale
    const r = Math.round(15 + (16 - 15) * intensity);
    const g = Math.round(50 + (185 - 50) * intensity);
    const b = Math.round(60 + (129 - 60) * intensity);
    return `rgb(${r}, ${g}, ${b})`;
  };

  // Month labels — show month name above the column where the 1st of the month falls
  const monthLabelsKa = ['იან','თებ','მარ','აპრ','მაი','ივნ','ივლ','აგვ','სექ','ოქტ','ნოე','დეკ'];
  const monthLabels = columns.map((col) => {
    const firstDay = col.find((d) => d && String(d.date).slice(8, 10) === '01');
    if (!firstDay) return null;
    const m = parseInt(String(firstDay.date).slice(5, 7), 10);
    return monthLabelsKa[m - 1] || '';
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowX: 'auto' }}>
      <div style={{ display: 'flex', marginBottom: 4, marginLeft: 30 }}>
        {monthLabels.map((label, i) => (
          <div
            key={i}
            style={{ width: columnWidth, fontSize: 9, color: '#94a3b8', textAlign: 'left' }}
          >
            {label || ''}
          </div>
        ))}
      </div>
      <div style={{ display: 'flex' }}>
        <div style={{ display: 'flex', flexDirection: 'column', marginRight: 4 }}>
          {dayLabels.map((d, i) => (
            <div key={i} style={{ height: cellSize, marginBottom: cellGap, fontSize: 9, color: '#94a3b8', lineHeight: `${cellSize}px`, width: 24 }}>
              {i % 2 === 0 ? d : ''}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex' }}>
          {columns.map((col, ci) => (
            <div key={ci} style={{ display: 'flex', flexDirection: 'column', marginRight: cellGap }}>
              {col.map((d, di) => (
                <div
                  key={di}
                  title={d ? `${d.date} — ${d.count} ცალი, ${formatNumber(d.amount)}` : ''}
                  style={{
                    width: cellSize,
                    height: cellSize,
                    marginBottom: cellGap,
                    background: d ? colorFor(d.count) : 'transparent',
                    borderRadius: 2,
                    cursor: d && d.count ? 'pointer' : 'default',
                  }}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 10, fontSize: 11, color: '#94a3b8' }}>
        <span>ნაკლები</span>
        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((t, i) => (
          <div
            key={i}
            style={{
              width: cellSize,
              height: cellSize,
              background: t === 0 ? '#1e293b' : `rgb(${Math.round(15 + (16 - 15) * t)}, ${Math.round(50 + (185 - 50) * t)}, ${Math.round(60 + (129 - 60) * t)})`,
              borderRadius: 2,
            }}
          />
        ))}
        <span>მეტი</span>
      </div>
    </div>
  );
}

function ChartCard({ title, subtitle, height = 280, info, children }) {
  return (
    <div
      style={{
        background: 'rgba(30, 41, 59, 0.6)',
        border: '1px solid rgba(148, 163, 184, 0.18)',
        borderRadius: 10,
        padding: 14,
        boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
      }}
    >
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#f9fafb', display: 'flex', alignItems: 'center' }}>
          <span>{title}</span>
          {info && <InfoTip text={info} />}
        </div>
        {subtitle && <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>{subtitle}</div>}
      </div>
      <div style={{ width: '100%', height }}>{children}</div>
    </div>
  );
}

const WAYBILL_SORT_OPTIONS = [
  { value: 'amount_asc', label: 'თანხა ზრდით' },
  { value: 'amount_desc', label: 'თანხა კლებით' },
  { value: 'date_desc', label: 'თარიღი ახლიდან' },
  { value: 'date_asc', label: 'თარიღი ძველიდან' },
];

const STORE_OPTIONS = [
  { value: '', label: 'ყველა' },
  { value: 'დვაბზუ', label: 'დვაბზუ' },
  { value: 'ოზურგეთი', label: 'ოზურგეთი' },
  { value: 'თბილისი', label: 'თბილისი' },
  { value: 'გაუნაწილებელი', label: 'გაუნაწილებელი' },
  { value: 'უცნობი', label: 'უცნობი' },
];

const STATUS_OPTIONS = [
  { value: '', label: 'ყველა' },
  { value: 'აქტიური', label: 'აქტიური' },
  { value: 'დასრულებული', label: 'დასრულებული' },
  { value: 'გაუქმებული', label: 'გაუქმებული' },
];

const TYPE_OPTIONS = [
  { value: '', label: 'ყველა ტიპი' },
  { value: 'ტრანსპორტირებით', label: 'ტრანსპორტირებით' },
  { value: 'ქვე-ზედნადები', label: 'ქვე-ზედნადები' },
  { value: 'დაბრუნება', label: 'დაბრუნება' },
];

function getWaybillAmount(wb) {
  const effective = Number(wb?.effective_amount);
  if (Number.isFinite(effective)) return effective;
  const nominal = Number(wb?.nominal_amount);
  return Number.isFinite(nominal) ? nominal : 0;
}

const COUNT = new Intl.NumberFormat('ka-GE', {
  maximumFractionDigits: 0,
});

function formatCount(value) {
  return COUNT.format(Number(value) || 0);
}

function KpiCard({ label, value, sub, tone, accent, smallValue, info }) {
  const toneClass = tone === 'pos' ? 'amount-positive' : tone === 'neg' ? 'amount-negative' : '';
  const valueColor = tone === 'pos' ? '#10b981' : tone === 'neg' ? '#ef4444' : '#f9fafb';
  const accentBar = accent || (tone === 'pos' ? '#10b981' : tone === 'neg' ? '#ef4444' : '#3b82f6');
  // Auto-shrink value font when text is long so big numbers like
  // "GEL 5,554,783" don't overflow the card.
  const valueLen = String(value || '').length;
  let fontSize = smallValue ? 15 : 24;
  if (!smallValue) {
    if (valueLen > 12) fontSize = 20;
    if (valueLen > 16) fontSize = 17;
    if (valueLen > 22) fontSize = 14;
  }
  return (
    <div
      style={{
        background: 'rgba(30, 41, 59, 0.6)',
        border: '1px solid rgba(148, 163, 184, 0.18)',
        borderLeft: `3px solid ${accentBar}`,
        borderRadius: 10,
        padding: '14px 16px',
        boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
        minWidth: 0,
        position: 'relative',
      }}
    >
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 500, display: 'flex', alignItems: 'center', minWidth: 0 }}>
        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: '0 1 auto', minWidth: 0 }}>{label}</span>
        {info && <InfoTip text={info} />}
      </div>
      <div
        className={toneClass}
        style={{
          fontSize,
          fontWeight: 700,
          color: valueColor,
          lineHeight: 1.15,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
        title={String(value)}
      >
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: '#cbd5e1', marginTop: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={String(sub)}>{sub}</div>}
    </div>
  );
}

export default function Waybills({ formatNumber, reloadKey, fromDate, fromTime, toDate, toTime }) {
  const [searchName, setSearchName] = useState('');
  const [waybillSortKey, setWaybillSortKey] = useState('amount_asc');
  const [storeFilter, setStoreFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [returnsOnly, setReturnsOnly] = useState(false);
  const [amountMin, setAmountMin] = useState('');
  const [amountMax, setAmountMax] = useState('');
  const [showRawTable, setShowRawTable] = useState(false);
  const now = new Date();
  const [tableYear, setTableYear] = useState(String(now.getFullYear()));
  const [tableMonth, setTableMonth] = useState(String(now.getMonth() + 1).padStart(2, '0'));
  const [tableDay, setTableDay] = useState('');
  const [tableQuery, setTableQuery] = useState('');

  const [data, setData] = useState({ waybills: [], waybills_summary: null, response_meta: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const hasActivePeriodFilter = Boolean(fromDate || toDate);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const handle = setTimeout(() => {
      if (!active) return;
      setTimeout(() => {
        if (active) {
          setLoading(true);
          setError(null);
        }
      }, 0);

      const params = new URLSearchParams({
        tab: 'waybills',
        sort: waybillSortKey,
      });
      const needle = searchName.trim();
      if (needle) params.set('q', needle);
      if (hasActivePeriodFilter) {
        params.set('from_date', fromDate || toDate || '');
        params.set('to_date', toDate || fromDate || '');
        params.set('from_time', fromTime || '00:00');
        params.set('to_time', toTime || '23:59');
      }
      if (storeFilter) params.set('store', storeFilter);
      if (statusFilter) params.set('status_filter', statusFilter);
      if (typeFilter) params.set('type_filter', typeFilter);
      if (returnsOnly) params.set('returns_only', 'true');
      if (amountMin !== '' && !Number.isNaN(Number(amountMin))) params.set('amount_min', String(amountMin));
      if (amountMax !== '' && !Number.isNaN(Number(amountMax))) params.set('amount_max', String(amountMax));

      fetchApiJson(`/api/data?${params.toString()}`, { signal: controller.signal })
        .then((json) => {
          if (!active) return;
          setData({
            waybills: json.waybills || [],
            waybills_summary: json.waybills_summary || null,
            response_meta: json.response_meta || null,
          });
          setLoading(false);
        })
        .catch((err) => {
          if (!active || err.name === 'AbortError') return;
          console.error('Failed to load waybills:', err);
          setError(err.message);
          setLoading(false);
        });
    }, 600);

    return () => {
      active = false;
      clearTimeout(handle);
      controller.abort();
    };
  }, [
    fromDate, fromTime, hasActivePeriodFilter, reloadKey, searchName, toDate, toTime,
    waybillSortKey, storeFilter, statusFilter, typeFilter, returnsOnly, amountMin, amountMax,
  ]);

  const filteredWaybills = useMemo(() => {
    return Array.isArray(data.waybills) ? data.waybills : [];
  }, [data.waybills]);

  // Available years from waybill data — used in year picker
  const availableYears = useMemo(() => {
    const set = new Set();
    filteredWaybills.forEach((w) => {
      const y = String(w.date || '').slice(0, 4);
      if (/^\d{4}$/.test(y)) set.add(y);
    });
    return Array.from(set).sort().reverse();
  }, [filteredWaybills]);

  // Detail-table view: client-side filter by year/month/day + search
  const tableRows = useMemo(() => {
    let rows = filteredWaybills;
    if (tableYear) {
      rows = rows.filter((w) => String(w.date || '').slice(0, 4) === tableYear);
    }
    if (tableMonth) {
      rows = rows.filter((w) => String(w.date || '').slice(5, 7) === tableMonth);
    }
    if (tableDay) {
      const dd = String(tableDay).padStart(2, '0');
      rows = rows.filter((w) => String(w.date || '').slice(8, 10) === dd);
    }
    if (tableQuery.trim()) {
      const needle = tableQuery.trim().toLowerCase();
      rows = rows.filter(
        (w) =>
          String(w.supplier || '').toLowerCase().includes(needle) ||
          String(w.waybill_number || '').toLowerCase().includes(needle)
      );
    }
    return rows;
  }, [filteredWaybills, tableYear, tableMonth, tableDay, tableQuery]);

  const tableSum = useMemo(
    () => tableRows.reduce((s, w) => s + (Number(w.effective_amount) || Number(w.nominal_amount) || 0), 0),
    [tableRows]
  );

  const waybillsSummary = data.waybills_summary || {};
  const statusBreakdown = Array.isArray(waybillsSummary.status_breakdown)
    ? waybillsSummary.status_breakdown
    : [];
  const storeBreakdown = Array.isArray(waybillsSummary.store_breakdown)
    ? waybillsSummary.store_breakdown
    : [];
  const monthlyTrend = Array.isArray(waybillsSummary.monthly_trend) ? waybillsSummary.monthly_trend : [];
  const yearlyComparison = Array.isArray(waybillsSummary.yearly_comparison) ? waybillsSummary.yearly_comparison : [];
  const yearlyKeys = Array.isArray(waybillsSummary.yearly_keys) ? waybillsSummary.yearly_keys : [];
  const quarterlyTrend = Array.isArray(waybillsSummary.quarterly_trend) ? waybillsSummary.quarterly_trend : [];
  const dayOfWeek = Array.isArray(waybillsSummary.day_of_week) ? waybillsSummary.day_of_week : [];
  const storeMonthly = Array.isArray(waybillsSummary.store_monthly) ? waybillsSummary.store_monthly : [];
  const storeKeys = Array.isArray(waybillsSummary.store_keys) ? waybillsSummary.store_keys : [];

  const calendarHeatmap = Array.isArray(waybillsSummary.calendar_heatmap) ? waybillsSummary.calendar_heatmap : [];
  const duplicateCandidates = Array.isArray(waybillsSummary.duplicate_candidates) ? waybillsSummary.duplicate_candidates : [];
  const monthBenchmark = waybillsSummary.month_benchmark && typeof waybillsSummary.month_benchmark === 'object'
    ? waybillsSummary.month_benchmark
    : null;
  const topLargest = Array.isArray(waybillsSummary.top_largest_waybills) ? waybillsSummary.top_largest_waybills : [];
  const spikeAlerts = Array.isArray(waybillsSummary.spike_alerts) ? waybillsSummary.spike_alerts : [];
  const topSuppliers = Array.isArray(waybillsSummary.top_suppliers) ? waybillsSummary.top_suppliers : [];
  const pareto = Array.isArray(waybillsSummary.pareto) ? waybillsSummary.pareto : [];
  const newSuppliersMonthly = Array.isArray(waybillsSummary.new_suppliers_monthly) ? waybillsSummary.new_suppliers_monthly : [];
  const silentSuppliers = Array.isArray(waybillsSummary.silent_suppliers) ? waybillsSummary.silent_suppliers : [];
  const supplierReliability = Array.isArray(waybillsSummary.supplier_reliability) ? waybillsSummary.supplier_reliability : [];
  const qualityTrends = Array.isArray(waybillsSummary.quality_trends) ? waybillsSummary.quality_trends : [];
  const typeBreakdown = Array.isArray(waybillsSummary.type_breakdown) ? waybillsSummary.type_breakdown : [];

  const hhi = waybillsSummary.hhi;
  const hhiClass = waybillsSummary.hhi_class;
  const supplierCountFor80 = waybillsSummary.supplier_count_for_80pct;
  const supplierCountTotal = waybillsSummary.supplier_count_total;

  // Trim long supplier names for chart Y-axis labels
  const shortenSupplier = (s) => {
    const name = String(s || '');
    return name.length > 30 ? name.slice(0, 30) + '…' : name;
  };
  const topSuppliersChart = useMemo(
    () => topSuppliers.map((x) => ({ ...x, label: shortenSupplier(x.supplier) })),
    [topSuppliers]
  );
  const statusPieData = useMemo(
    () => statusBreakdown.map((b) => ({
      name: b.status,
      value: b.row_count,
    })),
    [statusBreakdown]
  );
  const typePieData = useMemo(
    () => typeBreakdown.map((b) => ({
      name: b.type,
      value: b.row_count,
    })),
    [typeBreakdown]
  );

  const storePieData = useMemo(() => storeBreakdown.map((b) => ({
    name: b.store,
    value: Math.abs(b.effective_amount || 0),
    count: b.row_count,
  })), [storeBreakdown]);

  const dowMaxCount = useMemo(
    () => dayOfWeek.reduce((m, d) => Math.max(m, d.count || 0), 0),
    [dayOfWeek]
  );
  const periodMeta = waybillsSummary.period_meta || {};
  const periodLabel = periodMeta.label_ka || (hasActivePeriodFilter ? 'არჩეული პერიოდი' : 'პერიოდი');
  const periodCaveat = data.response_meta?.period_caveat_ka || '';

  const velocityPct = waybillsSummary.velocity_pct;
  const velocityLabel =
    velocityPct === null || velocityPct === undefined
      ? null
      : `${velocityPct > 0 ? '↑' : velocityPct < 0 ? '↓' : '→'} ${Math.abs(velocityPct).toFixed(1)}% წინა პერიოდთან`;
  const velocityTone = velocityPct === null || velocityPct === undefined
    ? null
    : velocityPct > 0
      ? 'pos'
      : velocityPct < 0
        ? 'neg'
        : null;

  const clearFilters = () => {
    setSearchName('');
    setStoreFilter('');
    setStatusFilter('');
    setTypeFilter('');
    setReturnsOnly(false);
    setAmountMin('');
    setAmountMax('');
  };

  const hasAnyFilter =
    searchName || storeFilter || statusFilter || typeFilter || returnsOnly || amountMin !== '' || amountMax !== '';

  if (error) {
    return (
      <div className="local-pay-banner" style={{ background: '#ef4444', color: '#fff' }} role="alert">
        <strong>შეცდომა:</strong> {error}
      </div>
    );
  }

  if (loading) {
    return <div className="loading">იტვირთება ზედნადებები...</div>;
  }

  return (
    <>
      <TrustBanner
        responseMeta={data.response_meta}
        waybillsSummary={waybillsSummary}
        paymentScopeSummary={{}}
        suppliersOnlyJournalOrBank={0}
      />

      {/* Tab Hero */}
      <div className="tab-hero">
        <span className="tab-hero-title">📄 ზედნადებები</span>
        <span className="tab-hero-desc">
          RS ზედნადებების სრული ანალიზი · {periodMeta.applied ? periodLabel : 'ყველა პერიოდი'}
        </span>
      </div>

      {/* KPI cards — unified grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 10, marginTop: 12, marginBottom: 12 }}>
        <KpiCard
          accent="#3b82f6"
          label="ჩანაწერი"
          info="სულ რამდენი ზედნადები მოვიდა მითითებულ პერიოდში. ერთ ზედნადებზე შეიძლება ბევრი პროდუქტი იყოს."
          value={formatCount(waybillsSummary.total_count || 0)}
          sub={`${formatCount(waybillsSummary.daily_avg_count || 0)} / დღეში`}
        />
        <KpiCard
          accent="#10b981"
          label="ჯამი (ეფექტური)"
          info="ფაქტურის რეალური ფული — გაუქმებული და დაბრუნებული უკვე გამოკლებული. ე.ი. რეალურად რა დაგვრჩა."
          value={formatNumber(waybillsSummary.total_effective_amount || 0)}
          sub={waybillsSummary.daily_avg_amount ? `${formatNumber(waybillsSummary.daily_avg_amount)} / დღე` : null}
        />
        <KpiCard
          accent="#06b6d4"
          label="საშუალო"
          info="ერთი ფაქტურის საშუალო თანხა. მედიანა უფრო ზუსტია (outlier-ები ნაკლებად ცვლის)."
          value={formatNumber(waybillsSummary.avg_amount || 0)}
          sub={`მედიანა ${formatNumber(waybillsSummary.median_amount || 0)}`}
        />
        <KpiCard
          accent="#f59e0b"
          label="უდიდესი"
          info="ერთი ფაქტურის ყველაზე დიდი თანხა — outlier-ები რომ დავინახოთ."
          value={formatNumber(waybillsSummary.max_amount || 0)}
        />
        <KpiCard
          label="დაბრუნება"
          info="რა % ფაქტურა დაუბრუნდა მომწოდებელს. დიდი % = ხარისხის ან საქონლის პრობლემა."
          value={`${(waybillsSummary.return_pct || 0).toFixed(1)}%`}
          sub={`${formatCount(waybillsSummary.return_count || 0)} ცალი · ${formatNumber(waybillsSummary.return_amount || 0)}`}
          tone="neg"
        />
        <KpiCard
          accent="#a855f7"
          label="აქტიური ფირმა"
          info="რამდენი უნიკალური მომწოდებლისგან მოვიდა ფაქტურა მითითებულ პერიოდში."
          value={formatCount(waybillsSummary.active_suppliers_count || 0)}
        />
        {periodMeta.applied && (
          <KpiCard
            label="ახალი ფირმა"
            info="მომწოდებელი რომელიც პერიოდში პირველად გამოჩნდა (ადრე არასოდეს გვქონდა მისგან ფაქტურა)."
            value={formatCount(waybillsSummary.new_suppliers_count || 0)}
            sub="ამ პერიოდში პირველად"
            tone="pos"
          />
        )}
        {velocityLabel && (
          <KpiCard
            label="ცვლილება"
            info="ფაქტურის ჯამი ამ პერიოდში vs წინა იგივე ხანგრძლივობის პერიოდი. პლუსი = გაიზარდა, მინუსი = შემცირდა."
            value={velocityLabel}
            sub={waybillsSummary.prev_period_total ? `წინა: ${formatNumber(waybillsSummary.prev_period_total)}` : null}
            tone={velocityTone}
          />
        )}
        <KpiCard
          accent="#64748b"
          smallValue
          label="თარიღის შუალედი"
          info="პირველი და ბოლო ფაქტურის თარიღი მითითებულ პერიოდში."
          value={waybillsSummary.date_min && waybillsSummary.date_max
            ? `${waybillsSummary.date_min} → ${waybillsSummary.date_max}`
            : '—'}
          sub={`${formatCount(waybillsSummary.day_span || 0)} დღე`}
        />
      </div>

      {/* Filters row 1 — text + sort */}
      <div className="controls controls-filters">
        <label className="filter-field">
          <span className="filter-label">ძებნა</span>
          <input
            type="text"
            className="search-input search-input-compact"
            placeholder="კომპანია ან ზედნადები…"
            value={searchName}
            onChange={(e) => setSearchName(e.target.value)}
            autoComplete="off"
          />
        </label>
        <label className="filter-field">
          <span className="filter-label">სორტი</span>
          <select
            className="pnl-month-select"
            value={waybillSortKey}
            onChange={(e) => setWaybillSortKey(e.target.value)}
          >
            {WAYBILL_SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="filter-field">
          <span className="filter-label">სტატუსი</span>
          <select
            className="pnl-month-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label className="filter-field">
          <span className="filter-label">ტიპი</span>
          <select
            className="pnl-month-select"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            {TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label className="filter-field">
          <span className="filter-label">თანხა (≥)</span>
          <input
            type="number"
            className="search-input search-input-compact"
            style={{ maxWidth: 90 }}
            placeholder="0"
            value={amountMin}
            onChange={(e) => setAmountMin(e.target.value)}
          />
        </label>
        <label className="filter-field">
          <span className="filter-label">თანხა (≤)</span>
          <input
            type="number"
            className="search-input search-input-compact"
            style={{ maxWidth: 90 }}
            placeholder="∞"
            value={amountMax}
            onChange={(e) => setAmountMax(e.target.value)}
          />
        </label>
        <label className="filter-field" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input
            type="checkbox"
            checked={returnsOnly}
            onChange={(e) => setReturnsOnly(e.target.checked)}
          />
          <span className="filter-label" style={{ margin: 0 }}>მხოლოდ დაბრუნება</span>
        </label>
        {hasAnyFilter && (
          <button
            type="button"
            className="badge"
            style={{ cursor: 'pointer', background: '#f3f4f6', border: '1px solid #d1d5db' }}
            onClick={clearFilters}
          >
            ✕ გასუფთავება
          </button>
        )}
      </div>

      {/* Store filter chips */}
      <div className="controls controls-filters" style={{ marginTop: 4, marginBottom: 8 }}>
        <span className="filter-label" style={{ alignSelf: 'center' }}>მაღაზია:</span>
        {STORE_OPTIONS.map((o) => (
          <button
            key={o.value || 'all'}
            type="button"
            className={`badge ${storeFilter === o.value ? 'active' : 'muted'}`}
            style={{ cursor: 'pointer', border: '1px solid #d1d5db' }}
            onClick={() => setStoreFilter(o.value)}
          >
            {o.label}
          </button>
        ))}
        {storeBreakdown.length > 0 && (
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>
            ({storeBreakdown.map((b) => `${b.store}: ${formatCount(b.row_count)}`).join(' · ')})
          </span>
        )}
      </div>

      {/* Bottom badges */}
      <div className="controls controls-filters" style={{ marginTop: 0, marginBottom: 12 }}>
        <span className="badge muted">პერიოდი: {periodMeta.applied ? periodLabel : 'ყველა'}</span>
        <span className="badge muted">ნომინალური: {formatNumber(waybillsSummary.total_nominal_amount || 0)}</span>
        {statusBreakdown.map((item) => (
          <span key={`status-${item.status || 'unknown'}`} className="badge muted">
            {item.status || 'უცნობი'}: {formatCount(item.row_count)}
          </span>
        ))}
      </div>

      {periodCaveat && (
        <div className="trust-banner-sub trust-banner-sub--warn">
          {periodCaveat}
        </div>
      )}

      {/* === Charts: time-based === */}
      {monthlyTrend.length > 0 && (
        <>
          <h3 style={{ marginTop: 24, marginBottom: 12, color: '#f9fafb', fontSize: 16 }}>📈 დროითი ტრენდი</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 12, marginBottom: 16 }}>
            <ChartCard
              title="თვის ტრენდი"
              subtitle="თანხა (მარცხენა) + რაოდენობა (მარჯვენა) + 3-თვიანი საშუალო"
              info="თვეების მიხედვით ფაქტურის ჯამი (მწვანე) + რაოდენობა (ცისფერი) + 3-თვიანი მცოცავი საშუალო (ნარინჯი). ნარინჯი ანელებს ერთჯერად ცვლილებას — trend უკეთ ჩანს."
            >
              <ResponsiveContainer>
                <LineChart data={monthlyTrend} margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="month" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="left" stroke="#10b981" tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="right" orientation="right" stroke="#3b82f6" tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line yAxisId="left" type="monotone" dataKey="amount" name="თანხა" stroke="#10b981" strokeWidth={2} dot={false} />
                  <Line yAxisId="left" type="monotone" dataKey="ma3_amount" name="3-თვიანი საშ." stroke="#f59e0b" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                  <Line yAxisId="right" type="monotone" dataKey="count" name="რაოდენობა" stroke="#3b82f6" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
            {yearlyKeys.length > 1 && (
              <ChartCard
                title="წლების შედარება"
                subtitle="თვე-თვე — სად მეტია, სად ნაკლები"
                info="თვე-თვე ფაქტურის ჯამი ცალკე ყოველი წლისთვის. დაგეხმარება ნახო რომელ წელს რომელი თვე იყო ცხელი ან ცარიელი."
              >
                <ResponsiveContainer>
                  <LineChart data={yearlyComparison} margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="month" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {yearlyKeys.map((y, i) => (
                      <Line key={y} type="monotone" dataKey={y} stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2} dot={{ r: 3 }} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>
            )}
          </div>
        </>
      )}

      {/* === Charts: seasonal === */}
      {(quarterlyTrend.length > 0 || dayOfWeek.length > 0) && (
        <>
          <h3 style={{ marginTop: 8, marginBottom: 12, color: '#f9fafb', fontSize: 16 }}>📊 სეზონური</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 12, marginBottom: 16 }}>
            {quarterlyTrend.length > 0 && (
              <ChartCard
                title="კვარტალი"
                subtitle="ფაქტურის ჯამი კვარტალურად"
                info="კვარტალი = 3 თვე ერთად. სეზონური trend უკეთ ჩანს ვიდრე ცალ-ცალკე თვეებში."
              >
                <ResponsiveContainer>
                  <BarChart data={quarterlyTrend} margin={{ top: 5, right: 10, left: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="quarter" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} />
                    <Bar dataKey="amount" name="თანხა" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
            )}
            {dayOfWeek.length > 0 && (
              <ChartCard
                title="კვირის რომელი დღე"
                subtitle="რაოდენობა (ფერი — სიხშირის სიდიდე)"
                info="ორშაბათიდან კვირამდე — როცა ყველაზე მეტი ფაქტურა მოდის. მუქი ფერი = მრავლად, ღია = ცოტად."
              >
                <ResponsiveContainer>
                  <BarChart data={dayOfWeek} margin={{ top: 5, right: 10, left: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="day" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} />
                    <Bar dataKey="count" name="რაოდენობა">
                      {dayOfWeek.map((d, i) => {
                        const intensity = dowMaxCount ? d.count / dowMaxCount : 0;
                        const r = Math.round(59 + (239 - 59) * intensity);
                        const g = Math.round(130 - 130 * intensity + 68);
                        const b = Math.round(246 - 200 * intensity);
                        return <Cell key={i} fill={`rgb(${r}, ${g}, ${b})`} />;
                      })}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
            )}
          </div>
        </>
      )}

      {/* === Charts: store === */}
      {storeBreakdown.length > 0 && (
        <>
          <h3 style={{ marginTop: 8, marginBottom: 12, color: '#f9fafb', fontSize: 16 }}>🏪 მაღაზიის ანალიზი</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 12, marginBottom: 16 }}>
            <ChartCard
              title="მაღაზიის წილი"
              subtitle="ფაქტურის ჯამი მაღაზიის მიხედვით"
              info="ყოველი მაღაზიის წვლილი მთლიან ფაქტურაში. გაუნაწილებელი = ფაქტურა რომელსაც კონკრეტული მაღაზია არ მიეკუთვნა."
            >
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={storePieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={(e) => e.name}>
                    {storePieData.map((entry, i) => (
                      <Cell key={i} fill={STORE_COLOR[entry.name] || CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} formatter={(v) => formatNumber(v)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </ChartCard>
            {storeMonthly.length > 0 && storeKeys.length > 0 && (
              <ChartCard
                title="მაღაზიის ისტორია"
                subtitle="თვის მიხედვით — დაფარული გრაფიკი"
                info="თვეების მიხედვით — როგორ იცვლება თითოეული მაღაზიის წილი დროში. ფერები ერთიდაიგივე pie-სთან."
              >
                <ResponsiveContainer>
                  <AreaChart data={storeMonthly} margin={{ top: 5, right: 10, left: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="month" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {storeKeys.map((sk, i) => (
                      <Area
                        key={sk}
                        type="monotone"
                        dataKey={sk}
                        stackId="1"
                        stroke={STORE_COLOR[sk] || CHART_COLORS[i % CHART_COLORS.length]}
                        fill={STORE_COLOR[sk] || CHART_COLORS[i % CHART_COLORS.length]}
                        fillOpacity={0.7}
                      />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
              </ChartCard>
            )}
          </div>
        </>
      )}

      {/* === Charts: suppliers === */}
      {topSuppliers.length > 0 && (
        <>
          <h3 style={{ marginTop: 8, marginBottom: 12, color: '#f9fafb', fontSize: 16 }}>👥 მომწოდებლის ანალიზი</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginBottom: 12 }}>
            <KpiCard
              accent={hhi >= 2500 ? '#ef4444' : hhi >= 1500 ? '#f59e0b' : '#10b981'}
              label="HHI კონცენტრაცია"
              info="ბაზრის კონცენტრაციის ინდექსი. ნაკლები 1500 = დივერსიფიცირებული. 1500-2500 = საშუალო. 2500-ზე მეტი = ერთ-ორ ფირმაზე ძალიან დამოკიდებული (რისკი)."
              value={hhi != null ? formatCount(hhi) : '—'}
              sub={hhiClass || ''}
            />
            <KpiCard
              accent="#a855f7"
              label="80% ფაქტურის მომცემი"
              info="რამდენი ფირმა იძლევა მთლიანი ფაქტურის 80%-ს. პატარა ციფრი = დიდი დამოკიდებულება ცოტა ფირმაზე."
              value={supplierCountFor80 != null ? `${supplierCountFor80} ფირმა` : '—'}
              sub={supplierCountTotal ? `მთლიანიდან: ${supplierCountTotal}` : ''}
            />
            <KpiCard
              accent="#06b6d4"
              label="ტოპ-1 დამოკიდებულება"
              info="ყველაზე დიდი მომწოდებლის წილი მთლიან ფაქტურაში. დიდი % = რისკი (ძალიან დამოკიდებული ერთ ფირმაზე)."
              value={topSuppliers[0] ? `${topSuppliers[0].share_pct}%` : '—'}
              sub={topSuppliers[0] ? shortenSupplier(topSuppliers[0].supplier) : ''}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 12, marginBottom: 16 }}>
            <ChartCard
              title="ტოპ-10 მომწოდებელი"
              subtitle="ფაქტურის ჯამის მიხედვით"
              info="10 ყველაზე დიდი მომწოდებელი ფაქტურის ჯამის მიხედვით. ამანვე ვიცი ვისზე ვართ ყველაზე დამოკიდებული."
              height={320}
            >
              <ResponsiveContainer>
                <BarChart data={topSuppliersChart} layout="vertical" margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis type="number" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="label" stroke="#94a3b8" tick={{ fontSize: 10 }} width={170} />
                  <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }}
                    formatter={(v, n, ent) => [formatNumber(v), `${ent.payload.share_pct}% / ${ent.payload.count} ცალი`]} />
                  <Bar dataKey="amount" name="თანხა" fill="#3b82f6" />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            {pareto.length > 0 && (
              <ChartCard
                title="Pareto — 80/20"
                subtitle="რანგი → კუმულატიური წილი"
                info="Pareto-ს კანონი: ხშირად 20% ფირმა იძლევა 80% ფაქტურას. ხაზი აჩვენებს — რანგი → კუმულატიური წილი. 80%-ზე გადადის ვის პოზიციაზე."
              >
                <ResponsiveContainer>
                  <LineChart data={pareto} margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="rank" stroke="#94a3b8" tick={{ fontSize: 11 }} label={{ value: 'მომწოდებლის რანგი', fill: '#94a3b8', fontSize: 11, position: 'insideBottom', offset: -2 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }}
                      formatter={(v, n, ent) => [`${v}%`, ent.payload.supplier?.slice(0, 50)]} />
                    <Line type="monotone" dataKey="cumulative_pct" name="კუმულ. %" stroke="#10b981" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>
            )}

            {newSuppliersMonthly.length > 0 && (
              <ChartCard
                title="ახალი მომწოდებლები თვეებში"
                subtitle="რომელ თვეში გამოჩნდა პირველად"
                info="ყოველ თვეში რამდენი ახალი ფირმა გამოჩნდა პირველად — ე.ი. ადრე არასოდეს მოგვიტანდა."
              >
                <ResponsiveContainer>
                  <BarChart data={newSuppliersMonthly} margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="month" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} />
                    <Bar dataKey="new_suppliers" name="ახალი ფირმა" fill="#a855f7" />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
            )}

            {silentSuppliers.length > 0 && (
              <ChartCard
                title="გაჩუმებული მომწოდებლები"
                subtitle="ვინ აღარ მოიტანა 90+ დღე"
                info="ფირმები რომელთაც აღარ მოგვიტანეს 90+ დღე. შესაძლოა გვწყვეტს ან რაიმე პრობლემაა — ღირს ხელახლა დაკავშირება."
                height={320}
              >
                <div style={{ overflow: 'auto', height: '100%' }}>
                  <table style={{ width: '100%', fontSize: 12 }}>
                    <thead>
                      <tr style={{ position: 'sticky', top: 0, background: '#1e293b' }}>
                        <th style={{ textAlign: 'left', padding: 6, color: '#94a3b8' }}>ფირმა</th>
                        <th style={{ textAlign: 'right', padding: 6, color: '#94a3b8' }}>ბოლოს</th>
                        <th style={{ textAlign: 'right', padding: 6, color: '#94a3b8' }}>დღე</th>
                      </tr>
                    </thead>
                    <tbody>
                      {silentSuppliers.map((s, i) => (
                        <tr key={i} style={{ borderTop: '1px solid #334155' }}>
                          <td style={{ padding: 6, color: '#e2e8f0' }}>{shortenSupplier(s.supplier)}</td>
                          <td style={{ padding: 6, color: '#94a3b8', textAlign: 'right' }}>{s.last_date}</td>
                          <td style={{ padding: 6, color: s.days_silent > 365 ? '#ef4444' : '#f59e0b', textAlign: 'right', fontWeight: 600 }}>{s.days_silent}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </ChartCard>
            )}

            {supplierReliability.length > 0 && (
              <ChartCard
                title="ტოპ-20 — სანდოობის ქულა"
                subtitle="100 = სრული. ციფრი ცარიელი = გაუქმება/დაბრუნება ნაკლები"
                info="ფორმულა: 100 − გაუქმება% − (დაბრუნება% × 0.5). მწვანე ≥95 = საუკეთესო, ყვითელი 85-95 = საშუალო, წითელი <85 = პრობლემა."
                height={400}
              >
                <div style={{ overflow: 'auto', height: '100%' }}>
                  <table style={{ width: '100%', fontSize: 12 }}>
                    <thead>
                      <tr style={{ position: 'sticky', top: 0, background: '#1e293b' }}>
                        <th style={{ textAlign: 'left', padding: 6, color: '#94a3b8' }}>ფირმა</th>
                        <th style={{ textAlign: 'right', padding: 6, color: '#94a3b8' }}>ქულა</th>
                        <th style={{ textAlign: 'right', padding: 6, color: '#94a3b8' }}>გაუქმ. %</th>
                        <th style={{ textAlign: 'right', padding: 6, color: '#94a3b8' }}>დაბრუნ. %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {supplierReliability.map((s, i) => (
                        <tr key={i} style={{ borderTop: '1px solid #334155' }}>
                          <td style={{ padding: 6, color: '#e2e8f0' }}>{shortenSupplier(s.supplier)}</td>
                          <td style={{ padding: 6, color: s.reliability_score >= 95 ? '#10b981' : s.reliability_score >= 85 ? '#f59e0b' : '#ef4444', textAlign: 'right', fontWeight: 700 }}>{s.reliability_score.toFixed(1)}</td>
                          <td style={{ padding: 6, color: '#94a3b8', textAlign: 'right' }}>{s.cancel_pct.toFixed(1)}</td>
                          <td style={{ padding: 6, color: '#94a3b8', textAlign: 'right' }}>{s.return_pct.toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </ChartCard>
            )}
          </div>
        </>
      )}

      {/* === Calendar heatmap === */}
      {calendarHeatmap.length > 0 && (
        <>
          <h3 style={{ marginTop: 8, marginBottom: 12, color: '#f9fafb', fontSize: 16 }}>📅 აქტივობის კალენდარი (ბოლო 365 დღე)</h3>
          <div style={{ marginBottom: 16 }}>
            <ChartCard
              title="ცარიელი დღე vs ცხელი დღე"
              subtitle="ფერი მიუთითებს რამდენი ფაქტურა მოვიდა იმ დღეს"
              info="ბოლო 365 დღის რუკა. ერთი კვადრატი = ერთი დღე. მუქი მწვანე = ცხელი დღე (ბევრი ფაქტურა), შავი = არცერთი ფაქტურა. დააფიქსე კურსორი კვადრატზე → ნახე დეტალი."
              height={210}
            >
              <CalendarHeatmap days={calendarHeatmap} formatNumber={formatNumber} />
            </ChartCard>
          </div>
        </>
      )}

      {/* === Month benchmark + duplicates === */}
      {(monthBenchmark || duplicateCandidates.length > 0) && (
        <>
          <h3 style={{ marginTop: 8, marginBottom: 12, color: '#f9fafb', fontSize: 16 }}>🎯 ბენჩმარკი და დუბლიკატის შემოწმება</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 12, marginBottom: 16 }}>
            {monthBenchmark && (
              <ChartCard
                title={`ბოლო სრული თვე — ${monthBenchmark.ref_month}`}
                subtitle="ბოლო 12 თვის საშუალოსთან შედარება"
                info="ბოლო სრული თვის ფაქტურა + ბოლო 12 თვის საშუალოსთან შედარება. ადგილი = რანგი 13-დან. პერცენტილი = ისტორიულად რა ადგილზეა. Z-ქულა = რამდენი სტანდარტული გადახრით განსხვავდება საშუალოსგან."
                height={210}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 4 }}>
                  <div style={{
                    fontSize: 32,
                    fontWeight: 700,
                    color: monthBenchmark.verdict_tone === 'pos' ? '#10b981'
                      : monthBenchmark.verdict_tone === 'neg' ? '#ef4444' : '#f9fafb',
                  }}>
                    {formatNumber(monthBenchmark.ref_amount)}
                  </div>
                  <div style={{ fontSize: 13, color: '#cbd5e1' }}>{monthBenchmark.verdict_ka}</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginTop: 6 }}>
                    <div>
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>ადგილი</div>
                      <div style={{ fontSize: 16, color: '#f9fafb', fontWeight: 600 }}>
                        {monthBenchmark.rank} / {monthBenchmark.total_compared}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>პერცენტილი</div>
                      <div style={{ fontSize: 16, color: '#f9fafb', fontWeight: 600 }}>
                        {monthBenchmark.percentile}%
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>12-თვის საშ.</div>
                      <div style={{ fontSize: 14, color: '#cbd5e1' }}>
                        {formatNumber(monthBenchmark.mean_prior_12m)}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>Z-ქულა</div>
                      <div style={{ fontSize: 14, color: '#cbd5e1' }}>
                        {monthBenchmark.z_score >= 0 ? '+' : ''}{monthBenchmark.z_score}
                      </div>
                    </div>
                  </div>
                </div>
              </ChartCard>
            )}

            {duplicateCandidates.length > 0 && (
              <ChartCard
                title="🔁 დუბლიკატის შემოწმება"
                subtitle="იგივე ფირმა + იგივე თარიღი + იგივე თანხა — შესამოწმებელი"
                info="ფირმები რომელთაც აქვთ იგივე თარიღი + იგივე თანხა 2+ ჯერ. შეიძლება ბუღალტრის შეცდომა (ერთი ფაქტურა ორჯერ ჩაწერა) ან ნამდვილი დუბლიკატი (ქვე-ზედნადები). კურსორი ხაზზე → ნომრები."
                height={360}
              >
                <div style={{ overflow: 'auto', height: '100%' }}>
                  <table style={{ width: '100%', fontSize: 12 }}>
                    <thead>
                      <tr style={{ position: 'sticky', top: 0, background: '#1e293b' }}>
                        <th style={{ textAlign: 'left', padding: 6, color: '#94a3b8' }}>ფირმა</th>
                        <th style={{ textAlign: 'left', padding: 6, color: '#94a3b8' }}>თარიღი</th>
                        <th style={{ textAlign: 'right', padding: 6, color: '#94a3b8' }}>თანხა</th>
                        <th style={{ textAlign: 'right', padding: 6, color: '#94a3b8' }}>×</th>
                      </tr>
                    </thead>
                    <tbody>
                      {duplicateCandidates.map((d, i) => (
                        <tr key={i} style={{ borderTop: '1px solid #334155' }} title={`ნომრები: ${(d.waybill_numbers || []).join(', ')}`}>
                          <td style={{ padding: 6, color: '#e2e8f0' }}>{shortenSupplier(d.supplier)}</td>
                          <td style={{ padding: 6, color: '#94a3b8' }}>{d.date}</td>
                          <td style={{ padding: 6, color: '#f59e0b', textAlign: 'right' }}>{formatNumber(d.amount)}</td>
                          <td style={{ padding: 6, color: '#ef4444', textAlign: 'right', fontWeight: 700 }}>{d.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </ChartCard>
            )}
          </div>
        </>
      )}

      {/* === Anomaly + risk === */}
      {(topLargest.length > 0 || spikeAlerts.length > 0) && (
        <>
          <h3 style={{ marginTop: 8, marginBottom: 12, color: '#f9fafb', fontSize: 16 }}>⚡ ანომალია და რისკი</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 12, marginBottom: 16 }}>
            {topLargest.length > 0 && (
              <ChartCard
                title="ტოპ-10 უდიდესი ერთი ზედნადები"
                subtitle="ცალკე outlier-ები — შესამოწმებელი"
                info="ყველაზე დიდი ცალკეული ფაქტურები — outlier-ები. ხელით უნდა შეამოწმო რომ რეალურია, არა შეცდომა."
                height={360}
              >
                <div style={{ overflow: 'auto', height: '100%' }}>
                  <table style={{ width: '100%', fontSize: 12 }}>
                    <thead>
                      <tr style={{ position: 'sticky', top: 0, background: '#1e293b' }}>
                        <th style={{ textAlign: 'left', padding: 6, color: '#94a3b8' }}>თარიღი</th>
                        <th style={{ textAlign: 'left', padding: 6, color: '#94a3b8' }}>ფირმა</th>
                        <th style={{ textAlign: 'left', padding: 6, color: '#94a3b8' }}>მაღაზია</th>
                        <th style={{ textAlign: 'right', padding: 6, color: '#94a3b8' }}>თანხა</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topLargest.map((w, i) => (
                        <tr key={i} style={{ borderTop: '1px solid #334155' }}>
                          <td style={{ padding: 6, color: '#94a3b8' }}>{w.date}</td>
                          <td style={{ padding: 6, color: '#e2e8f0' }}>{shortenSupplier(w.supplier)}</td>
                          <td style={{ padding: 6, color: '#94a3b8' }}>{w.store || '—'}</td>
                          <td style={{ padding: 6, color: '#f59e0b', textAlign: 'right', fontWeight: 700 }}>{formatNumber(w.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </ChartCard>
            )}

            {spikeAlerts.length > 0 ? (
              <ChartCard
                title="🚨 სპაიკ ალერტი"
                subtitle={`ბოლო სრულ თვეში (${spikeAlerts[0]?.current_month}) ფირმა 2X+ მეტი ვიდრე საშუალო`}
                info="ფირმა ბოლო სრულ თვეში 2X+ მეტი ფაქტურა მოიტანა ვიდრე მის ჩვეულებრივი საშუალო. შეიძლება ნამდვილი ცვლა, შეიძლება შეცდომა — ღირს შემოწმება."
                height={360}
              >
                <div style={{ overflow: 'auto', height: '100%' }}>
                  <table style={{ width: '100%', fontSize: 12 }}>
                    <thead>
                      <tr style={{ position: 'sticky', top: 0, background: '#1e293b' }}>
                        <th style={{ textAlign: 'left', padding: 6, color: '#94a3b8' }}>ფირმა</th>
                        <th style={{ textAlign: 'right', padding: 6, color: '#94a3b8' }}>X-ჯერ</th>
                        <th style={{ textAlign: 'right', padding: 6, color: '#94a3b8' }}>ახლა</th>
                        <th style={{ textAlign: 'right', padding: 6, color: '#94a3b8' }}>საშუალო</th>
                      </tr>
                    </thead>
                    <tbody>
                      {spikeAlerts.map((s, i) => (
                        <tr key={i} style={{ borderTop: '1px solid #334155' }}>
                          <td style={{ padding: 6, color: '#e2e8f0' }}>{shortenSupplier(s.supplier)}</td>
                          <td style={{ padding: 6, color: s.ratio >= 3 ? '#ef4444' : '#f59e0b', textAlign: 'right', fontWeight: 700 }}>{s.ratio}×</td>
                          <td style={{ padding: 6, color: '#10b981', textAlign: 'right' }}>{formatNumber(s.current_amount)}</td>
                          <td style={{ padding: 6, color: '#94a3b8', textAlign: 'right' }}>{formatNumber(s.avg_prior)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </ChartCard>
            ) : (
              <ChartCard title="🚨 სპაიკ ალერტი" subtitle="ბოლო სრულ თვეში — არცერთი 2X+ ცვლილება">
                <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
                  ანომალია ვერ ფიქსირდება
                </div>
              </ChartCard>
            )}
          </div>
        </>
      )}

      {/* === Charts: status & quality === */}
      {(statusBreakdown.length > 0 || qualityTrends.length > 0) && (
        <>
          <h3 style={{ marginTop: 8, marginBottom: 12, color: '#f9fafb', fontSize: 16 }}>⚠️ სტატუსი და ხარისხი</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 12, marginBottom: 16 }}>
            {statusBreakdown.length > 0 && (
              <ChartCard
                title="სტატუსი — წილი"
                info="აქტიური / დასრულებული / გაუქმებული — რა წილი აქვს თითოეულს. გაუქმებული წითლად — ცუდად ჩანს."
              >
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={statusPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={(e) => e.name}>
                      {statusPieData.map((entry, i) => (
                        <Cell key={i} fill={
                          entry.name?.includes('გაუქმებული') ? '#ef4444' :
                          entry.name?.includes('აქტიური') ? '#10b981' :
                          entry.name?.includes('დასრულებული') ? '#3b82f6' :
                          CHART_COLORS[i % CHART_COLORS.length]
                        } />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} formatter={(v) => formatCount(v)} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </ChartCard>
            )}

            {typeBreakdown.length > 0 && (
              <ChartCard
                title="ტიპი — წილი"
                info="ტრანსპორტირებით / ქვე-ზედნადები / დაბრუნება / სხვა — რა სახის ფაქტურები მოდის. ქვე-ზედნადები = ერთი მთავარი ფაქტურის ნაწილი."
              >
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={typePieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={(e) => e.name}>
                      {typePieData.map((entry, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} formatter={(v) => formatCount(v)} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </ChartCard>
            )}

            {qualityTrends.length > 0 && (
              <ChartCard
                title="გაუქმება + დაბრუნება — დროში %"
                subtitle="თვეში რამდენი % გაუქმდა / დაბრუნდა"
                info="თვეების მიხედვით % რომელი ფაქტურა გაუქმდა (წითელი) / დაბრუნდა (ნარინჯი). უნდა ეცადო ეს ციფრები იყოს მცირე და სტაბილური."
              >
                <ResponsiveContainer>
                  <LineChart data={qualityTrends} margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="month" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} unit="%" />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line type="monotone" dataKey="cancel_pct" name="გაუქმება %" stroke="#ef4444" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="return_pct" name="დაბრუნება %" stroke="#f59e0b" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>
            )}
          </div>
        </>
      )}

      {/* === Detailed waybill table — collapsed by default === */}
      <div style={{ marginTop: 16 }}>
        <button
          type="button"
          onClick={() => setShowRawTable((v) => !v)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'rgba(30, 41, 59, 0.6)',
            border: '1px solid rgba(148, 163, 184, 0.18)',
            borderRadius: 8,
            padding: '10px 14px',
            color: '#e2e8f0',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 500,
            width: '100%',
            justifyContent: 'space-between',
          }}
        >
          <span>📋 დეტალური ცხრილი — ყველა ზედნადები ცალ-ცალკე</span>
          <span style={{ color: '#94a3b8', fontSize: 11 }}>
            {formatCount(waybillsSummary.total_count || filteredWaybills.length)} ჩანაწერი · {showRawTable ? '▲ დახურვა' : '▼ გახსნა'}
          </span>
        </button>
      </div>

      {showRawTable && (
        <>
          {/* Detail-table inline filters */}
          <div
            style={{
              marginTop: 8,
              display: 'flex',
              flexWrap: 'wrap',
              gap: 8,
              alignItems: 'flex-end',
              padding: '10px 12px',
              background: 'rgba(30, 41, 59, 0.45)',
              border: '1px solid rgba(148, 163, 184, 0.18)',
              borderRadius: 8,
            }}
          >
            <label className="filter-field">
              <span className="filter-label">წელი</span>
              <select className="pnl-month-select" value={tableYear} onChange={(e) => setTableYear(e.target.value)}>
                <option value="">ყველა</option>
                {availableYears.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </label>
            <label className="filter-field">
              <span className="filter-label">თვე</span>
              <select className="pnl-month-select" value={tableMonth} onChange={(e) => setTableMonth(e.target.value)}>
                <option value="">ყველა</option>
                {['01','02','03','04','05','06','07','08','09','10','11','12'].map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </label>
            <label className="filter-field">
              <span className="filter-label">რიცხვი</span>
              <select className="pnl-month-select" value={tableDay} onChange={(e) => setTableDay(e.target.value)}>
                <option value="">ყველა</option>
                {Array.from({ length: 31 }, (_, i) => String(i + 1).padStart(2, '0')).map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </label>
            <label className="filter-field" style={{ flex: '1 1 220px' }}>
              <span className="filter-label">ძებნა (ფირმა / ნომერი)</span>
              <input
                type="text"
                className="search-input search-input-compact"
                placeholder="მაგ. ჯიდიაი ან 0974439764"
                value={tableQuery}
                onChange={(e) => setTableQuery(e.target.value)}
              />
            </label>
            <button
              type="button"
              className="badge"
              style={{ cursor: 'pointer', background: '#f3f4f6', border: '1px solid #d1d5db' }}
              onClick={() => {
                setTableYear('');
                setTableMonth('');
                setTableDay('');
                setTableQuery('');
              }}
            >
              ✕ გასუფთავება
            </button>
            <span style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: 12 }}>
              ნაჩვენებია {formatCount(tableRows.length)} ჩანაწერი · ჯამი {formatNumber(tableSum)}
            </span>
          </div>

          <div className="table-wrapper table-premium" style={{ marginTop: 8 }}>
            <table>
              <thead>
                <tr>
                  <th>თარიღი</th>
                  <th>ორგანიზაცია</th>
                  <th>მაღაზია</th>
                  <th>ზედნადები</th>
                  <th>თანხა</th>
                  <th>სტატუსი</th>
                </tr>
              </thead>
              <tbody>
                {tableRows.map((wb, idx) => {
                  let badgeClass = 'badge active';
                  let badgeText = 'აქტიური';

                  if (wb.status?.includes('გაუქმებული')) {
                    badgeClass = 'badge canceled';
                    badgeText = 'გაუქმებული';
                  } else if (wb.is_return || wb.type?.includes('დაბრუნება')) {
                    badgeClass = 'badge return';
                    badgeText = 'დაბრუნება';
                  }

                  return (
                    <tr key={idx}>
                      <td>{wb.date}</td>
                      <td>{wb.supplier}</td>
                      <td>{wb.store || <span style={{ color: 'var(--muted)' }}>—</span>}</td>
                      <td>{wb.waybill_number}</td>
                      <td
                        className={
                          wb.effective_amount < 0
                            ? 'amount-negative'
                            : wb.effective_amount === 0
                              ? 'amount-neutral'
                              : 'amount-positive'
                        }
                      >
                        {formatNumber(getWaybillAmount(wb))}
                      </td>
                      <td>
                        <span className={badgeClass}>{badgeText}</span>
                      </td>
                    </tr>
                  );
                })}
                {tableRows.length === 0 && (
                  <tr>
                    <td colSpan="6" style={{ textAlign: 'center' }}>
                      ამ ფილტრის შედეგებში ჩანაწერი ვერ მოიძებნა
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
