import React, { useMemo, useState, useCallback } from 'react';
import DateRangePicker from './components/DateRangePicker.jsx';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
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

const OBJECT_COLORS = {
  'ოზურგეთი': '#4f8ef7',
  'დვაბზუ': '#34c97e',
  'გაუნაწილებელი': '#8899aa',
  'საერთო': '#f7a434',
};

const INCOME_OBJECTS = ['ოზურგეთი', 'დვაბზუ', 'გაუნაწილებელი'];
const ALL_OBJECTS = ['ოზურგეთი', 'დვაბზუ', 'საერთო', 'გაუნაწილებელი'];

async function loadXlsxModule() {
  const xlsxModule = await import('xlsx');
  return xlsxModule.default || xlsxModule;
}

function monthLabel(m) {
  if (!m || m === 'უცნობი თვე') return m || '—';
  const [y, mo] = m.split('-');
  if (!y || !mo) return m;
  return `${mo}/${String(y).slice(2)}`;
}

function yearOf(m) {
  return m ? m.split('-')[0] : null;
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

function Sparkline({ netData, color }) {
  if (!netData || netData.length < 2) return null;
  return (
    <div style={{ marginTop: 8, height: 52 }}>
      <ResponsiveContainer width="100%" height={52}>
        <LineChart data={netData} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function sumRows(rows) {
  let pos = 0;
  let cash = 0;
  let totalInc = 0;
  let expenses = 0;
  const byObj = {};
  for (const m of rows) {
    const tPos = Number(m.total?.pos_income) || 0;
    const tCash = Number(m.total?.cash_income) || 0;
    const tTot = Number(m.total?.total_income ?? m.total?.pos_income) || 0;
    pos += tPos;
    cash += tCash;
    totalInc += tTot;
    expenses += Number(m.total?.expenses) || 0;
    for (const [obj, vals] of Object.entries(m.objects || {})) {
      if (!byObj[obj]) {
        byObj[obj] = { pos_income: 0, cash_income: 0, total_income: 0, expenses: 0 };
      }
      byObj[obj].pos_income += Number(vals.pos_income) || 0;
      byObj[obj].cash_income += Number(vals.cash_income) || 0;
      byObj[obj].total_income += Number(vals.total_income ?? vals.pos_income) || 0;
      byObj[obj].expenses += Number(vals.expenses) || 0;
    }
  }
  return {
    income: pos,
    cashIncome: cash,
    totalIncome: totalInc,
    expenses,
    net: totalInc - expenses,
    byObj,
  };
}

export default function PnL({ monthlyPnl }) {
  const allRows = useMemo(
    () => (Array.isArray(monthlyPnl) ? monthlyPnl : []),
    [monthlyPnl],
  );

  const allMonths = useMemo(
    () =>
      [...new Set(allRows.map((r) => r.month).filter(Boolean))].sort(),
    [allRows],
  );

  const [pnlFrom, setPnlFrom] = useState('');
  const [pnlTo, setPnlTo] = useState('');

  const effectiveFrom = pnlFrom || allMonths[0] || '';
  const effectiveTo = pnlTo || allMonths[allMonths.length - 1] || '';

  const rows = useMemo(() => {
    if (!effectiveFrom && !effectiveTo) return allRows;
    return allRows.filter((m) => {
      const mo = m.month || '';
      return mo >= effectiveFrom && mo <= effectiveTo;
    });
  }, [allRows, effectiveFrom, effectiveTo]);

  const objectSet = useMemo(() => {
    const seen = new Set();
    for (const m of allRows) {
      for (const k of Object.keys(m.objects || {})) seen.add(k);
    }
    return ALL_OBJECTS.filter((o) => seen.has(o));
  }, [allRows]);

  const totals = useMemo(() => sumRows(rows), [rows]);

  const chartData = useMemo(() => {
    return rows.map((m) => {
      const entry = { month: monthLabel(m.month), _raw: m.month };
      for (const obj of ALL_OBJECTS) {
        const vals = m.objects?.[obj] || {};
        entry[`${obj}_income`] =
          Number(vals.total_income ?? vals.pos_income) || 0;
        entry[`${obj}_exp`] = Number(vals.expenses) || 0;
      }
      entry['სულ_net'] = Number(m.total?.net) || 0;
      entry['სულ_income'] =
        Number(m.total?.total_income ?? m.total?.pos_income) || 0;
      entry['სულ_expenses'] = Number(m.total?.expenses) || 0;
      return entry;
    });
  }, [rows]);

  const sparklinesByObj = useMemo(() => {
    const result = {};
    for (const obj of INCOME_OBJECTS) {
      result[obj] = rows.map((m) => {
        const v = m.objects?.[obj] || {};
        const inc = Number(v.total_income ?? v.pos_income) || 0;
        const exp = Number(v.expenses) || 0;
        return { v: inc - exp };
      });
    }
    return result;
  }, [rows]);

  // ცხრილის rows — ჩვეულებრივი + წლიური subtotal-ები
  const tableRows = useMemo(() => {
    const result = [];
    let currentYear = null;
    let yearAcc = [];

    const pushYearSubtotal = (year, acc) => {
      if (!acc.length) return;
      const s = sumRows(acc);
      result.push({ _type: 'year', year, ...s, _rows: acc });
    };

    for (const m of rows) {
      const y = yearOf(m.month);
      if (y !== currentYear) {
        if (currentYear !== null) {
          pushYearSubtotal(currentYear, yearAcc);
        }
        currentYear = y;
        yearAcc = [];
      }
      result.push({ _type: 'month', ...m });
      yearAcc.push(m);
    }
    if (currentYear !== null) {
      pushYearSubtotal(currentYear, yearAcc);
    }
    return result;
  }, [rows]);

  // Excel ჩამოტვირთვა
  const handleExport = useCallback(async () => {
    const nonCommon = objectSet.filter((o) => o !== 'საერთო');
    const hasCommon = objectSet.includes('საერთო');
    const headers = ['თვე'];
    for (const obj of nonCommon) {
      headers.push(
        `${obj} POS`,
        `${obj} ნაღდი`,
        `${obj} ხარჯი`,
        `${obj} net`,
      );
    }
    if (hasCommon) headers.push('საერთო ხარჯი');
    headers.push('სულ POS', 'სულ ნაღდი', 'სულ შემოსავალი', 'სულ ხარჯი', 'სულ net');

    const sheetData = [headers];
    for (const m of rows) {
      const row = [monthLabel(m.month)];
      for (const obj of nonCommon) {
        const v = m.objects?.[obj] || {};
        const pos = Number(v.pos_income) || 0;
        const cash = Number(v.cash_income) || 0;
        const exp = Number(v.expenses) || 0;
        row.push(pos, cash, exp, pos + cash - exp);
      }
      if (hasCommon) {
        row.push(Number(m.objects?.['საერთო']?.expenses) || 0);
      }
      const tPos = Number(m.total?.pos_income) || 0;
      const tCash = Number(m.total?.cash_income) || 0;
      const tTot = Number(m.total?.total_income ?? m.total?.pos_income) || 0;
      row.push(
        tPos,
        tCash,
        tTot,
        Number(m.total?.expenses) || 0,
        Number(m.total?.net) || 0,
      );
      sheetData.push(row);
    }
    // ჯამის ხაზი
    const totRow = ['სულ'];
    for (const obj of nonCommon) {
      const t = totals.byObj[obj] || {};
      const pos = Number(t.pos_income) || 0;
      const cash = Number(t.cash_income) || 0;
      const exp = Number(t.expenses) || 0;
      totRow.push(pos, cash, exp, pos + cash - exp);
    }
    if (hasCommon) {
      totRow.push(Number((totals.byObj['საერთო'] || {}).expenses) || 0);
    }
    totRow.push(
      totals.income,
      totals.cashIncome,
      totals.totalIncome,
      totals.expenses,
      totals.net,
    );
    sheetData.push(totRow);

    const XLSX = await loadXlsxModule();
    const ws = XLSX.utils.aoa_to_sheet(sheetData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'P&L');
    const fromStr = effectiveFrom.replace('-', '');
    const toStr = effectiveTo.replace('-', '');
    XLSX.writeFile(wb, `P&L_${fromStr}_${toStr}.xlsx`);
  }, [rows, objectSet, totals, effectiveFrom, effectiveTo]);

  if (!allRows.length) {
    return (
      <div className="cashflow-page pnl-empty">
        <div
          className="kpi-card"
          style={{ maxWidth: 480, margin: '48px auto', textAlign: 'center' }}
        >
          <div className="kpi-label">P&L მონაცემები ჯერ არ არის</div>
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
        <span className="tab-hero-title">📈 P&L — თვიური მოგება-ზარალი</span>
        <span className="tab-hero-desc">ობიექტების მიხედვით: ოზურგეთი, დვაბზუ, საერთო</span>
      </div>

      {/* ---- პერიოდის ფილტრი ---- */}
      <DateRangePicker
        allMonths={allMonths}
        from={pnlFrom}
        to={pnlTo}
        onFromChange={setPnlFrom}
        onToChange={setPnlTo}
        label="P&L პერიოდი"
      >
        <button type="button" className="btn-download-xlsx pnl-export-btn" onClick={handleExport}>
          Excel ჩამოტვირთვა
        </button>
      </DateRangePicker>

      {/* ---- KPI ზედა ბარათები ---- */}
      <div className="kpi-grid">
        <div className="kpi-card kpi-card--accent">
          <div className="kpi-label">სულ შემოსავალი</div>
          <div className="kpi-value amount-positive">{fmt(totals.totalIncome)}</div>
          <div className="kpi-sub">
            POS: {fmt(totals.income)} · ნაღდი: {fmt(totals.cashIncome)}
          </div>
          <div className="kpi-sub">{rows.length} თვე</div>
        </div>
        <div className="kpi-card kpi-card--warn">
          <div className="kpi-label">სულ ხარჯი</div>
          <div className="kpi-value amount-negative">{fmt(totals.expenses)}</div>
          <div className="kpi-sub">TBC + BOG კატეგორიები</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">სუფთა მოგება (net)</div>
          <div
            className={`kpi-value ${totals.net >= 0 ? 'amount-positive' : 'amount-negative'}`}
          >
            {fmt(totals.net)}
          </div>
          <div className="kpi-sub">შემოსავალი − ხარჯი</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">ობიექტები / თვეები</div>
          <div className="kpi-value amount-neutral">
            {objectSet.length} / {rows.length}
          </div>
          <div className="kpi-sub">{objectSet.join(' · ')}</div>
        </div>
      </div>

      {/* ---- ობიექტების KPI sparkline-ებით ---- */}
      <div className="kpi-grid pnl-obj-grid">
        {INCOME_OBJECTS.filter((o) => objectSet.includes(o)).map((obj) => {
          const t = totals.byObj[obj] || {};
          const pos = Number(t.pos_income) || 0;
          const cash = Number(t.cash_income) || 0;
          const totalInc = Number(t.total_income) || pos;
          const exp = Number(t.expenses) || 0;
          const net = totalInc - exp;
          const sparkData = sparklinesByObj[obj] || [];
          const sparkColor = net >= 0 ? '#34c97e' : '#e05c6e';
          return (
            <div
              className="kpi-card"
              key={obj}
              style={{ borderTop: `2px solid ${OBJECT_COLORS[obj] || '#555'}` }}
            >
              <div className="kpi-label">{obj}</div>
              <div className="kpi-value amount-positive">{fmt(totalInc)}</div>
              <div className="kpi-sub">
                POS: {fmt(pos)} · ნაღდი: {fmt(cash)}
              </div>
              <div className="kpi-sub">
                ხარჯი: <span className="amount-negative">{fmt(exp)}</span>
              </div>
              <div className="kpi-sub">
                net:{' '}
                <span className={net >= 0 ? 'amount-positive' : 'amount-negative'}>
                  {fmt(net)}
                </span>
              </div>
              <Sparkline netData={sparkData} color={sparkColor} />
            </div>
          );
        })}
        {objectSet.includes('საერთო') && (
          <div
            className="kpi-card"
            style={{ borderTop: `3px solid ${OBJECT_COLORS['საერთო']}` }}
          >
            <div className="kpi-label">საერთო (კომპანიის დონის ხარჯი)</div>
            <div className="kpi-value amount-negative">
              {fmt((totals.byObj['საერთო'] || {}).expenses)}
            </div>
            <div className="kpi-sub">სესხი · ლიცენზია · საბანკო საკომისიო</div>
          </div>
        )}
      </div>

      {/* ---- ჩარტი 1: Stacked Bar — შემოსავალი ობიექტებით ---- */}
      <div className="chart-card chart-card--wide">
        <h3>თვიური შემოსავალი — ობიექტების მიხედვით</h3>
        <div className="chart-area">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 20, left: 10, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3040" />
              <XAxis
                dataKey="month"
                tick={{ fontSize: 11, fill: '#8899aa' }}
                angle={-45}
                textAnchor="end"
                interval={chartInterval}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#8899aa' }}
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ paddingTop: 8, fontSize: 13 }} />
              {INCOME_OBJECTS.filter((o) => objectSet.includes(o)).map((obj) => (
                <Bar
                  key={obj}
                  dataKey={`${obj}_income`}
                  name={obj}
                  stackId="income"
                  fill={OBJECT_COLORS[obj]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ---- ჩარტი 2: Composed — ხარჯი + net line ---- */}
      <div className="chart-card chart-card--wide">
        <h3>სულ შემოსავალი, ხარჯი და net (თვეები)</h3>
        <div className="chart-area">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 8, right: 20, left: 10, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3040" />
              <XAxis
                dataKey="month"
                tick={{ fontSize: 11, fill: '#8899aa' }}
                angle={-45}
                textAnchor="end"
                interval={chartInterval}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#8899aa' }}
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ paddingTop: 8, fontSize: 13 }} />
              <Bar dataKey="სულ_income" name="სულ შემოსავალი" fill="#4f8ef7" opacity={0.6} />
              <Bar dataKey="სულ_expenses" name="სულ ხარჯი" fill="#e05c6e" opacity={0.6} />
              <Line
                type="monotone"
                dataKey="სულ_net"
                name="net (სულ)"
                stroke="#34c97e"
                strokeWidth={2}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ---- თვიური ცხრილი წლიური subtotal-ებით ---- */}
      <div className="table-wrapper cashflow-table pnl-table-scroll">
        <table>
          <thead>
            <tr>
              <th>თვე</th>
              {objectSet.filter((o) => o !== 'საერთო').map((obj) => (
                <React.Fragment key={obj}>
                  <th style={{ color: OBJECT_COLORS[obj] }}>
                    {obj} POS
                  </th>
                  <th style={{ color: OBJECT_COLORS[obj] }}>
                    {obj} ნაღდი
                  </th>
                  <th>{obj} ხარჯი</th>
                  <th>{obj} net</th>
                </React.Fragment>
              ))}
              {objectSet.includes('საერთო') && <th>საერთო ხარჯი</th>}
              <th>სულ POS</th>
              <th>სულ ნაღდი</th>
              <th>სულ შემოსავალი</th>
              <th>სულ ხარჯი</th>
              <th>სულ net</th>
            </tr>
          </thead>
          <tbody>
            {tableRows.map((row, idx) => {
              if (row._type === 'year') {
                const ynet = row.net;
                const nonCommon = objectSet.filter((o) => o !== 'საერთო');
                return (
                  <tr key={`year-${row.year}-${idx}`} className="pnl-year-subtotal">
                    <td><strong>{row.year} ჯამი</strong></td>
                    {nonCommon.map((obj) => {
                      const t = row.byObj[obj] || {};
                      const pos = Number(t.pos_income) || 0;
                      const cash = Number(t.cash_income) || 0;
                      const exp = Number(t.expenses) || 0;
                      const net = pos + cash - exp;
                      return (
                        <React.Fragment key={obj}>
                          <td className="amount-positive">
                            <strong>{pos ? fmt(pos) : '—'}</strong>
                          </td>
                          <td className="amount-positive">
                            <strong>{cash ? fmt(cash) : '—'}</strong>
                          </td>
                          <td className="amount-negative">
                            <strong>{exp ? fmt(exp) : '—'}</strong>
                          </td>
                          <td
                            className={net >= 0 ? 'amount-positive' : 'amount-negative'}
                          >
                            <strong>{fmt(net)}</strong>
                          </td>
                        </React.Fragment>
                      );
                    })}
                    {objectSet.includes('საერთო') && (
                      <td className="amount-negative">
                        <strong>{fmt((row.byObj['საერთო'] || {}).expenses)}</strong>
                      </td>
                    )}
                    <td className="amount-positive"><strong>{fmt(row.income)}</strong></td>
                    <td className="amount-positive"><strong>{fmt(row.cashIncome)}</strong></td>
                    <td className="amount-positive"><strong>{fmt(row.totalIncome)}</strong></td>
                    <td className="amount-negative"><strong>{fmt(row.expenses)}</strong></td>
                    <td className={ynet >= 0 ? 'amount-positive' : 'amount-negative'}>
                      <strong>{fmt(ynet)}</strong>
                    </td>
                  </tr>
                );
              }

              // ჩვეულებრივი თვის ხაზი
              const m = row;
              const totalNet = Number(m.total?.net) || 0;
              const monthTotalInc = Number(
                m.total?.total_income ?? m.total?.pos_income,
              ) || 0;
              return (
                <tr key={m.month}>
                  <td>{monthLabel(m.month)}</td>
                  {objectSet.filter((o) => o !== 'საერთო').map((obj) => {
                    const v = m.objects?.[obj] || {};
                    const pos = Number(v.pos_income) || 0;
                    const cash = Number(v.cash_income) || 0;
                    const exp = Number(v.expenses) || 0;
                    const net = Number(v.net ?? pos + cash - exp);
                    return (
                      <React.Fragment key={obj}>
                        <td className="amount-positive">
                          {pos ? fmt(pos) : '—'}
                        </td>
                        <td className="amount-positive">
                          {cash ? fmt(cash) : '—'}
                        </td>
                        <td className="amount-negative">
                          {exp ? fmt(exp) : '—'}
                        </td>
                        <td
                          className={net >= 0 ? 'amount-positive' : 'amount-negative'}
                        >
                          {fmt(net)}
                        </td>
                      </React.Fragment>
                    );
                  })}
                  {objectSet.includes('საერთო') && (
                    <td className="amount-negative">
                      {Number(m.objects?.['საერთო']?.expenses)
                        ? fmt(m.objects['საერთო'].expenses)
                        : '—'}
                    </td>
                  )}
                  <td className="amount-positive">{fmt(m.total?.pos_income)}</td>
                  <td className="amount-positive">{fmt(m.total?.cash_income)}</td>
                  <td className="amount-positive">{fmt(monthTotalInc)}</td>
                  <td className="amount-negative">{fmt(m.total?.expenses)}</td>
                  <td className={totalNet >= 0 ? 'amount-positive' : 'amount-negative'}>
                    {fmt(totalNet)}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="pnl-tfoot-total">
              <td><strong>სულ ({rows.length} თვე)</strong></td>
              {objectSet.filter((o) => o !== 'საერთო').map((obj) => {
                const t = totals.byObj[obj] || {};
                const pos = Number(t.pos_income) || 0;
                const cash = Number(t.cash_income) || 0;
                const exp = Number(t.expenses) || 0;
                const net = pos + cash - exp;
                return (
                  <React.Fragment key={obj}>
                    <td className="amount-positive">
                      <strong>{fmt(pos)}</strong>
                    </td>
                    <td className="amount-positive">
                      <strong>{fmt(cash)}</strong>
                    </td>
                    <td className="amount-negative">
                      <strong>{fmt(exp)}</strong>
                    </td>
                    <td
                      className={net >= 0 ? 'amount-positive' : 'amount-negative'}
                    >
                      <strong>{fmt(net)}</strong>
                    </td>
                  </React.Fragment>
                );
              })}
              {objectSet.includes('საერთო') && (
                <td className="amount-negative">
                  <strong>{fmt((totals.byObj['საერთო'] || {}).expenses)}</strong>
                </td>
              )}
              <td className="amount-positive"><strong>{fmt(totals.income)}</strong></td>
              <td className="amount-positive"><strong>{fmt(totals.cashIncome)}</strong></td>
              <td className="amount-positive"><strong>{fmt(totals.totalIncome)}</strong></td>
              <td className="amount-negative"><strong>{fmt(totals.expenses)}</strong></td>
              <td className={totals.net >= 0 ? 'amount-positive' : 'amount-negative'}>
                <strong>{fmt(totals.net)}</strong>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
