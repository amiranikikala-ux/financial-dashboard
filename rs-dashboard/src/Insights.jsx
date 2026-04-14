import { useState, useEffect, useMemo } from 'react';
import { fetchApiJson } from './lib/api.js';

const GEL = new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL', maximumFractionDigits: 0 });
const fmt = (v) => GEL.format(Number(v) || 0);
const fmtPct = (v, sign = true) => {
  const n = Number(v) || 0;
  return `${sign && n > 0 ? '+' : ''}${n.toFixed(1)}%`;
};
const toNum = (v) => Number(v) || 0;

function monthLabel(m) {
  if (!m) return '—';
  const [y, mo] = m.split('-');
  if (!y || !mo) return m;
  const MONTHS_KA = ['იან', 'თებ', 'მარ', 'აპრ', 'მაი', 'ივნ', 'ივლ', 'აგვ', 'სექ', 'ოქტ', 'ნოე', 'დეკ'];
  const idx = Number(mo) - 1;
  return `${MONTHS_KA[idx] || mo} ${y}`;
}

function riskColor(score) {
  if (score >= 80) return '#22c55e';
  if (score >= 60) return '#a3e07a';
  if (score >= 40) return '#eab308';
  if (score >= 20) return '#f7a434';
  return '#ef4444';
}

function riskLabel(score) {
  if (score >= 80) return 'დაბალი რისკი';
  if (score >= 60) return 'ზომიერი';
  if (score >= 40) return 'საშუალო';
  if (score >= 20) return 'მაღალი';
  return 'კრიტიკული';
}

function RiskGauge({ score, label }) {
  const color = riskColor(score);
  const pct = Math.min(100, Math.max(0, score));
  return (
    <div className="insights-risk-gauge">
      <div className="insights-risk-gauge-label">{label}</div>
      <div className="insights-risk-gauge-bar">
        <div className="insights-risk-gauge-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="insights-risk-gauge-value" style={{ color }}>{Math.round(score)}/100</div>
    </div>
  );
}

function AlertCard({ type, title, description, value }) {
  const icons = { danger: '🔴', warning: '🟡', info: '🔵', success: '🟢' };
  const bgMap = { danger: 'rgba(239,68,68,0.08)', warning: 'rgba(234,179,8,0.08)', info: 'rgba(59,130,246,0.08)', success: 'rgba(34,197,94,0.08)' };
  return (
    <div className="insights-alert" style={{ background: bgMap[type] || bgMap.info }}>
      <span className="insights-alert-icon">{icons[type] || '📌'}</span>
      <div className="insights-alert-body">
        <div className="insights-alert-title">{title}</div>
        <div className="insights-alert-desc">{description}</div>
        {value != null && <div className="insights-alert-value">{value}</div>}
      </div>
    </div>
  );
}

export default function Insights({ reloadKey }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [monthlyPnl, setMonthlyPnl] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [ratios, setRatios] = useState(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const opts = { signal: controller.signal };
    setTimeout(() => {
      if (!active) return;
      setLoading(true);
      setError(null);
    }, 0);
    Promise.all([
      fetchApiJson('/api/data?tab=pnl_summary', opts),
      fetchApiJson('/api/data?tab=forecast', opts),
      fetchApiJson('/api/data?tab=ratios', opts),
    ])
      .then(([pnlJson, forecastJson, ratiosJson]) => {
        if (!active) return;
        setMonthlyPnl(Array.isArray(pnlJson.monthly_pnl) ? pnlJson.monthly_pnl : []);
        setForecast(forecastJson.forecast || null);
        setRatios(ratiosJson.financial_ratios || null);
        setLoading(false);
      })
      .catch((err) => {
        if (!active || err.name === 'AbortError') return;
        console.error('Insights data load failed:', err);
        setError(err.message);
        setLoading(false);
      });

    return () => { active = false; controller.abort(); };
  }, [reloadKey]);

  // ---- COMPUTED DATA ----

  const sorted = useMemo(
    () => [...monthlyPnl].sort((a, b) => (a.month || '').localeCompare(b.month || '')),
    [monthlyPnl],
  );

  const last6 = useMemo(() => sorted.slice(-6), [sorted]);
  const last12 = useMemo(() => sorted.slice(-12), [sorted]);

  // ---- 1. CASH BURN RATE ----
  const burnAnalysis = useMemo(() => {
    if (last6.length === 0) return null;
    const n = last6.length;
    let totalIncome = 0;
    let totalExpenses = 0;
    for (const m of last6) {
      totalIncome += toNum(m.total?.pos_income);
      totalExpenses += toNum(m.total?.expenses);
    }
    const avgIncome = totalIncome / n;
    const avgExpenses = totalExpenses / n;
    const netMonthly = avgIncome - avgExpenses;
    const isBurning = netMonthly < 0;
    // approximate cumulative cash from all-time net
    let totalCash = 0;
    for (const m of sorted) {
      totalCash += toNum(m.total?.pos_income) - toNum(m.total?.expenses);
    }
    const runwayMonths = isBurning ? Math.max(0, Math.floor(totalCash / Math.abs(netMonthly))) : null;
    return { avgIncome, avgExpenses, netMonthly, isBurning, runwayMonths, totalCash, months: n };
  }, [last6, sorted]);

  // ---- 2. BREAK-EVEN ANALYSIS ----
  const breakEven = useMemo(() => {
    if (last12.length === 0) return null;
    let profitableCount = 0;
    let firstProfitable = null;
    let longestStreak = 0;
    let currentStreak = 0;
    const monthly = [];

    for (const m of last12) {
      const income = toNum(m.total?.pos_income);
      const expenses = toNum(m.total?.expenses);
      const net = income - expenses;
      const profitable = net > 0;
      if (profitable) {
        profitableCount++;
        currentStreak++;
        longestStreak = Math.max(longestStreak, currentStreak);
        if (!firstProfitable) firstProfitable = m.month;
      } else {
        currentStreak = 0;
      }
      monthly.push({ month: m.month, income, expenses, net, profitable });
    }

    const profitablePct = (profitableCount / last12.length) * 100;
    // break-even point: average monthly expenses = how much revenue needed
    const avgExp = monthly.reduce((a, r) => a + r.expenses, 0) / monthly.length;

    return { profitableCount, total: last12.length, profitablePct, firstProfitable, longestStreak, breakEvenRevenue: avgExp, monthly };
  }, [last12]);

  // ---- 3. RISK SCORE ----
  const riskScores = useMemo(() => {
    if (last6.length < 2) return null;

    // Margin risk (higher margin = lower risk)
    const totalInc = last6.reduce((a, m) => a + toNum(m.total?.pos_income), 0);
    const totalExp = last6.reduce((a, m) => a + toNum(m.total?.expenses), 0);
    const marginPct = totalInc > 0 ? ((totalInc - totalExp) / totalInc) * 100 : 0;
    const marginScore = Math.min(100, Math.max(0, marginPct * 2)); // 50% margin = 100 score

    // Volatility risk (standard deviation of monthly net / avg)
    const nets = last6.map((m) => toNum(m.total?.pos_income) - toNum(m.total?.expenses));
    const avgNet = nets.reduce((a, v) => a + v, 0) / nets.length;
    const variance = nets.reduce((a, v) => a + Math.pow(v - avgNet, 2), 0) / nets.length;
    const stdDev = Math.sqrt(variance);
    const cv = avgNet !== 0 ? Math.abs(stdDev / avgNet) : 2;
    const stabilityScore = Math.min(100, Math.max(0, (1 - cv) * 100));

    // Growth trend (last 3 vs prev 3)
    const prev3 = last6.slice(0, 3);
    const curr3 = last6.slice(-3);
    const prev3Avg = prev3.reduce((a, m) => a + toNum(m.total?.pos_income), 0) / 3;
    const curr3Avg = curr3.reduce((a, m) => a + toNum(m.total?.pos_income), 0) / 3;
    const growthPct = prev3Avg > 0 ? ((curr3Avg - prev3Avg) / prev3Avg) * 100 : 0;
    const growthScore = Math.min(100, Math.max(0, 50 + growthPct));

    // Expense control (expense growth < income growth is good)
    const prev3Exp = prev3.reduce((a, m) => a + toNum(m.total?.expenses), 0) / 3;
    const curr3Exp = curr3.reduce((a, m) => a + toNum(m.total?.expenses), 0) / 3;
    const expGrowthPct = prev3Exp > 0 ? ((curr3Exp - prev3Exp) / prev3Exp) * 100 : 0;
    const expenseControl = growthPct >= expGrowthPct ? 80 : Math.max(0, 80 - (expGrowthPct - growthPct) * 2);

    // AP days from ratios
    const apDays = toNum(ratios?.company?.ap_days);
    const apScore = apDays <= 30 ? 100 : apDays <= 60 ? 80 : apDays <= 90 ? 50 : apDays <= 120 ? 25 : 10;

    const composite = Math.round(
      marginScore * 0.25 + stabilityScore * 0.2 + growthScore * 0.2 + expenseControl * 0.2 + apScore * 0.15,
    );

    return {
      margin: { score: Math.round(marginScore), value: marginPct },
      stability: { score: Math.round(stabilityScore), value: cv },
      growth: { score: Math.round(growthScore), value: growthPct },
      expenseControl: { score: Math.round(expenseControl), value: expGrowthPct },
      ap: { score: Math.round(apScore), value: apDays },
      composite,
    };
  }, [last6, ratios]);

  // ---- 4. TREND ALERTS ----
  const alerts = useMemo(() => {
    const result = [];
    if (sorted.length < 2) return result;

    const lastM = sorted[sorted.length - 1];
    const prevM = sorted[sorted.length - 2];
    const lastInc = toNum(lastM.total?.pos_income);
    const prevInc = toNum(prevM.total?.pos_income);
    const lastExp = toNum(lastM.total?.expenses);
    const prevExp = toNum(prevM.total?.expenses);
    const lastNet = lastInc - lastExp;

    // Income change
    if (prevInc > 0) {
      const incChg = ((lastInc - prevInc) / prevInc) * 100;
      if (incChg <= -20) {
        result.push({
          type: 'danger',
          title: `შემოსავლის ვარდნა ${fmtPct(incChg)}`,
          description: `${monthLabel(lastM.month)}: ${fmt(lastInc)} vs ${monthLabel(prevM.month)}: ${fmt(prevInc)}`,
        });
      } else if (incChg >= 20) {
        result.push({
          type: 'success',
          title: `შემოსავლის ზრდა ${fmtPct(incChg)}`,
          description: `${monthLabel(lastM.month)}: ${fmt(lastInc)} vs ${monthLabel(prevM.month)}: ${fmt(prevInc)}`,
        });
      }
    }

    // Expense spike
    if (prevExp > 0) {
      const expChg = ((lastExp - prevExp) / prevExp) * 100;
      if (expChg >= 25) {
        result.push({
          type: 'warning',
          title: `ხარჯის ზრდა ${fmtPct(expChg)}`,
          description: `${monthLabel(lastM.month)}: ${fmt(lastExp)} vs ${monthLabel(prevM.month)}: ${fmt(prevExp)}`,
        });
      }
    }

    // Net loss alert
    if (lastNet < 0) {
      result.push({
        type: 'danger',
        title: 'ბოლო თვე წამგებიანია',
        description: `${monthLabel(lastM.month)} — net: ${fmt(lastNet)}`,
      });
    }

    // Consecutive declining net
    if (sorted.length >= 3) {
      let declining = 0;
      for (let i = sorted.length - 1; i >= 1; i--) {
        const curr = toNum(sorted[i].total?.pos_income) - toNum(sorted[i].total?.expenses);
        const prev = toNum(sorted[i - 1].total?.pos_income) - toNum(sorted[i - 1].total?.expenses);
        if (curr < prev) declining++;
        else break;
      }
      if (declining >= 3) {
        result.push({
          type: 'warning',
          title: `${declining} თანმიმდევრული კლება`,
          description: 'Net მოგება ზედიზედ მცირდება',
        });
      }
    }

    // All-time high/low check in last month
    if (sorted.length >= 6) {
      const allNets = sorted.map((m) => toNum(m.total?.pos_income) - toNum(m.total?.expenses));
      const max = Math.max(...allNets);
      const min = Math.min(...allNets);
      if (lastNet === max && lastNet > 0) {
        result.push({ type: 'success', title: 'ისტორიული მაქსიმუმი!', description: `net: ${fmt(lastNet)} — ${monthLabel(lastM.month)}` });
      }
      if (lastNet === min) {
        result.push({ type: 'danger', title: 'ისტორიული მინიმუმი', description: `net: ${fmt(lastNet)} — ${monthLabel(lastM.month)}` });
      }
    }

    // Forecast warning
    if (forecast?.forecast?.months) {
      const fMonths = forecast.forecast.months;
      const negativeForecasts = fMonths.filter((m) => toNum(m.total?.net) < 0);
      if (negativeForecasts.length > 0) {
        result.push({
          type: 'warning',
          title: `პროგნოზი: ${negativeForecasts.length}/${fMonths.length} თვე წამგებიანია`,
          description: negativeForecasts.map((m) => `${monthLabel(m.month)}: ${fmt(m.total?.net)}`).join(' · '),
        });
      }
    }

    // Margin too low
    if (burnAnalysis && !burnAnalysis.isBurning) {
      const margin = burnAnalysis.avgIncome > 0 ? ((burnAnalysis.avgIncome - burnAnalysis.avgExpenses) / burnAnalysis.avgIncome) * 100 : 0;
      if (margin < 10 && margin > 0) {
        result.push({
          type: 'warning',
          title: `დაბალი მარჟა: ${margin.toFixed(1)}%`,
          description: 'საშ. მოგების მარჟა 10%-ზე დაბალია',
        });
      }
    }

    if (result.length === 0) {
      result.push({ type: 'info', title: 'მნიშვნელოვანი სიგნალები არ არის', description: 'ყველა ინდიკატორი ნორმალურ ფარგლებშია' });
    }

    return result;
  }, [sorted, forecast, burnAnalysis]);

  // ---- RENDER ----
  if (loading) {
    return <div className="loading">ინსაითები იტვირთება...</div>;
  }

  if (error) {
    return (
      <div className="local-pay-banner" style={{ background: '#ef4444', color: '#fff' }} role="alert">
        <strong>შეცდომა:</strong> {error}
      </div>
    );
  }

  if (!sorted.length) {
    return (
      <div className="cashflow-page pnl-empty">
        <div className="kpi-card" style={{ maxWidth: 520, margin: '48px auto', textAlign: 'center' }}>
          <div className="kpi-label">მონაცემები ჯერ არ არის</div>
          <div className="kpi-sub" style={{ marginTop: 12 }}>გაუშვი ტერმინალში:</div>
          <code className="pnl-code-hint">python generate_dashboard_data.py</code>
        </div>
      </div>
    );
  }

  return (
    <div className="cashflow-page">

      {/* Tab Hero */}
      <div className="tab-hero">
        <span className="tab-hero-title">🧠 ინსაითები — პროფესიონალური ანალიზი</span>
        <span className="tab-hero-desc">Cash Burn · Break-Even · Risk Score · Trend Alerts</span>
      </div>

      {/* ---- TREND ALERTS ---- */}
      <div className="insights-section">
        <h3 className="insights-section-title">⚡ Trend Alerts</h3>
        <div className="insights-alerts-grid">
          {alerts.map((a, i) => (
            <AlertCard key={i} type={a.type} title={a.title} description={a.description} value={a.value} />
          ))}
        </div>
      </div>

      {/* ---- CASH BURN RATE ---- */}
      {burnAnalysis && (
        <div className="insights-section">
          <h3 className="insights-section-title">🔥 Cash Burn Rate</h3>
          <div className="kpi-grid">
            <div className="kpi-card kpi-card--accent">
              <div className="kpi-label">საშ. თვიური შემოსავალი</div>
              <div className="kpi-value amount-positive">{fmt(burnAnalysis.avgIncome)}</div>
              <div className="kpi-sub">ბოლო {burnAnalysis.months} თვე</div>
            </div>
            <div className="kpi-card kpi-card--warn">
              <div className="kpi-label">საშ. თვიური ხარჯი</div>
              <div className="kpi-value amount-negative">{fmt(burnAnalysis.avgExpenses)}</div>
              <div className="kpi-sub">ბოლო {burnAnalysis.months} თვე</div>
            </div>
            <div className={`kpi-card ${burnAnalysis.isBurning ? 'kpi-card--warn' : ''}`}>
              <div className="kpi-label">საშ. თვიური net</div>
              <div className={`kpi-value ${burnAnalysis.netMonthly >= 0 ? 'amount-positive' : 'amount-negative'}`}>
                {fmt(burnAnalysis.netMonthly)}
              </div>
              <div className="kpi-sub">
                {burnAnalysis.isBurning ? '❌ cash burn' : '✅ მოგებიანი'}
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">
                {burnAnalysis.isBurning ? '⏳ Runway' : '💰 კუმულატიური net'}
              </div>
              <div className={`kpi-value ${burnAnalysis.totalCash >= 0 ? 'amount-positive' : 'amount-negative'}`}>
                {burnAnalysis.isBurning
                  ? `${burnAnalysis.runwayMonths} თვე`
                  : fmt(burnAnalysis.totalCash)}
              </div>
              <div className="kpi-sub">
                {burnAnalysis.isBurning
                  ? 'მოსალოდნელი ამოწურვის ვადა'
                  : 'სულ აკუმულირებული net'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ---- BREAK-EVEN ---- */}
      {breakEven && (
        <div className="insights-section">
          <h3 className="insights-section-title">📊 Break-Even ანალიზი</h3>
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">მომგებიანი თვეები</div>
              <div className={`kpi-value ${breakEven.profitablePct >= 50 ? 'amount-positive' : 'amount-negative'}`}>
                {breakEven.profitableCount} / {breakEven.total}
              </div>
              <div className="kpi-sub">{breakEven.profitablePct.toFixed(0)}% მოგებიანი</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">უგრძესი მოგებიანი სტრიქი</div>
              <div className="kpi-value amount-positive">{breakEven.longestStreak} თვე</div>
              <div className="kpi-sub">ზედიზედ მომგებიანი თვეები</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Break-Even ზღვარი</div>
              <div className="kpi-value amount-neutral">{fmt(breakEven.breakEvenRevenue)}</div>
              <div className="kpi-sub">საშ. თვიური ხარჯი = მინ. შემოსავალი</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">პირველი მოგებიანი</div>
              <div className="kpi-value amount-positive">
                {breakEven.firstProfitable ? monthLabel(breakEven.firstProfitable) : '—'}
              </div>
              <div className="kpi-sub">ბოლო 12 თვიდან</div>
            </div>
          </div>

          {/* Mini monthly bar */}
          <div className="insights-breakeven-months">
            {breakEven.monthly.map((m) => (
              <div
                key={m.month}
                className={`insights-be-month ${m.profitable ? 'insights-be-profit' : 'insights-be-loss'}`}
                title={`${monthLabel(m.month)}: ${fmt(m.net)}`}
              >
                <span className="insights-be-month-label">{(m.month || '').slice(5)}</span>
                <span className="insights-be-month-icon">{m.profitable ? '✅' : '❌'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---- RISK SCORE DASHBOARD ---- */}
      {riskScores && (
        <div className="insights-section">
          <h3 className="insights-section-title">🛡️ Risk Score Dashboard</h3>

          <div className="insights-risk-composite">
            <div className="insights-risk-big-score" style={{ color: riskColor(riskScores.composite) }}>
              {riskScores.composite}
            </div>
            <div className="insights-risk-big-label">
              {riskLabel(riskScores.composite)}
            </div>
            <div className="insights-risk-big-sub">კომპოზიტური ჯანმრთელობის ქულა</div>
          </div>

          <div className="insights-risk-gauges">
            <RiskGauge
              score={riskScores.margin.score}
              label={`მარჟა (${riskScores.margin.value.toFixed(1)}%)`}
            />
            <RiskGauge
              score={riskScores.stability.score}
              label={`სტაბილურობა (CV: ${riskScores.stability.value.toFixed(2)})`}
            />
            <RiskGauge
              score={riskScores.growth.score}
              label={`ზრდა (${fmtPct(riskScores.growth.value)})`}
            />
            <RiskGauge
              score={riskScores.expenseControl.score}
              label={`ხარჯ. კონტრ. (${fmtPct(riskScores.expenseControl.value)})`}
            />
            <RiskGauge
              score={riskScores.ap.score}
              label={`AP Days (${Math.round(riskScores.ap.value)} დღე)`}
            />
          </div>
        </div>
      )}
    </div>
  );
}
