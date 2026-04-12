import { useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  ScatterChart,
  Scatter,
  ZAxis,
} from 'recharts';
import { mergeSupplier, shortLabel } from './financeMerge.js';

const PALETTE = ['#60a5fa', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#94a3b8', '#38bdf8'];

function fmt(v) {
  return new Intl.NumberFormat('ka-GE', {
    style: 'currency',
    currency: 'GEL',
    maximumFractionDigits: 0,
  }).format(v);
}

function fmtFull(v) {
  return new Intl.NumberFormat('ka-GE', {
    style: 'currency',
    currency: 'GEL',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(v);
}

export default function Analytics({ suppliers, localPayments }) {
  const [includeBrowser, setIncludeBrowser] = useState(true);

  const rows = useMemo(() => {
    const local = includeBrowser ? localPayments : {};
    return (suppliers || []).map((s) => {
      const m = mergeSupplier(s, local);
      return {
        ...m,
        label: shortLabel(m.org, 34),
      };
    });
  }, [suppliers, includeBrowser, localPayments]);

  const totals = useMemo(() => {
    let eff = 0;
    let paid = 0;
    let debt = 0;
    let browser = 0;
    for (const r of rows) {
      eff += r.effective;
      paid += r.paid;
      debt += r.debt;
      browser += r.browserExtra || 0;
    }
    return {
      eff,
      paid,
      debt,
      browser,
      n: rows.length,
    };
  }, [rows]);

  const topDebt = useMemo(() => {
    return [...rows]
      .filter((r) => r.debt > 0)
      .sort((a, b) => b.debt - a.debt)
      .slice(0, 20)
      .map((r) => ({
        name: r.label,
        debt: Math.round(r.debt * 100) / 100,
      }));
  }, [rows]);

  const topEffective = useMemo(() => {
    return [...rows]
      .sort((a, b) => b.effective - a.effective)
      .slice(0, 20)
      .map((r) => ({
        name: r.label,
        effective: Math.round(r.effective * 100) / 100,
      }));
  }, [rows]);

  const pieDebtShare = useMemo(() => {
    const sorted = [...rows].filter((r) => r.debt > 0).sort((a, b) => b.debt - a.debt);
    const top = sorted.slice(0, 5);
    const restSum = sorted.slice(5).reduce((s, r) => s + r.debt, 0);
    const out = top.map((r) => ({
      name: shortLabel(r.org, 18),
      value: Math.round(r.debt * 100) / 100,
    }));
    if (restSum > 1) {
      out.push({ name: 'დანარჩენი', value: Math.round(restSum * 100) / 100 });
    }
    return out.filter((x) => x.value > 0);
  }, [rows]);

  const paymentMix = useMemo(() => {
    let cash = 0;
    for (const r of rows) {
      cash += r.manualTotal ?? (r.manual + (r.browserExtra || 0));
    }
    const other = Math.max(0, totals.paid - cash);
    return [
      { name: 'ნაღდით გადახდა', value: Math.round(cash * 100) / 100 },
      { name: 'სხვა (ბანკი/ბარათი)', value: Math.round(other * 100) / 100 },
    ].filter((x) => x.value > 0.01);
  }, [rows, totals.paid]);

  const scatterPay = useMemo(() => {
    return [...rows]
      .filter((r) => r.effective > 0 || r.paid > 0)
      .map((r) => ({
        x: Math.round(r.effective * 100) / 100,
        y: Math.round(r.paid * 100) / 100,
        z: 120,
        name: r.label,
      }))
      .sort((a, b) => b.x - a.x)
      .slice(0, 80);
  }, [rows]);

  const tooltipStyle = {
    background: 'rgba(12, 18, 34, 0.97)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10,
    color: '#f1f5f9',
    fontSize: 12,
    boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
  };

  return (
    <div className="analytics-page">
      <div className="tab-hero">
        <span className="tab-hero-title">📊 ანალიტიკა</span>
        <span className="tab-hero-desc">მომწოდებლების ვიზუალური ანალიზი — ვალი, გადახდა, წილი</span>
      </div>
      <div className="analytics-toolbar">
        <label className="analytics-toggle">
          <input
            type="checkbox"
            checked={includeBrowser}
            onChange={(e) => setIncludeBrowser(e.target.checked)}
          />
          <span>ბრაუზერში ჩაწერილი გადახდების ჩართვა (იგივე, რაც მთავარ ცხრილში)</span>
        </label>
        <p className="analytics-note">
          ციფრები: <strong>რეალური ჯამი − სულ გადახდილი = დავალიანება</strong> თითო მომწოდებელზე; ჯამები
          მოდის <code>data.json</code>-იდან + ლოკალური დამატება თუ ჩართულია.
        </p>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card" style={{ borderBottom: '3px solid #3b82f6' }}>
          <div className="kpi-label">რეალური ჯამი (RS)</div>
          <div className="kpi-value">{fmtFull(totals.eff)}</div>
          <div className="kpi-sub">{totals.n} მომწოდებელი</div>
        </div>
        <div className="kpi-card kpi-card--accent" style={{ borderBottom: '3px solid #22c55e' }}>
          <div className="kpi-label">სულ გადახდილი</div>
          <div className="kpi-value">{fmtFull(totals.paid)}</div>
          {includeBrowser && totals.browser > 0 ? (
            <div className="kpi-sub">მათგან ბრაუზერში +{fmtFull(totals.browser)}</div>
          ) : (
            <div className="kpi-sub">&nbsp;</div>
          )}
        </div>
        <div className="kpi-card kpi-card--warn" style={{ borderBottom: '3px solid #ef4444' }}>
          <div className="kpi-label">დავალიანება</div>
          <div className="kpi-value">{fmtFull(totals.debt)}</div>
          <div className="kpi-sub">
            {totals.eff > 0 ? `${((totals.debt / totals.eff) * 100).toFixed(1)}% ჯამისა` : '—'}
          </div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <div className="chart-card-header">
            <h3>TOP დავალიანებით</h3>
            <span className="chart-card-header-desc">ყველაზე მაღალი დარჩენილი ვალი (₾)</span>
          </div>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height={420}>
              <BarChart
                data={topDebt}
                layout="vertical"
                margin={{ top: 8, right: 24, left: 8, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                <XAxis
                  type="number"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  tickFormatter={(v) => fmt(v)}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={200}
                  tick={{ fill: '#cbd5e1', fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value) => [fmtFull(value), 'დავალიანება']}
                />
                <Bar dataKey="debt" name="დავალიანება" fill="#f87171" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="chart-card-header">
            <h3>TOP რეალური ბრუნვით</h3>
            <span className="chart-card-header-desc">ეფექტური ჯამი ზედნადებიდან (₾)</span>
          </div>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height={420}>
              <BarChart
                data={topEffective}
                layout="vertical"
                margin={{ top: 8, right: 24, left: 8, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                <XAxis
                  type="number"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  tickFormatter={(v) => fmt(v)}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={200}
                  tick={{ fill: '#cbd5e1', fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value) => [fmtFull(value), 'რეალური']}
                />
                <Bar dataKey="effective" name="რეალური" fill="#34d399" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card chart-card--pie">
          <div className="chart-card-header">
            <h3>დავალიანების სტრუქტურა</h3>
            <span className="chart-card-header-desc">TOP-5 + დანარჩენი</span>
          </div>
          <div className="chart-area chart-area--pie">
            <ResponsiveContainer width="100%" height={320}>
              <PieChart>
                <Pie
                  data={pieDebtShare}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={110}
                  label={({ name, percent }) =>
                    `${name} ${(percent * 100).toFixed(0)}%`
                  }
                >
                  {pieDebtShare.map((_, i) => (
                    <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value) => fmtFull(value)}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card chart-card--pie">
          <h3>გადახდების შემადგენლობა</h3>
          <p className="chart-desc">ნაღდით გადახდა (CSV + ბრაუზერი) / დანარჩენი</p>
          <div className="chart-area chart-area--pie">
            <ResponsiveContainer width="100%" height={320}>
              <PieChart>
                <Pie
                  data={paymentMix}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={110}
                  label={({ name, percent }) =>
                    `${name} ${(percent * 100).toFixed(0)}%`
                  }
                >
                  {paymentMix.map((_, i) => (
                    <Cell key={i} fill={PALETTE[(i + 2) % PALETTE.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value) => fmtFull(value)}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card chart-card--wide">
          <div className="chart-card-header">
            <h3>რეალური vs გადახდილი (scatter)</h3>
            <span className="chart-card-header-desc">X = რეალური ჯამი, Y = სულ გადახდილი (max 80)</span>
          </div>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height={380}>
              <ScatterChart margin={{ top: 16, right: 24, bottom: 48, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                <XAxis
                  type="number"
                  dataKey="x"
                  name="რეალური"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  tickFormatter={(v) => fmt(v)}
                  label={{ value: 'რეალური ჯამი (₾)', position: 'bottom', fill: '#94a3b8', offset: 24 }}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  name="გადახდილი"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  tickFormatter={(v) => fmt(v)}
                  label={{
                    value: 'სულ გადახდილი (₾)',
                    angle: -90,
                    position: 'insideLeft',
                    fill: '#94a3b8',
                  }}
                />
                <ZAxis type="number" dataKey="z" range={[40, 40]} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(v, name) => [fmtFull(v), name === 'y' ? 'გადახდილი' : 'რეალური']}
                  labelFormatter={(_, p) => (p && p[0] && p[0].payload ? p[0].payload.name : '')}
                />
                <Scatter name="მომწოდებლები" data={scatterPay} fill="#60a5fa" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
