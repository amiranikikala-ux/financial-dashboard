import { useMemo } from 'react';
import {
  Bar,
  ComposedChart,
  CartesianGrid,
  Legend,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 0,
});
const fmt = (v) => GEL.format(Number(v) || 0);
const fmtPct = (v, sign = true) => {
  const n = Number(v) || 0;
  return `${sign && n > 0 ? '+' : ''}${n.toFixed(1)}%`;
};

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
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color || '#ccc' }}>
          {p.name}:{' '}
          {p.dataKey === 'seasonality_index'
            ? Number(p.value).toFixed(2)
            : fmt(p.value)}
        </div>
      ))}
    </div>
  );
}

function ForecastBar({ fill, x, y, width, height, isForecast }) {
  if (!height || height <= 0) return null;
  return (
    <rect
      x={x}
      y={y}
      width={width}
      height={height}
      fill={fill}
      fillOpacity={isForecast ? 0.35 : 0.82}
      stroke={isForecast ? fill : 'none'}
      strokeWidth={isForecast ? 1 : 0}
      strokeDasharray={isForecast ? '4 2' : '0'}
    />
  );
}

export default function Forecast({ forecast, monthlyPnl }) {
  const forecastBlock = forecast;
  const yoy = useMemo(() => forecastBlock?.yoy || {}, [forecastBlock]);
  const seasonality = useMemo(() => forecastBlock?.seasonality || {}, [forecastBlock]);
  const forecastData = useMemo(() => forecastBlock?.forecast || {}, [forecastBlock]);
  const forecastMonths = useMemo(
    () => (Array.isArray(forecastData.months) ? forecastData.months : []),
    [forecastData],
  );
  const forecastMethod = forecastData.method || 'SMA-6';

  const historicalRows = useMemo(() => {
    const all = Array.isArray(monthlyPnl) ? monthlyPnl : [];
    return all.slice(-12);
  }, [monthlyPnl]);

  const mergedChartData = useMemo(() => {
    const hist = historicalRows.map((m) => ({
      month: monthLabel(m.month),
      income: Number(m.total?.pos_income) || 0,
      expenses: Number(m.total?.expenses) || 0,
      net: Number(m.total?.net) || 0,
      is_forecast: false,
    }));
    const fcast = forecastMonths.map((m) => ({
      month: monthLabel(m.month),
      income: Number(m.total?.pos_income) || 0,
      expenses: Number(m.total?.expenses) || 0,
      net: Number(m.total?.net) || 0,
      is_forecast: true,
    }));
    return [...hist, ...fcast];
  }, [historicalRows, forecastMonths]);

  const firstForecastMonth = useMemo(() => {
    const f = mergedChartData.find((r) => r.is_forecast);
    return f ? f.month : null;
  }, [mergedChartData]);

  const forecastZoneEnd =
    mergedChartData.length > 0 ? mergedChartData[mergedChartData.length - 1].month : null;

  const seasonChartData = useMemo(() => {
    const by = Array.isArray(seasonality.by_calendar_month)
      ? seasonality.by_calendar_month
      : [];
    return by.map((r) => ({
      label: r.label || String(r.calendar_month),
      avg_income: Number(r.avg_income) || 0,
      avg_expenses: Number(r.avg_expenses) || 0,
      avg_net: Number(r.avg_net) || 0,
      seasonality_index: Number(r.seasonality_index) || 0,
      calendar_month: r.calendar_month,
    }));
  }, [seasonality]);

  const forecastObjects = useMemo(() => {
    const s = new Set();
    for (const m of forecastMonths) {
      for (const k of Object.keys(m.objects || {})) s.add(k);
    }
    return Array.from(s).sort((a, b) => a === 'საერთო' ? 1 : b === 'საერთო' ? -1 : a.localeCompare(b));
  }, [forecastMonths]);

  const forecastTotals = useMemo(() => {
    let income = 0; let expenses = 0; let net = 0;
    const byObj = {};
    for (const m of forecastMonths) {
      income += Number(m.total?.pos_income) || 0;
      expenses += Number(m.total?.expenses) || 0;
      net += Number(m.total?.net) || 0;
      for (const [obj, vals] of Object.entries(m.objects || {})) {
        if (!byObj[obj]) byObj[obj] = { net: 0, expenses: 0 };
        byObj[obj].net += Number(vals.net) || 0;
        byObj[obj].expenses += Number(vals.expenses) || 0;
      }
    }
    return { income, expenses, net, byObj };
  }, [forecastMonths]);

  if (!forecastBlock) {
    return (
      <div className="cashflow-page pnl-empty">
        <div className="kpi-card" style={{ maxWidth: 520, margin: '48px auto', textAlign: 'center' }}>
          <div className="kpi-label">პროგნოზი ჯერ არ არის</div>
          <div className="kpi-sub" style={{ marginTop: 12 }}>გაუშვი ტერმინალში:</div>
          <code className="pnl-code-hint">python generate_dashboard_data.py</code>
        </div>
      </div>
    );
  }

  const incChg = Number(yoy.income_change_pct) || 0;
  const expChg = Number(yoy.expenses_change_pct) || 0;
  const netChg = Number(yoy.net_change_pct) || 0;
  const expenseHealthy = expChg <= incChg;
  const strongest = seasonality.strongest_month || {};
  const weakest = seasonality.weakest_month || {};

  return (
    <div className="cashflow-page">

      {/* Tab Hero */}
      <div className="tab-hero">
        <span className="tab-hero-title">🔮 პროგნოზი — Forecast + სეზონურობა + YoY</span>
        <span className="tab-hero-desc">SMA-6 მოდელი · ბოლო 12 თვის ტრენდის საფუძველზე</span>
      </div>

      {/* YoY KPI */}
      <div className="kpi-grid">
        <div className={`kpi-card ${incChg >= 0 ? 'kpi-card--accent' : 'kpi-card--warn'}`}>
          <div className="kpi-label">შემოსავლის ცვლილება YoY</div>
          <div className={`kpi-value ${incChg >= 0 ? 'amount-positive' : 'amount-negative'}`} style={{ fontSize: '1.6rem' }}>
            <span style={{ fontSize: '1.8rem', lineHeight: 1 }}>{incChg >= 0 ? '▲' : '▼'}</span>{' '}
            {fmtPct(incChg)}
          </div>
          <div className="kpi-sub">ბოლო 12: <span className="amount-positive">{fmt(yoy.last_12m?.income)}</span></div>
          <div className="kpi-sub">წინა 12: <span className="amount-neutral">{fmt(yoy.prev_12m?.income)}</span></div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">ხარჯის ცვლილება YoY</div>
          <div className={`kpi-value ${expenseHealthy ? 'amount-positive' : 'amount-negative'}`} style={{ fontSize: '1.6rem' }}>
            <span style={{ fontSize: '1.8rem', lineHeight: 1 }}>{expChg >= 0 ? '▲' : '▼'}</span>{' '}
            {fmtPct(expChg)}
          </div>
          <div className="kpi-sub" style={{ color: expenseHealthy ? '#22c55e' : '#eab308' }}>
            {expenseHealthy ? '✓ ხარჯი ≤ შემოსავლის ზრდა' : '⚠ ხარჯი უფრო სწრაფად იზრდება'}
          </div>
          <div className="kpi-sub">ბოლო 12: <span className="amount-negative">{fmt(yoy.last_12m?.expenses)}</span></div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Net ცვლილება YoY</div>
          <div className={`kpi-value ${netChg >= 0 ? 'amount-positive' : 'amount-negative'}`} style={{ fontSize: '1.6rem' }}>
            <span style={{ fontSize: '1.8rem', lineHeight: 1 }}>{netChg >= 0 ? '▲' : '▼'}</span>{' '}
            {fmtPct(netChg)}
          </div>
          <div className="kpi-sub">ბოლო 12: <span className={yoy.last_12m?.net >= 0 ? 'amount-positive' : 'amount-negative'}>{fmt(yoy.last_12m?.net)}</span></div>
          <div className="kpi-sub">წინა 12: <span className="amount-neutral">{fmt(yoy.prev_12m?.net)}</span></div>
        </div>
      </div>

      {/* Forecast Chart */}
      <div className="chart-card chart-card--wide">
        <div className="chart-card-header">
          <h3>6-თვიანი პროგნოზი — <span className="forecast-method-badge">{forecastMethod}</span></h3>
          <span className="chart-card-header-desc">ბოლო 12 ისტ. + 6 forecast</span>
        </div>
        <div className="chart-area">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={mergedChartData} margin={{ top: 8, right: 20, left: 10, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3040" />
              {firstForecastMonth && forecastZoneEnd && (
                <ReferenceArea
                  x1={firstForecastMonth}
                  x2={forecastZoneEnd}
                  fill="rgba(59,130,246,0.04)"
                  label={{ value: `პროგნოზი (${forecastMethod})`, fill: '#4f8ef755', fontSize: 11, position: 'insideTopLeft' }}
                />
              )}
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#8899aa' }} angle={-45} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 11, fill: '#8899aa' }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ paddingTop: 8, fontSize: 13 }} />
              <Bar
                dataKey="income"
                name="POS შემოსავალი"
                fill="#4f8ef7"
                shape={(props) => {
                  const entry = mergedChartData[props.index] || {};
                  return <ForecastBar {...props} isForecast={entry.is_forecast} />;
                }}
              />
              <Bar
                dataKey="expenses"
                name="ხარჯი"
                fill="#e05c6e"
                shape={(props) => {
                  const entry = mergedChartData[props.index] || {};
                  return <ForecastBar {...props} fill="#e05c6e" isForecast={entry.is_forecast} />;
                }}
              />
              <Line type="monotone" dataKey="net" name="net" stroke="#34c97e" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="forecast-legend-hint">
          <span className="forecast-legend-solid">▬ ისტორიული</span>
          <span className="forecast-legend-dashed">┅ პროგნოზი ({forecastMethod})</span>
        </div>
      </div>

      {/* Seasonality Chart */}
      {seasonChartData.length > 0 && (
        <div className="chart-card chart-card--wide">
          <h3>სეზონურობა — თვიური საშუალო</h3>
          <div className="forecast-season-kpis">
            <div className="kpi-card" style={{ borderTop: '3px solid #22c55e', flex: 1 }}>
              <div className="kpi-label">☀️ ძლიერი თვე</div>
              <div className="kpi-value amount-positive">{strongest.label || '—'}</div>
              <div className="kpi-sub">ინდექსი: <strong style={{ color: '#34c97e' }}>{Number(strongest.seasonality_index || 0).toFixed(2)}</strong></div>
              <div className="kpi-sub">საშ. net: <span className="amount-positive">{fmt(seasonChartData.find(r => r.calendar_month === strongest.calendar_month)?.avg_net)}</span></div>
            </div>
            <div className="kpi-card" style={{ borderTop: '3px solid #ef4444', flex: 1 }}>
              <div className="kpi-label">❄️ სუსტი თვე</div>
              <div className="kpi-value amount-negative">{weakest.label || '—'}</div>
              <div className="kpi-sub">ინდექსი: <strong style={{ color: '#e05c6e' }}>{Number(weakest.seasonality_index || 0).toFixed(2)}</strong></div>
              <div className="kpi-sub">საშ. net: <span className="amount-negative">{fmt(seasonChartData.find(r => r.calendar_month === weakest.calendar_month)?.avg_net)}</span></div>
            </div>
          </div>
          <div className="chart-area">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={seasonChartData} margin={{ top: 8, right: 60, left: 10, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3040" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#8899aa' }} />
                <YAxis yAxisId="left" tick={{ fontSize: 11, fill: '#8899aa' }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: '#34c97e' }} domain={[0, 2.5]} tickFormatter={(v) => v.toFixed(1)} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ paddingTop: 8, fontSize: 13 }} />
                <Bar yAxisId="left" dataKey="avg_income" name="საშ. შემოსავალი" fill="#4f8ef7" opacity={0.75} />
                <Bar yAxisId="left" dataKey="avg_expenses" name="საშ. ხარჯი" fill="#e05c6e" opacity={0.65} />
                <Line yAxisId="right" type="monotone" dataKey="seasonality_index" name="სეზ. ინდექსი" stroke="#34c97e" strokeWidth={2} dot={{ r: 3, fill: '#34c97e' }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Forecast Table */}
      {forecastMonths.length > 0 && (
        <div className="chart-card chart-card--wide">
          <h3>პროგნოზის ცხრილი <span className="forecast-method-badge">{forecastMethod}</span></h3>
          <div className="table-wrapper cashflow-table pnl-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>თვე</th>
                  {forecastObjects.map(obj => (
                    <th key={obj}>{obj} {obj === 'საერთო' ? 'ხარჯი' : 'net'}</th>
                  ))}
                  <th>სულ POS</th>
                  <th>სულ ხარჯი</th>
                  <th>სულ net</th>
                </tr>
              </thead>
              <tbody>
                {forecastMonths.map((m) => {
                  const totNet = Number(m.total?.net) || 0;
                  return (
                    <tr key={m.month} className="forecast-row">
                      <td>{monthLabel(m.month)}</td>
                      {forecastObjects.map(obj => {
                        if (obj === 'საერთო') {
                          const exp = Number(m.objects?.[obj]?.expenses) || 0;
                          return <td key={obj} className="amount-negative">{exp ? fmt(exp) : '—'}</td>;
                        }
                        const net = Number(m.objects?.[obj]?.net) || 0;
                        return <td key={obj} className={net >= 0 ? 'amount-positive' : 'amount-negative'}>{fmt(net)}</td>;
                      })}
                      <td className="amount-positive">{fmt(m.total?.pos_income)}</td>
                      <td className="amount-negative">{fmt(m.total?.expenses)}</td>
                      <td className={totNet >= 0 ? 'amount-positive' : 'amount-negative'}>{fmt(totNet)}</td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr className="pnl-tfoot-total">
                  <td><strong>ჯამი ({forecastMonths.length} თვე)</strong></td>
                  {forecastObjects.map(obj => {
                    if (obj === 'საერთო') {
                      const exp = forecastTotals.byObj[obj]?.expenses || 0;
                      return <td key={obj} className="amount-negative"><strong>{fmt(exp)}</strong></td>;
                    }
                    const net = forecastTotals.byObj[obj]?.net || 0;
                    return <td key={obj} className={net >= 0 ? 'amount-positive' : 'amount-negative'}><strong>{fmt(net)}</strong></td>;
                  })}
                  <td className="amount-positive"><strong>{fmt(forecastTotals.income)}</strong></td>
                  <td className="amount-negative"><strong>{fmt(forecastTotals.expenses)}</strong></td>
                  <td className={forecastTotals.net >= 0 ? 'amount-positive' : 'amount-negative'}><strong>{fmt(forecastTotals.net)}</strong></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
