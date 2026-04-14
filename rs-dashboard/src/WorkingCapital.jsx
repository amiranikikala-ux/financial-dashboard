import { useMemo, useState } from 'react';
import {
  Bar,
  ComposedChart,
  CartesianGrid,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import ExportButton from './components/ExportButton.jsx';

const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 0,
});
const fmt = (v) => GEL.format(Number(v) || 0);

const OBJECT_COLORS = {
  'ოზურგეთი': '#4f8ef7',
  'დვაბზუ': '#34c97e',
  'გაუნაწილებელი': '#8899aa',
  'საერთო': '#f7a434',
};

const AGING_BUCKETS = [
  { key: '0-30',    label: '0–30 დღე',   cls: 'aging-0-30' },
  { key: '31-60',   label: '31–60 დღე',  cls: 'aging-31-60' },
  { key: '61-90',   label: '61–90 დღე',  cls: 'aging-61-90' },
  { key: '91-180',  label: '91–180 დღე', cls: 'aging-91-180' },
  { key: '180+',    label: '180+ დღე',   cls: 'aging-180-plus' },
];

function agingClass(bucket) {
  const map = {
    '0-30':   'aging-0-30',
    '31-60':  'aging-31-60',
    '61-90':  'aging-61-90',
    '91-180': 'aging-91-180',
    '180+':   'aging-180-plus',
  };
  return map[bucket] || 'aging-0-30';
}

function monthLabel(m) {
  if (!m) return '—';
  const [y, mo] = m.split('-');
  if (!y || !mo) return m;
  return `${mo}/${String(y).slice(2)}`;
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="pnl-tooltip">
      <div className="pnl-tooltip-label">{label}</div>
      {payload.map((p, i) => (
        <div key={`${String(p.dataKey ?? 'k')}-${i}`} style={{ color: p.color || '#ccc' }}>
          {p.name}: {fmt(p.value)}
        </div>
      ))}
    </div>
  );
}

const SORT_OPTIONS = [
  { value: 'debt_desc',  label: 'დავალიანება ↓' },
  { value: 'debt_asc',   label: 'დავალიანება ↑' },
  { value: 'days_desc',  label: 'დღეები ↓' },
  { value: 'days_asc',   label: 'დღეები ↑' },
  { value: 'org_asc',    label: 'ორგანიზაცია A→Z' },
];

const PAYMENT_SCOPE_META = {
  strict_bank_plus_manual: {
    label: 'Strict + manual',
    className: 'payment-scope-badge--split',
  },
  strict_bank_only: {
    label: 'Strict bank only',
    className: 'payment-scope-badge--strict',
  },
  manual_only: {
    label: 'Manual only',
    className: 'payment-scope-badge--manual',
  },
  unpaid_or_unmatched: {
    label: 'No paid proof',
    className: 'payment-scope-badge--unpaid',
  },
  negative_adjustment: {
    label: 'Negative adj.',
    className: 'payment-scope-badge--negative',
  },
};

const TRUTH_LAYER_LABELS = {
  'bank.raw_tax_id': 'raw tax id',
  'bank.extracted_tax_id': 'extracted tax id',
  'supplier_matching_registry.official_name': 'registry official name',
  'supplier_matching_registry.alias': 'registry alias',
  'supplier_matching_registry.person_alias': 'registry person alias',
  'supplier_matching_registry.iban': 'registry IBAN',
  'supplier_matching_registry.account_hint': 'registry account hint',
  'rs_waybills.organization_name': 'RS exact name',
  'rs_waybills.waybill_reference': 'RS waybill reference',
  'legacy_truth_assist.partner_iban_map': 'legacy IBAN audit-only',
  'legacy_truth_assist.known_aliases': 'legacy alias audit-only',
};

function amountClass(value) {
  const num = Number(value) || 0;
  if (num > 0) return 'amount-positive';
  if (num < 0) return 'amount-negative';
  return 'amount-neutral';
}

function getPaymentScopeMeta(scope) {
  return PAYMENT_SCOPE_META[String(scope || '').trim()] || {
    label: String(scope || 'Unknown scope'),
    className: 'payment-scope-badge--unpaid',
  };
}

function getOfficialNameSourceMeta(source) {
  const raw = String(source || '').trim();
  if (raw === 'supplier_matching_registry.official_name') {
    return { label: 'Registry primary', className: 'truth-source-badge--registry' };
  }
  if (raw === 'rs_waybills.organization_name') {
    return { label: 'RS backstop', className: 'truth-source-badge--rs' };
  }
  if (raw.startsWith('legacy_truth_assist.')) {
    return { label: 'Legacy audit-only', className: 'truth-source-badge--legacy' };
  }
  if (raw) {
    return { label: 'Other source', className: 'truth-source-badge--other' };
  }
  return { label: 'Truth pending', className: 'truth-source-badge--other' };
}

function compactText(value, maxLen = 88) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  return text.length > maxLen ? `${text.slice(0, maxLen - 1)}…` : text;
}

function formatTruthSources(rawSources) {
  if (!Array.isArray(rawSources) || rawSources.length === 0) return '';
  return rawSources
    .map((source) => TRUTH_LAYER_LABELS[source] || source)
    .join(' · ');
}

export default function WorkingCapital({
  supplierAging,
  agingSummary,
  apMonthlyTrend,
  paymentScopeSummary,
  truthBoundarySummary,
  onSupplierClick,
}) {
  const aging = useMemo(
    () => (Array.isArray(supplierAging) ? supplierAging : []),
    [supplierAging],
  );
  const apTrend = useMemo(
    () => (Array.isArray(apMonthlyTrend) ? apMonthlyTrend : []),
    [apMonthlyTrend],
  );

  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState('debt_desc');

  const kpis = useMemo(() => {
    const totalDebt = aging.reduce((s, r) => s + (Number(r.total_debt) || 0), 0);
    const count = aging.length;
    const avgDays =
      count > 0
        ? aging.reduce((s, r) => s + (Number(r.days_since_last) || 0), 0) / count
        : 0;
    const lastTrend = apTrend[apTrend.length - 1];
    const cumDebt = Number(lastTrend?.cumulative_debt) || 0;
    return { totalDebt, count, avgDays, cumDebt };
  }, [aging, apTrend]);

  const paymentSplitCards = useMemo(
    () => [
      {
        key: 'strict',
        label: 'Strict ბანკი',
        amount: Number(paymentScopeSummary?.strict_bank_only_total) || 0,
        supplierCount: Number(paymentScopeSummary?.strict_supplier_count) || 0,
        className: 'wc-split-card--strict',
      },
      {
        key: 'manual',
        label: 'Manual / off-bank',
        amount: Number(paymentScopeSummary?.manual_journal_total) || 0,
        supplierCount: Number(paymentScopeSummary?.manual_supplier_count) || 0,
        className: 'wc-split-card--manual',
      },
      {
        key: 'combined',
        label: 'Supplier total_paid',
        amount: Number(paymentScopeSummary?.combined_supplier_paid_total) || 0,
        supplierCount: Number(paymentScopeSummary?.combined_supplier_count) || 0,
        className: 'wc-split-card--combined',
      },
    ],
    [paymentScopeSummary],
  );

  const paymentScopeBadges = useMemo(
    () => [
      {
        key: 'strict-only',
        label: `strict-only ${Number(paymentScopeSummary?.strict_only_supplier_count) || 0}`,
        className: 'payment-scope-badge--strict',
      },
      {
        key: 'manual-only',
        label: `manual-only ${Number(paymentScopeSummary?.manual_only_supplier_count) || 0}`,
        className: 'payment-scope-badge--manual',
      },
      {
        key: 'overlap',
        label: `strict + manual ${Number(paymentScopeSummary?.strict_and_manual_overlap_count) || 0}`,
        className: 'payment-scope-badge--split',
      },
    ],
    [paymentScopeSummary],
  );

  const truthBoundaryBadges = useMemo(
    () => [
      {
        key: 'registry',
        label: `registry primary ${Number(truthBoundarySummary?.registry_primary_supplier_count) || 0}`,
        className: 'truth-source-badge--registry',
      },
      {
        key: 'rs',
        label: `RS backstop ${Number(truthBoundarySummary?.rs_backstop_supplier_count) || 0}`,
        className: 'truth-source-badge--rs',
      },
      {
        key: 'legacy',
        label: `legacy audit-only ${Number(truthBoundarySummary?.legacy_truth_assist_supplier_count) || 0}`,
        className: 'truth-source-badge--legacy',
      },
    ],
    [truthBoundarySummary],
  );

  const paymentScopeNotes = useMemo(
    () =>
      Array.isArray(paymentScopeSummary?.scope_notes)
        ? paymentScopeSummary.scope_notes.filter(Boolean)
        : [],
    [paymentScopeSummary],
  );

  const agingBucketData = useMemo(() => {
    const maxDebt = Math.max(
      ...AGING_BUCKETS.map((b) => Number(agingSummary[b.key]?.total_debt) || 0),
      1,
    );
    return AGING_BUCKETS.map((b) => {
      const s = agingSummary[b.key] || {};
      const debt = Number(s.total_debt) || 0;
      const count = Number(s.count) || 0;
      return { ...b, debt, count, pct: (debt / maxDebt) * 100 };
    });
  }, [agingSummary]);

  const chartData = useMemo(() => {
    return apTrend.map((r) => ({
      month: monthLabel(r.month),
      შესყიდვა: Number(r.rs_purchases) || 0,
      გადახდა: Number(r.estimated_payments) || 0,
      cumDebt: Number(r.cumulative_debt) || 0,
    }));
  }, [apTrend]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return aging.filter((r) =>
      !needle || String(r.org || '').toLowerCase().includes(needle),
    );
  }, [aging, search]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    switch (sortKey) {
      case 'debt_desc': return arr.sort((a, b) => (Number(b.total_debt) || 0) - (Number(a.total_debt) || 0));
      case 'debt_asc':  return arr.sort((a, b) => (Number(a.total_debt) || 0) - (Number(b.total_debt) || 0));
      case 'days_desc': return arr.sort((a, b) => (Number(b.days_since_last) || 0) - (Number(a.days_since_last) || 0));
      case 'days_asc':  return arr.sort((a, b) => (Number(a.days_since_last) || 0) - (Number(b.days_since_last) || 0));
      case 'org_asc':   return arr.sort((a, b) => String(a.org || '').localeCompare(String(b.org || ''), 'ka'));
      default:          return arr;
    }
  }, [filtered, sortKey]);

  if (!aging.length) {
    return (
      <div className="cashflow-page pnl-empty">
        <div
          className="kpi-card"
          style={{ maxWidth: 520, margin: '48px auto', textAlign: 'center' }}
        >
          <div className="kpi-label">საბრუნავი კაპიტალის მონაცემები ჯერ არ არის</div>
          <div className="kpi-sub" style={{ marginTop: 12 }}>
            გაუშვი ტერმინალში:
          </div>
          <code className="pnl-code-hint">python generate_dashboard_data.py</code>
        </div>
      </div>
    );
  }

  const chartInterval = Math.max(0, Math.floor(chartData.length / 24) * 2);

  return (
    <div className="cashflow-page">

      {/* Tab Hero */}
      <div className="tab-hero">
        <span className="tab-hero-title">💰 საბრუნავი კაპიტალი — AP Aging</span>
        <span className="tab-hero-desc">მომწოდებლების დავალიანება, Aging Buckets, AP Trend</span>
      </div>

      {/* ---- KPI ბარათები ---- */}
      <div className="kpi-grid">
        <div className="kpi-card kpi-card--warn">
          <div className="kpi-label">სულ დავალიანება (AP)</div>
          <div className="kpi-value amount-negative">{fmt(kpis.totalDebt)}</div>
          <div className="kpi-sub">{kpis.count} მომწოდებელი</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">მომწოდებლების რაოდენობა</div>
          <div className="kpi-value amount-neutral">{kpis.count}</div>
          <div className="kpi-sub">დავალიანებით</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">საშუალო aging (დღე)</div>
          <div
            className={`kpi-value ${
              kpis.avgDays > 90
                ? 'amount-negative'
                : kpis.avgDays > 30
                ? 'amount-neutral'
                : 'amount-positive'
            }`}
          >
            {Math.round(kpis.avgDays)}
          </div>
          <div className="kpi-sub">ბოლო ზედნადების დღეებიდან</div>
        </div>
        <div className="kpi-card kpi-card--accent">
          <div className="kpi-label">კუმულაციური ვალი (ბოლო თვე)</div>
          <div className="kpi-value amount-negative">{fmt(kpis.cumDebt)}</div>
          <div className="kpi-sub">AP trend-ის მიხედვით</div>
        </div>
      </div>

      <div className="chart-card chart-card--wide">
        <div className="chart-card-header">
          <h3>Payment split + truth boundary</h3>
          <span className="chart-card-header-desc">
            AP row-ები strict bank-ს, manual/off-bank-ს და supplier truth provenance-ს ცალ-ცალკე აჩვენებს
          </span>
        </div>
        <div className="wc-split-grid">
          {paymentSplitCards.map((card) => (
            <div key={card.key} className={`wc-split-card ${card.className}`}>
              <div className="wc-split-card-label">{card.label}</div>
              <div className="wc-split-card-value">{fmt(card.amount)}</div>
              <div className="wc-split-card-sub">{card.supplierCount} მომწოდებელი</div>
            </div>
          ))}
        </div>
        <div className="wc-chip-row">
          {paymentScopeBadges.map((item) => (
            <span key={item.key} className={`badge payment-scope-badge ${item.className}`}>
              {item.label}
            </span>
          ))}
        </div>
        <div className="wc-truth-panel">
          <div className="wc-truth-panel-title">Strict supplier truth</div>
          <div className="wc-chip-row">
            {truthBoundaryBadges.map((item) => (
              <span key={item.key} className={`badge truth-source-badge ${item.className}`}>
                {item.label}
              </span>
            ))}
          </div>
          {truthBoundarySummary?.summary_ka ? (
            <p className="wc-truth-panel-note">{truthBoundarySummary.summary_ka}</p>
          ) : null}
          {paymentScopeNotes.length > 0 ? (
            <p className="wc-truth-panel-note">{paymentScopeNotes.join(' ')}</p>
          ) : null}
        </div>
      </div>

      {/* ---- Aging Buckets ---- */}
      <div className="chart-card chart-card--wide">
        <h3>Aging Buckets — დავალიანება ასაკის მიხედვით</h3>
        <div className="wc-aging-bars">
          {agingBucketData.map((b) => (
            <div key={b.key} className="wc-aging-row">
              <div className="wc-aging-label">
                <span className={`badge ${b.cls}`}>{b.label}</span>
              </div>
              <div className="wc-aging-bar-wrap">
                <div
                  className={`wc-aging-bar-fill ${b.cls}-fill`}
                  style={{ width: `${b.pct}%` }}
                />
              </div>
              <div className="wc-aging-stats">
                <span className="amount-negative">{fmt(b.debt)}</span>
                <span className="wc-aging-count">{b.count} მომწ.</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ---- AP Trend ჩარტი ---- */}
      {chartData.length > 0 && (
        <div className="chart-card chart-card--wide">
          <h3>AP Trend — შესყიდვა, გადახდა, კუმულაციური ვალი</h3>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 8, right: 60, left: 10, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3040" />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11, fill: '#8899aa' }}
                  angle={-45}
                  textAnchor="end"
                  interval={chartInterval}
                />
                <YAxis
                  yAxisId="left"
                  tick={{ fontSize: 11, fill: '#8899aa' }}
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fontSize: 11, fill: '#e05c6e' }}
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ paddingTop: 8, fontSize: 13 }} />
                <Bar yAxisId="left" dataKey="შესყიდვა" name="შესყიდვა (RS)" fill="#4f8ef7" opacity={0.75} />
                <Bar yAxisId="left" dataKey="გადახდა" name="გადახდა" fill="#34c97e" opacity={0.75} />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="cumDebt"
                  name="კუმულ. ვალი"
                  stroke="#e05c6e"
                  strokeWidth={2}
                  dot={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ---- ცხრილი — ძებნა + სორტი ---- */}
      <div className="wc-table-controls">
        <input
          type="text"
          className="search-input search-input-compact"
          placeholder="ძებნა ორგანიზაციით…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoComplete="off"
        />
        <label className="wc-sort-label">
          <span>სორტი:</span>
          <select
            className="pnl-month-select"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value)}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <span className="wc-count-hint">{sorted.length} / {aging.length} მომწოდებელი</span>
        <ExportButton
          filename={`AP_Aging_${new Date().toISOString().slice(0, 10)}.xlsx`}
          sheets={[{
            name: 'AP Aging',
            rows: sorted.map((r) => ({
              ორგანიზაცია: r.org || '',
              ობიექტი: r.object || '',
              ზედნადები: Number(r.waybill_count) || 0,
              რეალური_ჯამი: Number(r.rs_total) || 0,
              strict_ბანკი: Number(r.strict_bank_paid) || 0,
              manual_paid: Number(r.manual_paid) || 0,
              გადახდილი: Number(r.total_paid) || 0,
              დავალიანება: Number(r.total_debt) || 0,
              ბოლო_ზედნადები: r.last_waybill_date || '',
              დღეები: Number(r.days_since_last) || 0,
              aging_bucket: r.aging_bucket || '',
              scope: r.payment_scope || '',
            })),
          }]}
        />
      </div>

      <div className="table-wrapper cashflow-table pnl-table-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>ორგანიზაცია</th>
              <th>ობიექტი</th>
              <th>ზედნადები</th>
              <th>რეალური ჯამი</th>
              <th>Strict ბანკი</th>
              <th>Manual / off-bank</th>
              <th>გადახდილი</th>
              <th>დავალიანება</th>
              <th>ბოლო ზედნადები</th>
              <th>დღეები</th>
              <th>Aging</th>
              <th>Scope</th>
              <th>Truth</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, idx) => {
              const objColor = OBJECT_COLORS[r.object] || '#8899aa';
              const debt = Number(r.total_debt) || 0;
              const strictPaid = Number(r.strict_bank_paid) || 0;
              const manualPaid = Number(r.manual_paid) || 0;
              const scopeMeta = getPaymentScopeMeta(r.payment_scope);
              const truthMeta = getOfficialNameSourceMeta(r.official_name_truth_source);
              const truthSummary = compactText(r.supplier_truth_summary, 92);
              const truthSources = formatTruthSources(r.supplier_truth_sources);
              const truthTitle = [r.supplier_truth_summary, truthSources]
                .filter(Boolean)
                .join(' | ');
              return (
                <tr
                  key={`wc-aging-${idx}`}
                  onClick={() => onSupplierClick && onSupplierClick(r)}
                  style={{ cursor: onSupplierClick ? 'pointer' : 'default' }}
                  title={onSupplierClick ? 'კლიკი — დეტალები' : ''}
                >
                  <td>{idx + 1}</td>
                  <td className="wc-org-cell">{r.org}</td>
                  <td>
                    {r.object ? (
                      <span
                        className="badge"
                        style={{
                          background: `${objColor}22`,
                          color: objColor,
                          border: `1px solid ${objColor}55`,
                        }}
                      >
                        {r.object}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>{r.waybill_count ?? '—'}</td>
                  <td className="amount-neutral">{fmt(r.total_effective)}</td>
                  <td className={amountClass(strictPaid)}>{fmt(strictPaid)}</td>
                  <td className={amountClass(manualPaid)}>{fmt(manualPaid)}</td>
                  <td className="amount-positive">{fmt(r.total_paid)}</td>
                  <td className={debt > 0 ? 'amount-negative' : 'amount-neutral'}>
                    {fmt(debt)}
                  </td>
                  <td>{r.last_waybill_date || '—'}</td>
                  <td
                    className={
                      (r.days_since_last || 0) > 90
                        ? 'amount-negative'
                        : (r.days_since_last || 0) > 30
                        ? 'amount-neutral'
                        : 'amount-positive'
                    }
                  >
                    {r.days_since_last ?? '—'}
                  </td>
                  <td>
                    <span className={`badge badge-aging-table ${agingClass(r.aging_bucket)}`}>
                      {r.aging_bucket || '—'}
                    </span>
                  </td>
                  <td>
                    <div className="wc-meta-cell" title={r.payment_scope_note || scopeMeta.label}>
                      <span className={`badge payment-scope-badge ${scopeMeta.className}`}>
                        {scopeMeta.label}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div className="wc-meta-cell" title={truthTitle || truthMeta.label}>
                      <span className={`badge truth-source-badge ${truthMeta.className}`}>
                        {truthMeta.label}
                      </span>
                      {truthSummary ? (
                        <span className="wc-meta-note wc-meta-note--strong">{truthSummary}</span>
                      ) : null}
                      {truthSources ? <span className="wc-meta-note">{truthSources}</span> : null}
                    </div>
                  </td>
                </tr>
              );
            })}
            {sorted.length === 0 && (
              <tr>
                <td colSpan="14" style={{ textAlign: 'center' }}>
                  მომწოდებელი არ მოიძებნა
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
