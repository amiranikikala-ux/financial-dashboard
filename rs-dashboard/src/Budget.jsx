import { useMemo, useState } from 'react';
import DateRangePicker from './components/DateRangePicker.jsx';
import ExportButton from './components/ExportButton.jsx';
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
  const [, mo] = m.split('-');
  return mo || m;
}

// progress bar color: income/net — higher is better; expense — lower is better
function incomeColor(pct) {
  if (pct >= 95) return '#34c97e';
  if (pct >= 80) return '#f7d434';
  return '#e05c6e';
}
function expenseColor(pct) {
  // actual/plan: <=100 is good
  if (pct <= 100) return '#34c97e';
  return '#e05c6e';
}

function Gauge({ value, max = 100, color }) {
  const pct = Math.min(100, Math.max(0, (Number(value) / (max || 1)) * 100));
  return (
    <div className="ratio-gauge" style={{ marginTop: 6 }}>
      <div className="ratio-gauge-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function InlineGauge({ pct, color }) {
  const w = Math.min(100, Math.max(0, Number(pct) || 0));
  return (
    <div className="ratio-gauge budget-inline-gauge">
      <div className="ratio-gauge-fill" style={{ width: `${w}%`, background: color }} />
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="pnl-tooltip">
      <div className="pnl-tooltip-label">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color || '#ccc' }}>
          {p.name}: {fmt(p.value)}
        </div>
      ))}
    </div>
  );
}

export default function Budget({ budget }) {
  const annual = useMemo(() => budget?.annual || {}, [budget]);
  const monthly = useMemo(
    () => (Array.isArray(budget?.monthly) ? budget.monthly : []),
    [budget],
  );
  const ytd = useMemo(() => budget?.ytd_summary || {}, [budget]);

  const currentYear = String(ytd.current_year || new Date().getFullYear());

  const allYears = useMemo(
    () => Object.keys(annual).sort(),
    [annual],
  );

  const [selectedYear, setSelectedYear] = useState(() => {
    const years = Object.keys(annual).sort();
    return years.includes(currentYear) ? currentYear : years[years.length - 1] || currentYear;
  });

  // all months for the selected year
  const yearMonthlyAll = useMemo(
    () => monthly.filter((m) => String(m.month || '').startsWith(selectedYear)),
    [monthly, selectedYear],
  );

  const yearMonthsList = useMemo(
    () => yearMonthlyAll.map((m) => m.month).filter(Boolean).sort(),
    [yearMonthlyAll],
  );

  const [budgetFrom, setBudgetFrom] = useState('');
  const [budgetTo, setBudgetTo] = useState('');

  // reset month filter when year changes
  const [prevYear, setPrevYear] = useState(selectedYear);
  if (selectedYear !== prevYear) {
    setPrevYear(selectedYear);
    setBudgetFrom('');
    setBudgetTo('');
  }

  const yearMonthly = useMemo(() => {
    if (!budgetFrom && !budgetTo) return yearMonthlyAll;
    const ef = budgetFrom || yearMonthsList[0] || '';
    const et = budgetTo || yearMonthsList[yearMonthsList.length - 1] || '';
    return yearMonthlyAll.filter((m) => {
      const mo = m.month || '';
      return mo >= ef && mo <= et;
    });
  }, [yearMonthlyAll, budgetFrom, budgetTo, yearMonthsList]);

  // chart data
  const chartData = useMemo(() => {
    return yearMonthly.map((m) => ({
      month: monthLabel(m.month),
      plan_income: Number(m.plan?.income) || 0,
      actual_income: Number(m.actual?.income) || 0,
      plan_expenses: Number(m.plan?.expenses) || 0,
      actual_expenses: Number(m.actual?.expenses) || 0,
      plan_net: Number(m.plan?.net) || 0,
      actual_net: Number(m.actual?.net) || 0,
    }));
  }, [yearMonthly]);

  // year totals for tfoot
  const yearTotals = useMemo(() => {
    const t = { plan_inc: 0, act_inc: 0, plan_exp: 0, act_exp: 0, plan_net: 0, act_net: 0 };
    for (const m of yearMonthly) {
      t.plan_inc += Number(m.plan?.income) || 0;
      t.act_inc += Number(m.actual?.income) || 0;
      t.plan_exp += Number(m.plan?.expenses) || 0;
      t.act_exp += Number(m.actual?.expenses) || 0;
      t.plan_net += Number(m.plan?.net) || 0;
      t.act_net += Number(m.actual?.net) || 0;
    }
    return t;
  }, [yearMonthly]);

  if (!budget) {
    return (
      <div className="cashflow-page pnl-empty">
        <div
          className="kpi-card"
          style={{ maxWidth: 520, margin: '48px auto', textAlign: 'center' }}
        >
          <div className="kpi-label">ბიუჯეტი ჯერ არ არის</div>
          <div className="kpi-sub" style={{ marginTop: 12 }}>
            გაუშვი ტერმინალში:
          </div>
          <code className="pnl-code-hint">python generate_dashboard_data.py</code>
        </div>
      </div>
    );
  }

  // YTD values
  const ytdPlanInc = Number(ytd.plan_ytd?.income) || 0;
  const ytdActInc = Number(ytd.actual_ytd?.income) || 0;
  const ytdVarInc = Number(ytd.variance_ytd?.income) || 0;
  const ytdIncPct = ytdPlanInc > 0 ? (ytdActInc / ytdPlanInc) * 100 : 0;

  const ytdPlanExp = Number(ytd.plan_ytd?.expenses) || 0;
  const ytdActExp = Number(ytd.actual_ytd?.expenses) || 0;
  const ytdVarExp = Number(ytd.variance_ytd?.expenses) || 0;
  const ytdExpPct = ytdPlanExp > 0 ? (ytdActExp / ytdPlanExp) * 100 : 0;

  const ytdPlanNet = Number(ytd.plan_ytd?.net) || 0;
  const ytdActNet = Number(ytd.actual_ytd?.net) || 0;
  const ytdVarNet = Number(ytd.variance_ytd?.net) || 0;
  const ytdNetPct = ytdPlanNet > 0 ? (ytdActNet / ytdPlanNet) * 100 : 0;

  const onTrack = ytd.on_track;
  const monthsElapsed = Number(ytd.months_elapsed) || 0;

  return (
    <div className="cashflow-page">

      {/* Tab Hero */}
      <div className="tab-hero">
        <span className="tab-hero-title">📋 ბიუჯეტი — Plan vs Actual</span>
        <span className="tab-hero-desc">YTD შეფასება · წლიური შედარება · თვიური ანალიზი</span>
        <ExportButton
          filename={`Budget_${selectedYear}_${new Date().toISOString().slice(0, 10)}.xlsx`}
          sheets={[{
            name: `Plan vs Actual ${selectedYear}`,
            rows: yearMonthly.map((m) => ({
              თვე: m.month || '',
              გეგმა_შემოსავალი: Number(m.plan?.income) || 0,
              ფაქტიური_შემოსავალი: Number(m.actual?.income) || 0,
              გეგმა_ხარჯები: Number(m.plan?.expenses) || 0,
              ფაქტიური_ხარჯები: Number(m.actual?.expenses) || 0,
              გეგმა_net: Number(m.plan?.net) || 0,
              ფაქტიური_net: Number(m.actual?.net) || 0,
            })),
          }]}
        />
      </div>

      {/* ---- A. YTD KPI ---- */}
      <div className="budget-ytd-heading">
        <span className="forecast-method-badge">{currentYear} — YTD ({monthsElapsed} თვე)</span>
        {budget.config_source && (
          <span className="budget-config-source">წყარო: {budget.config_source}</span>
        )}
      </div>

      <div className="kpi-grid">
        {/* YTD შემოსავალი */}
        <div className="kpi-card kpi-card--accent">
          <div className="kpi-label">YTD შემოსავალი</div>
          <div className="kpi-value amount-positive">{fmt(ytdActInc)}</div>
          <div className="kpi-sub">
            გეგმა: <span className="amount-neutral">{fmt(ytdPlanInc)}</span>
          </div>
          <Gauge value={ytdIncPct} max={100} color={incomeColor(ytdIncPct)} />
          <div className="kpi-sub" style={{ marginTop: 4 }}>
            {fmtPct(ytdIncPct, false)} შესრ. ·{' '}
            <span className={ytdVarInc >= 0 ? 'amount-positive' : 'amount-negative'}>
              {ytdVarInc >= 0 ? '+' : ''}{fmt(ytdVarInc)}
            </span>
          </div>
        </div>

        {/* YTD ხარჯი */}
        <div className={`kpi-card ${ytdExpPct > 100 ? 'kpi-card--warn' : ''}`}>
          <div className="kpi-label">YTD ხარჯი</div>
          <div className="kpi-value amount-negative">{fmt(ytdActExp)}</div>
          <div className="kpi-sub">
            გეგმა: <span className="amount-neutral">{fmt(ytdPlanExp)}</span>
          </div>
          <Gauge value={ytdExpPct} max={100} color={expenseColor(ytdExpPct)} />
          <div className="kpi-sub" style={{ marginTop: 4 }}>
            {fmtPct(ytdExpPct, false)} შესრ. ·{' '}
            <span className={ytdVarExp <= 0 ? 'amount-positive' : 'amount-negative'}>
              {ytdVarExp >= 0 ? '+' : ''}{fmt(ytdVarExp)}
            </span>
          </div>
        </div>

        {/* YTD Net */}
        <div className="kpi-card">
          <div className="kpi-label">YTD Net</div>
          <div className={`kpi-value ${ytdActNet >= 0 ? 'amount-positive' : 'amount-negative'}`}>
            {fmt(ytdActNet)}
          </div>
          <div className="kpi-sub">
            გეგმა: <span className="amount-neutral">{fmt(ytdPlanNet)}</span>
          </div>
          <Gauge value={ytdNetPct} max={100} color={incomeColor(ytdNetPct)} />
          <div className="kpi-sub" style={{ marginTop: 4 }}>
            {fmtPct(ytdNetPct, false)} შესრ. ·{' '}
            <span className={ytdVarNet >= 0 ? 'amount-positive' : 'amount-negative'}>
              {ytdVarNet >= 0 ? '+' : ''}{fmt(ytdVarNet)}
            </span>
          </div>
        </div>

        {/* On Track */}
        <div className={`kpi-card ${onTrack ? '' : 'kpi-card--warn budget-off-track-pulse'}`}>
          <div className="kpi-label">სტატუსი</div>
          <div className="kpi-value" style={{ fontSize: '2.4rem' }}>
            {onTrack ? '✅' : '⚠️'}
          </div>
          <div className="kpi-sub">
            {onTrack ? 'გეგმის ფარგლებში' : 'გეგმიდან გადახვევა'}
          </div>
          <div className="kpi-sub">
            {monthsElapsed} თვე გასულია · {currentYear}
          </div>
        </div>
      </div>

      {/* ---- B. წლიური შედარება ---- */}
      {allYears.length > 0 && (
        <div className="chart-card chart-card--wide">
          <h3>წლიური Plan vs Actual</h3>
          <div className="table-wrapper cashflow-table pnl-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>წელი</th>
                  <th>გეგმა POS</th>
                  <th>ფაქტი POS</th>
                  <th>სხვ. POS</th>
                  <th>გეგმა ხარჯი</th>
                  <th>ფაქტი ხარჯი</th>
                  <th>სხვ. ხარჯი</th>
                  <th>გეგმა net</th>
                  <th>ფაქტი net</th>
                  <th>სხვ. net</th>
                  <th style={{ minWidth: 110 }}>შესრ. %</th>
                </tr>
              </thead>
              <tbody>
                {allYears.map((yr) => {
                  const a = annual[yr] || {};
                  const isCurrent = yr === currentYear;
                  const varInc = Number(a.variance?.income) || 0;
                  const varExp = Number(a.variance?.expenses) || 0;
                  const varNet = Number(a.variance?.net) || 0;
                  const compPct = Number(a.completion_pct) || 0;
                  return (
                    <tr
                      key={yr}
                      className={isCurrent ? 'budget-current-year-row' : ''}
                    >
                      <td>
                        <strong>{yr}</strong>
                        {isCurrent && (
                          <span className="budget-current-badge">YTD</span>
                        )}
                      </td>
                      <td className="amount-neutral">{fmt(a.plan?.income)}</td>
                      <td className="amount-positive">{fmt(a.actual?.income)}</td>
                      <td className={varInc >= 0 ? 'amount-positive' : 'amount-negative'}>
                        {varInc >= 0 ? '+' : ''}{fmt(varInc)}
                      </td>
                      <td className="amount-neutral">{fmt(a.plan?.expenses)}</td>
                      <td className="amount-negative">{fmt(a.actual?.expenses)}</td>
                      <td className={varExp <= 0 ? 'amount-positive' : 'amount-negative'}>
                        {varExp >= 0 ? '+' : ''}{fmt(varExp)}
                      </td>
                      <td className="amount-neutral">{fmt(a.plan?.net)}</td>
                      <td className={Number(a.actual?.net) >= 0 ? 'amount-positive' : 'amount-negative'}>
                        {fmt(a.actual?.net)}
                      </td>
                      <td className={varNet >= 0 ? 'amount-positive' : 'amount-negative'}>
                        {varNet >= 0 ? '+' : ''}{fmt(varNet)}
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <InlineGauge pct={compPct} color={incomeColor(compPct)} />
                          <span style={{ fontSize: '0.8rem', color: '#94a3b8', minWidth: 36 }}>
                            {compPct.toFixed(1)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---- C. Plan vs Actual ჩარტი ---- */}
      <div className="chart-card chart-card--wide">
        <div className="budget-chart-header">
          <h3>Plan vs Actual — თვიური</h3>
          <label className="budget-year-select-label">
            <span>წელი:</span>
            <select
              className="pnl-month-select"
              value={selectedYear}
              onChange={(e) => setSelectedYear(e.target.value)}
            >
              {allYears.map((yr) => (
                <option key={yr} value={yr}>
                  {yr}
                </option>
              ))}
            </select>
          </label>
        </div>
        <DateRangePicker
          allMonths={yearMonthsList}
          from={budgetFrom}
          to={budgetTo}
          onFromChange={setBudgetFrom}
          onToChange={setBudgetTo}
          label={`${selectedYear} თვეები`}
        />
        {chartData.length > 0 ? (
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 8, right: 20, left: 10, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3040" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#8899aa' }} />
                <YAxis
                  tick={{ fontSize: 11, fill: '#8899aa' }}
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ paddingTop: 8, fontSize: 12 }} />
                <Bar dataKey="plan_income"    name="გეგმა POS"    fill="none" stroke="#7db9f7" strokeWidth={1.5} strokeDasharray="4 2" opacity={0.85} barSize={10} />
                <Bar dataKey="actual_income"  name="ფაქტი POS"   fill="#1a6fd4" opacity={0.85} barSize={10} />
                <Bar dataKey="plan_expenses"  name="გეგმა ხარჯი" fill="none" stroke="#f7a0aa" strokeWidth={1.5} strokeDasharray="4 2" opacity={0.85} barSize={10} />
                <Bar dataKey="actual_expenses" name="ფაქტი ხარჯი" fill="#c02040" opacity={0.85} barSize={10} />
                <Line
                  type="monotone"
                  dataKey="plan_net"
                  name="გეგმა net"
                  stroke="#8899aa"
                  strokeWidth={1.5}
                  strokeDasharray="6 3"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="actual_net"
                  name="ფაქტი net"
                  stroke="#34c97e"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#34c97e' }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="kpi-sub" style={{ padding: '1rem', textAlign: 'center' }}>
            {selectedYear} წლის თვიური მონაცემები არ არის
          </div>
        )}
      </div>

      {/* ---- D. თვიური ცხრილი ---- */}
      {yearMonthly.length > 0 && (
        <div className="chart-card chart-card--wide">
          <h3>თვიური Plan vs Actual — {selectedYear}</h3>
          <div className="table-wrapper cashflow-table pnl-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>თვე</th>
                  <th>გეგმა POS</th>
                  <th>ფაქტი POS</th>
                  <th>სხვ. %</th>
                  <th>გეგმა ხარჯი</th>
                  <th>ფაქტი ხარჯი</th>
                  <th>სხვ. %</th>
                  <th>გეგმა net</th>
                  <th>ფაქტი net</th>
                  <th>სხვ. %</th>
                  <th>სტატუსი</th>
                </tr>
              </thead>
              <tbody>
                {yearMonthly.map((m) => {
                  const vpInc = Number(m.variance_pct?.income) || 0;
                  const vpExp = Number(m.variance_pct?.expenses) || 0;
                  const vpNet = Number(m.variance_pct?.net) || 0;
                  const actNet = Number(m.actual?.net) || 0;
                  return (
                    <tr key={m.month}>
                      <td>{monthLabel(m.month)}</td>
                      <td className="amount-neutral">{fmt(m.plan?.income)}</td>
                      <td className="amount-positive">{fmt(m.actual?.income)}</td>
                      <td className={vpInc >= 0 ? 'amount-positive' : 'amount-negative'}>
                        {fmtPct(vpInc)}
                      </td>
                      <td className="amount-neutral">{fmt(m.plan?.expenses)}</td>
                      <td className="amount-negative">{fmt(m.actual?.expenses)}</td>
                      <td className={vpExp <= 0 ? 'amount-positive' : 'amount-negative'}>
                        {fmtPct(vpExp)}
                      </td>
                      <td className="amount-neutral">{fmt(m.plan?.net)}</td>
                      <td className={actNet >= 0 ? 'amount-positive' : 'amount-negative'}>
                        {fmt(actNet)}
                      </td>
                      <td className={vpNet >= 0 ? 'amount-positive' : 'amount-negative'}>
                        {fmtPct(vpNet)}
                      </td>
                      <td>
                        <span className={`badge ${m.on_track ? 'budget-on-track' : 'budget-off-track'}`}>
                          {m.on_track ? '✅ OK' : '⚠️ გადახ.'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr className="pnl-tfoot-total">
                  <td><strong>სულ {selectedYear}</strong></td>
                  <td className="amount-neutral"><strong>{fmt(yearTotals.plan_inc)}</strong></td>
                  <td className="amount-positive"><strong>{fmt(yearTotals.act_inc)}</strong></td>
                  <td className={yearTotals.act_inc >= yearTotals.plan_inc ? 'amount-positive' : 'amount-negative'}>
                    <strong>
                      {yearTotals.plan_inc > 0
                        ? fmtPct(((yearTotals.act_inc - yearTotals.plan_inc) / yearTotals.plan_inc) * 100)
                        : '—'}
                    </strong>
                  </td>
                  <td className="amount-neutral"><strong>{fmt(yearTotals.plan_exp)}</strong></td>
                  <td className="amount-negative"><strong>{fmt(yearTotals.act_exp)}</strong></td>
                  <td className={yearTotals.act_exp <= yearTotals.plan_exp ? 'amount-positive' : 'amount-negative'}>
                    <strong>
                      {yearTotals.plan_exp > 0
                        ? fmtPct(((yearTotals.act_exp - yearTotals.plan_exp) / yearTotals.plan_exp) * 100)
                        : '—'}
                    </strong>
                  </td>
                  <td className="amount-neutral"><strong>{fmt(yearTotals.plan_net)}</strong></td>
                  <td className={yearTotals.act_net >= 0 ? 'amount-positive' : 'amount-negative'}>
                    <strong>{fmt(yearTotals.act_net)}</strong>
                  </td>
                  <td className={yearTotals.act_net >= yearTotals.plan_net ? 'amount-positive' : 'amount-negative'}>
                    <strong>
                      {yearTotals.plan_net > 0
                        ? fmtPct(((yearTotals.act_net - yearTotals.plan_net) / yearTotals.plan_net) * 100)
                        : '—'}
                    </strong>
                  </td>
                  <td>—</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
