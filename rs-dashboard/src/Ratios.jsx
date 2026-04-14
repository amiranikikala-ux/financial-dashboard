import { useMemo } from 'react';
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
const fmtPct = (v) => `${Number(v || 0).toFixed(1)}%`;

const OBJECT_COLORS = {
  'ოზურგეთი': '#4f8ef7',
  'დვაბზუ': '#34c97e',
  'გაუნაწილებელი': '#8899aa',
  'საერთო': '#f7a434',
};

function monthLabel(m) {
  if (!m) return '—';
  const [y, mo] = m.split('-');
  if (!y || !mo) return m;
  return `${mo}/${String(y).slice(2)}`;
}

function marginColor(pct) {
  if (pct >= 50) return '#34c97e';
  if (pct >= 30) return '#f7d434';
  return '#e05c6e';
}
function paymentColor(pct) {
  if (pct >= 90) return '#34c97e';
  if (pct >= 70) return '#f7d434';
  return '#e05c6e';
}
function apDaysColor(days) {
  if (days < 45) return '#34c97e';
  if (days <= 90) return '#f7d434';
  return '#e05c6e';
}

function Gauge({ value, max = 100, color }) {
  const pct = Math.min(100, Math.max(0, (Number(value) / max) * 100));
  return (
    <div className="ratio-gauge">
      <div
        className="ratio-gauge-fill"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  );
}

function shortLabel(s, max = 42) {
  if (!s) return '—';
  const t = String(s).replace(/^\(\d+.*?\)\s*/, '').trim();
  return t.length > max ? `${t.slice(0, max)}…` : t;
}

function agingClass(bucket) {
  const map = {
    '0-30':   'aging-0-30',
    '31-60':  'aging-31-60',
    '61-90':  'aging-61-90',
    '91-180': 'aging-91-180',
    '180+':   'aging-180-plus',
  };
  return map[String(bucket)] || 'aging-0-30';
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="pnl-tooltip">
      <div className="pnl-tooltip-label">{label}</div>
      {payload.map((p, i) => (
        <div key={`${String(p.dataKey ?? 'k')}-${i}`} style={{ color: p.color || '#ccc' }}>
          {p.name}:{' '}
          {p.dataKey === 'net_margin_pct'
            ? fmtPct(p.value)
            : fmt(p.value)}
        </div>
      ))}
    </div>
  );
}

export default function Ratios({ financialRatios }) {
  const ratios = financialRatios;

  const company = useMemo(() => ratios?.company || {}, [ratios]);
  const objects = useMemo(() => ratios?.objects || {}, [ratios]);
  const monthlyTrend = useMemo(
    () => (Array.isArray(ratios?.monthly_trend) ? ratios.monthly_trend : []),
    [ratios],
  );
  const topRisk = useMemo(
    () => (Array.isArray(ratios?.top_risk_suppliers) ? ratios.top_risk_suppliers : []),
    [ratios],
  );

  const chartData = useMemo(() => {
    const last12 = monthlyTrend.slice(-12);
    return last12.map((r) => ({
      month: monthLabel(r.month),
      income: Number(r.income_amount) || 0,
      expenses: Number(r.expenses_amount) || 0,
      net_margin_pct: Number(r.net_margin_pct ?? r.gross_margin_pct) || 0,
    }));
  }, [monthlyTrend]);

  if (!ratios) {
    return (
      <div className="cashflow-page pnl-empty">
        <div
          className="kpi-card"
          style={{ maxWidth: 520, margin: '48px auto', textAlign: 'center' }}
        >
          <div className="kpi-label">კოეფიციენტები ჯერ არ არის</div>
          <div className="kpi-sub" style={{ marginTop: 12 }}>
            გაუშვი ტერმინალში:
          </div>
          <code className="pnl-code-hint">python generate_dashboard_data.py</code>
        </div>
      </div>
    );
  }

  const gm = Number(company.net_margin_pct ?? company.gross_margin_pct) || 0;
  const pr = Number(company.payment_ratio_pct) || 0;
  const apd = Number(company.ap_days) || 0;
  const avgNet = Number(company.avg_monthly_net) || 0;

  const objectKeys = ['ოზურგეთი', 'დვაბზუ'].filter((k) => objects[k]);

  return (
    <div className="cashflow-page">

      {/* Tab Hero */}
      <div className="tab-hero">
        <span className="tab-hero-title">📐 კოეფიციენტები — ფინანსური Ratios</span>
        <span className="tab-hero-desc">Net Margin · Payment Ratio · AP Days · ობიექტების შედარება</span>
        <ExportButton
          filename={`Ratios_${new Date().toISOString().slice(0, 10)}.xlsx`}
          sheets={[
            {
              name: 'თვიური ტრენდი',
              rows: monthlyTrend.map((r) => ({
                თვე: r.month || '',
                შემოსავალი: Number(r.income_amount) || 0,
                ხარჯები: Number(r.expenses_amount) || 0,
                net_margin_pct: Number(r.net_margin_pct ?? r.gross_margin_pct) || 0,
              })),
            },
            {
              name: 'Top Risk',
              rows: topRisk.map((r) => ({
                ორგანიზაცია: r.org || '',
                დავალიანება: Number(r.debt) || 0,
                payment_ratio_pct: Number(r.payment_ratio_pct) || 0,
                AP_days: Number(r.ap_days) || 0,
              })),
            },
          ]}
        />
      </div>

      {/* ---- A. კომპანიის KPI ---- */}
      <div className="kpi-grid">

        {/* Net Margin */}
        <div className="kpi-card">
          <div className="kpi-label">Net Margin</div>
          <div
            className="kpi-value"
            style={{ color: marginColor(gm) }}
          >
            {fmtPct(gm)}
          </div>
          <Gauge value={gm} max={100} color={marginColor(gm)} />
          <div className="kpi-sub" style={{ marginTop: 6 }}>
            შემოსავალი: <span className="amount-positive">{fmt(company.total_income)}</span>
          </div>
          <div className="kpi-sub">
            ხარჯი: <span className="amount-negative">{fmt(company.total_expenses)}</span>
          </div>
        </div>

        {/* Payment Ratio */}
        <div className="kpi-card">
          <div className="kpi-label">Payment Ratio</div>
          <div
            className="kpi-value"
            style={{ color: paymentColor(pr) }}
          >
            {fmtPct(pr)}
          </div>
          <Gauge value={pr} max={100} color={paymentColor(pr)} />
          <div className="kpi-sub" style={{ marginTop: 6 }}>
            გადახდილი: <span className="amount-positive">{fmt(company.total_paid)}</span>
          </div>
          <div className="kpi-sub">
            სულ ვალდებ.: <span className="amount-neutral">{fmt(company.total_effective)}</span>
          </div>
        </div>

        {/* AP Days */}
        <div className="kpi-card">
          <div className="kpi-label">AP Days</div>
          <div
            className="kpi-value"
            style={{ color: apDaysColor(apd) }}
          >
            {apd} <span style={{ fontSize: '0.6em', color: '#8899aa' }}>დღე</span>
          </div>
          <Gauge value={Math.min(apd, 180)} max={180} color={apDaysColor(apd)} />
          <div className="kpi-sub" style={{ marginTop: 6 }}>
            &lt;45 კარგი · 45–90 ყურადღება · &gt;90 კრიტიკული
          </div>
          <div className="kpi-sub">
            სულ დავალიანება: <span className="amount-negative">{fmt(company.total_debt)}</span>
          </div>
        </div>

        {/* Average Monthly Net */}
        <div className="kpi-card kpi-card--accent">
          <div className="kpi-label">საშ. თვიური Net</div>
          <div
            className={`kpi-value ${avgNet >= 0 ? 'amount-positive' : 'amount-negative'}`}
          >
            {fmt(avgNet)}
          </div>
          <div className="kpi-sub" style={{ marginTop: 6 }}>
            სულ net: <span className={company.total_net >= 0 ? 'amount-positive' : 'amount-negative'}>{fmt(company.total_net)}</span>
          </div>
        </div>
      </div>

      {/* ---- B. ობიექტების შედარება ---- */}
      {objectKeys.length > 0 && (() => {
        const objGMs = objectKeys.map(k => ({ k, gm: Number(objects[k]?.net_margin_pct ?? objects[k]?.gross_margin_pct) || 0 }));
        const maxGM = Math.max(...objGMs.map(x => x.gm));
        const winnerObj = objGMs.find(x => x.gm === maxGM)?.k;
        return (
        <div className="ratio-objects-grid">
          {objectKeys.map((obj) => {
            const o = objects[obj] || {};
            const ogm = Number(o.net_margin_pct ?? o.gross_margin_pct) || 0;
            const color = OBJECT_COLORS[obj] || '#8899aa';
            const oNet = Number(o.avg_monthly_net) || 0;
            const isWinner = obj === winnerObj && objectKeys.length > 1;
            return (
              <div
                className="kpi-card ratio-obj-card"
                key={obj}
                style={{ borderTop: `2px solid ${color}` }}
              >
                <div className="kpi-label" style={{ color }}>
                  {obj}
                  {isWinner && <span className="ratio-obj-winner">🏆 წინ</span>}
                </div>

                <div className="ratio-obj-row">
                  <span className="ratio-obj-metric">Net Margin</span>
                  <span className="kpi-value" style={{ color: marginColor(ogm), fontSize: '1.4rem' }}>
                    {fmtPct(ogm)}
                  </span>
                </div>
                <Gauge value={ogm} max={100} color={marginColor(ogm)} />

                <div className="ratio-obj-row" style={{ marginTop: 10 }}>
                  <span className="ratio-obj-metric">საშ. თვ. Net</span>
                  <span className={oNet >= 0 ? 'amount-positive' : 'amount-negative'}>
                    {fmt(oNet)}
                  </span>
                </div>

                <div className="ratio-obj-stats">
                  <div className="ratio-obj-stat">
                    <span className="kpi-sub">შემოსავ. წილი</span>
                    <strong style={{ color }}>{fmtPct(o.share_of_income_pct)}</strong>
                  </div>
                  <div className="ratio-obj-stat">
                    <span className="kpi-sub">ხარჯის წილი</span>
                    <strong className="amount-negative">{fmtPct(o.share_of_expenses_pct)}</strong>
                  </div>
                </div>

                <div className="kpi-sub" style={{ marginTop: 6 }}>
                  POS: <span className="amount-positive">{fmt(o.total_income)}</span>
                  {' · '}
                  ხარჯი: <span className="amount-negative">{fmt(o.total_expenses)}</span>
                </div>
                <div className="kpi-sub">
                  net:{' '}
                  <span className={o.total_net >= 0 ? 'amount-positive' : 'amount-negative'}>
                    {fmt(o.total_net)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
        );
      })()}

      {/* ---- C. თვიური Trend ---- */}
      {chartData.length > 0 && (
        <div className="chart-card chart-card--wide">
          <h3>Net Margin Trend — ბოლო 12 თვე</h3>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 8, right: 60, left: 10, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3040" />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11, fill: '#8899aa' }}
                  angle={-45}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis
                  yAxisId="left"
                  tick={{ fontSize: 11, fill: '#8899aa' }}
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fontSize: 11, fill: '#34c97e' }}
                  tickFormatter={(v) => `${v.toFixed(0)}%`}
                  domain={[0, 100]}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ paddingTop: 8, fontSize: 13 }} />
                <Bar yAxisId="left" dataKey="income" name="შემოსავალი" fill="#4f8ef7" opacity={0.7} />
                <Bar yAxisId="left" dataKey="expenses" name="ხარჯი" fill="#e05c6e" opacity={0.7} />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="net_margin_pct"
                  name="Net Margin %"
                  stroke="#34c97e"
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: '#34c97e' }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ---- D. TOP რისკიანი მომწოდებლები ---- */}
      {topRisk.length > 0 && (
        <div className="chart-card chart-card--wide">
          <h3>TOP რისკიანი მომწოდებლები</h3>
          <div className="ratio-risk-grid">
            {topRisk.slice(0, 5).map((r, idx) => {
              const rpr = Number(r.payment_ratio_pct) || 0;
              const isHighRisk = rpr < 70;
              return (
                <div
                  key={`ratios-risk-${idx}`}
                  className={`ratio-risk-card ${isHighRisk ? 'ratio-risk-card--danger' : ''}`}
                >
                  <div className="ratio-risk-org" title={r.org}>
                    {shortLabel(r.org)}
                  </div>
                  <div className="ratio-risk-debt amount-negative">{fmt(r.total_debt)}</div>
                  <div className="ratio-risk-meta">
                    <span className={`badge ${agingClass(r.aging_bucket)}`}>
                      {r.aging_bucket || '—'}
                    </span>
                    <span
                      className="ratio-risk-pct"
                      style={{ color: paymentColor(rpr) }}
                    >
                      {fmtPct(rpr)} გად.
                    </span>
                    <span className="kpi-sub">{r.days_since_last ?? '—'} დღე</span>
                  </div>
                  <div className="ratio-gauge" style={{ marginTop: 6 }}>
                    <div
                      className="ratio-gauge-fill"
                      style={{ width: `${Math.min(100, rpr)}%`, background: paymentColor(rpr) }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
