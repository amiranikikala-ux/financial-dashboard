import { useState } from 'react';

const GEL = new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL', maximumFractionDigits: 0 });
const fmt = (v) => GEL.format(Number(v) || 0);
const fmtPct = (v, sign = false) => {
  const n = Number(v) || 0;
  return `${sign && n > 0 ? '+' : ''}${n.toFixed(1)}%`;
};
const asArray = (v) => (Array.isArray(v) ? v : []);
const toNum = (v) => Number(v) || 0;

function toSheetRows(rows) {
  if (rows.length > 0) return rows;
  return [{ message: 'მონაცემი ვერ მოიძებნა' }];
}

const OBJECT_COLORS = { 'ოზურგეთი': '#4f8ef7', 'დვაბზუ': '#34c97e' };

async function loadXlsxModule() {
  const xlsxModule = await import('xlsx');
  return xlsxModule.default || xlsxModule;
}

function buildCanonicalPeriodParams(fromDate, toDate, fromTime, toTime) {
  const resolvedFromDate = fromDate || toDate;
  const resolvedToDate = toDate || fromDate;
  if (!resolvedFromDate && !resolvedToDate) return null;
  return {
    from_date: resolvedFromDate,
    to_date: resolvedToDate,
    from_time: fromTime || '00:00',
    to_time: toTime || '23:59',
  };
}

function criteriaColor(score) {
  const s = Number(score) || 0;
  if (s >= 80) return '#22c55e';
  if (s >= 60) return '#a3e07a';
  if (s >= 40) return '#f7a434';
  return '#ef4444';
}

function apDaysColor(d) {
  if (d < 45) return '#22c55e';
  if (d <= 90) return '#eab308';
  return '#ef4444';
}

function gradeColor(grade) {
  const map = { A: '#22c55e', B: '#a3e07a', C: '#eab308', D: '#f7a434', F: '#ef4444' };
  return map[String(grade).toUpperCase()] || '#8899aa';
}

function priorityColor(p) {
  const map = { 1: '#ef4444', 2: '#f7a434', 3: '#eab308', 4: '#3b82f6', 5: '#8899aa' };
  return map[Number(p)] || '#8899aa';
}

// ---- Audit Timeline Step ----
function AuditStep({ item, isLast }) {
  const [open, setOpen] = useState(false);
  const score = Math.min(100, Math.max(0, Number(item.score) || 0));
  const color = criteriaColor(score);
  return (
    <div className="exec-audit-step">
      <div className="exec-audit-step-content">
        <button
          type="button"
          className="exec-audit-step-circle"
          style={{ background: `${color}22`, border: `2px solid ${color}`, color }}
          onClick={() => item.note_ka && setOpen((v) => !v)}
          title={item.note_ka || ''}
          aria-expanded={open}
        >
          {score}
        </button>
        {!isLast && <div className="exec-audit-step-line" style={{ background: `linear-gradient(90deg, ${color}, #2d3748)` }} />}
      </div>
      <div className="exec-audit-step-label">{item.label_ka}</div>
      {open && item.note_ka && (
        <div className="exec-audit-step-note">{item.note_ka}</div>
      )}
    </div>
  );
}

// ---- KPI Card with icon + bottom border color ----
function ExecKpiCard({ icon, label, value, sub, bottomColor, bgTint, className = '' }) {
  return (
    <div
      className={`exec-kpi-card ${className}`}
      style={{
        borderBottom: `3px solid ${bottomColor || 'transparent'}`,
        background: bgTint ? `rgba(${bgTint},0.06)` : undefined,
      }}
    >
      <div className="exec-kpi-card-inner">
        <div className="exec-kpi-icon">{icon}</div>
        <div className="exec-kpi-body">
          <div className="kpi-label">{label}</div>
          <div className="kpi-value" style={{ color: bottomColor, fontSize: '1.4rem' }}>{value}</div>
          {sub && <div className="kpi-sub">{sub}</div>}
        </div>
      </div>
    </div>
  );
}

export default function Executive({ executiveSummary, fromDate, fromTime, toDate, toTime }) {
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);
  const canonicalPeriodParams = buildCanonicalPeriodParams(fromDate, toDate, fromTime, toTime);

  const es = executiveSummary;

  if (!es) {
    return (
      <div className="cashflow-page pnl-empty">
        <div className="kpi-card" style={{ maxWidth: 520, margin: '48px auto', textAlign: 'center' }}>
          <div className="kpi-label">Executive Summary ჯერ არ არის</div>
          <div className="kpi-sub" style={{ marginTop: 12 }}>გაუშვი ტერმინალში:</div>
          <code className="pnl-code-hint">python generate_dashboard_data.py</code>
        </div>
      </div>
    );
  }

  const audit = es.audit_readiness || {};
  const exec = es.executive || {};
  const kpis = exec.kpis || {};

  const criteria = Array.isArray(audit.criteria) ? audit.criteria : [];
  const auditScore = Number(audit.overall_score) || 0;
  const grade = String(audit.grade || '—');
  const gradeCol = gradeColor(grade);
  const keyDecisions = Array.isArray(exec.key_decisions) ? exec.key_decisions : [];
  const nextSteps = Array.isArray(exec.next_steps) ? exec.next_steps : [];
  const objects = Array.isArray(exec.objects) ? exec.objects : [];

  const apDays = Number(kpis.ap_days) || 0;
  const yoy = Number(kpis.yoy_growth_pct) || 0;
  const netMargin = Number(kpis.net_margin_pct ?? kpis.gross_margin_pct) || 0;
  const isHeadlineCritical = String(exec.headline_ka || '').toLowerCase().includes('კრიტიკულ');
  const gmColor = netMargin >= 50 ? '#22c55e' : netMargin >= 30 ? '#eab308' : '#ef4444';
  const yoyCol = yoy >= 0 ? '#22c55e' : '#ef4444';

  const handlePrintPdf = () => {
    document.body.classList.add('print-executive-mode');
    window.print();
    setTimeout(() => document.body.classList.remove('print-executive-mode'), 500);
  };

  const handleDownloadFullExcel = async () => {
    setExporting(true);
    setExportError(null);
    try {
      const params = new URLSearchParams({ tab: 'executive_export' });
      if (canonicalPeriodParams) {
        Object.entries(canonicalPeriodParams).forEach(([key, value]) => {
          params.set(key, value);
        });
      }
      const res = await fetch(`/api/data?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const exportData = await res.json();

      const XLSX = await loadXlsxModule();
      const wb = XLSX.utils.book_new();
      const monthlyPnl = asArray(exportData?.monthly_pnl);
      const budgetMonthly = asArray(exportData?.budget?.monthly);
      const ratios = exportData?.financial_ratios || {};
      const supplierAging = asArray(exportData?.supplier_aging);
      const apTrend = asArray(exportData?.ap_monthly_trend);
      const forecastMonths = asArray(exportData?.forecast?.forecast?.months);
      const seasonalityRows = asArray(exportData?.forecast?.seasonality?.by_calendar_month);
      const sectorComparison = asArray(exportData?.company_valuation?.sector_comparison);
      const valuationMethods = asArray(exportData?.company_valuation?.valuation?.methods);
      const valuationRange = exportData?.company_valuation?.valuation?.range || {};
      const swot = exportData?.company_valuation?.swot || {};
      const monthRange = monthlyPnl.map((m) => m?.month).filter(Boolean).sort();
      const periodFromMonths = monthRange.length ? `${monthRange[0]} — ${monthRange[monthRange.length - 1]}` : '';
      const swotLine = (items) => asArray(items).map((item) => item?.text_ka).filter(Boolean).join(' | ') || '—';

      const execRows = [
        ['ველი', 'მნიშვნელობა'],
        ['კომპანია', exec.company_name || 'FOODTIME LLC'],
        ['პერიოდი', periodFromMonths || exec.period || '—'],
        ['Audit Grade', `${audit.grade || '—'} (${Math.round(toNum(audit.overall_score))}/100)`],
        ['Headline', exec.headline_ka || '—'],
        ['წლიური შემოსავალი', toNum(kpis.annual_revenue)],
        ['წლიური Net', toNum(kpis.annual_net)],
        ['Net Margin', `${toNum(kpis.net_margin_pct ?? kpis.gross_margin_pct).toFixed(1)}%`],
        ['AP Days', toNum(kpis.ap_days)],
        ['YoY Growth', `${toNum(kpis.yoy_growth_pct) >= 0 ? '+' : ''}${toNum(kpis.yoy_growth_pct).toFixed(1)}%`],
        ['ვალუაცია (median)', toNum(kpis.valuation_median)],
        ['ძლიერი სეზონი', kpis.strongest_month || '—'],
        ['სუსტი სეზონი', kpis.weakest_month || '—'],
        [],
        ['ტიპი', 'ტექსტი'],
        ['Strength', swotLine(swot.strengths)],
        ['Weakness', swotLine(swot.weaknesses)],
        ['Opportunity', swotLine(swot.opportunities)],
        ['Threat', swotLine(swot.threats)],
      ];
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(execRows), 'Executive Summary');

      const pnlObjects = [...new Set(monthlyPnl.flatMap((m) => Object.keys(m?.objects || {})))];
      const pnlRows = monthlyPnl.map((m) => {
        const row = { თვე: m.month || '—' };
        for (const obj of pnlObjects) {
          const vals = m.objects?.[obj] || {};
          const pos = toNum(vals.pos_income);
          const cash = toNum(vals.cash_income);
          const expenses = toNum(vals.expenses);
          row[`${obj} POS`] = pos;
          row[`${obj} ნაღდი`] = cash;
          row[`${obj} ხარჯი`] = expenses;
          row[`${obj} net`] = toNum(vals.net ?? pos + cash - expenses);
        }
        row['სულ POS'] = toNum(m.total?.pos_income);
        row['სულ ნაღდი'] = toNum(m.total?.cash_income);
        row['სულ შემოსავალი'] = toNum(m.total?.total_income ?? m.total?.pos_income);
        row['სულ ხარჯი'] = toNum(m.total?.expenses);
        row['სულ net'] = toNum(m.total?.net);
        return row;
      });
      if (pnlRows.length > 0) {
        const totalRow = { თვე: 'ჯამი' };
        for (const obj of pnlObjects) {
          totalRow[`${obj} POS`] = pnlRows.reduce((acc, r) => acc + toNum(r[`${obj} POS`]), 0);
          totalRow[`${obj} ნაღდი`] = pnlRows.reduce((acc, r) => acc + toNum(r[`${obj} ნაღდი`]), 0);
          totalRow[`${obj} ხარჯი`] = pnlRows.reduce((acc, r) => acc + toNum(r[`${obj} ხარჯი`]), 0);
          totalRow[`${obj} net`] = pnlRows.reduce((acc, r) => acc + toNum(r[`${obj} net`]), 0);
        }
        totalRow['სულ POS'] = pnlRows.reduce((acc, r) => acc + toNum(r['სულ POS']), 0);
        totalRow['სულ ნაღდი'] = pnlRows.reduce((acc, r) => acc + toNum(r['სულ ნაღდი']), 0);
        totalRow['სულ შემოსავალი'] = pnlRows.reduce((acc, r) => acc + toNum(r['სულ შემოსავალი']), 0);
        totalRow['სულ ხარჯი'] = pnlRows.reduce((acc, r) => acc + toNum(r['სულ ხარჯი']), 0);
        totalRow['სულ net'] = pnlRows.reduce((acc, r) => acc + toNum(r['სულ net']), 0);
        pnlRows.push(totalRow);
      }
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(toSheetRows(pnlRows)), 'P&L თვიური');

      const budgetRows = budgetMonthly.map((m) => ({
        month: m.month || '—',
        plan_income: toNum(m.plan?.income), plan_expenses: toNum(m.plan?.expenses), plan_net: toNum(m.plan?.net),
        actual_income: toNum(m.actual?.income), actual_expenses: toNum(m.actual?.expenses), actual_net: toNum(m.actual?.net),
        variance_income: toNum(m.variance?.income), variance_expenses: toNum(m.variance?.expenses), variance_net: toNum(m.variance?.net),
        variance_pct_income: toNum(m.variance_pct?.income), variance_pct_expenses: toNum(m.variance_pct?.expenses), variance_pct_net: toNum(m.variance_pct?.net),
        on_track: m.on_track ? 'true' : 'false',
      }));
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(toSheetRows(budgetRows)), 'ბიუჯეტი Plan vs Actual');

      const ratioRows = [['company', 'ველი', 'მნიშვნელობა']];
      for (const [field, value] of Object.entries(ratios.company || {})) ratioRows.push(['company', field, value]);
      ratioRows.push([], ['objects', 'ობიექტი', 'ველი', 'მნიშვნელობა']);
      for (const [obj, fields] of Object.entries(ratios.objects || {}))
        for (const [field, value] of Object.entries(fields || {})) ratioRows.push(['objects', obj, field, value]);
      ratioRows.push([], ['monthly_trend', 'თვე', 'net_margin_pct', 'income_amount', 'expenses_amount', 'net_amount']);
      for (const row of asArray(ratios.monthly_trend))
        ratioRows.push(['monthly_trend', row.month || '—', toNum(row.net_margin_pct ?? row.gross_margin_pct), toNum(row.income_amount), toNum(row.expenses_amount), toNum(row.net_amount)]);
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(ratioRows), 'კოეფიციენტები');

      const supplierRows = supplierAging.map((row) => ({
        org: row.org || '—', total_effective: toNum(row.total_effective), total_paid: toNum(row.total_paid),
        total_debt: toNum(row.total_debt), last_waybill_date: row.last_waybill_date || '',
        days_since_last: toNum(row.days_since_last), aging_bucket: row.aging_bucket || '', object: row.object || '',
      }));
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(toSheetRows(supplierRows)), 'მომწოდებლები (aging)');

      const apRows = apTrend.map((row) => ({
        month: row.month || '—', rs_purchases: toNum(row.rs_purchases), estimated_payments: toNum(row.estimated_payments),
        monthly_debt_change: toNum(row.monthly_debt_change), cumulative_debt: toNum(row.cumulative_debt),
      }));
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(toSheetRows(apRows)), 'AP Trend');

      const forecastObjects = [...new Set(forecastMonths.flatMap((m) => Object.keys(m?.objects || {})))];
      const forecastRows = forecastMonths.map((m) => {
        const row = { month: m.month || '—', total_pos_income: toNum(m.total?.pos_income), total_expenses: toNum(m.total?.expenses), total_net: toNum(m.total?.net) };
        for (const obj of forecastObjects) {
          const vals = m.objects?.[obj] || {};
          row[`${obj}_pos_income`] = toNum(vals.pos_income); row[`${obj}_expenses`] = toNum(vals.expenses); row[`${obj}_net`] = toNum(vals.net);
        }
        return row;
      });
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(toSheetRows(forecastRows)), 'პროგნოზი');

      const seasonalitySheetRows = seasonalityRows.map((row) => ({
        calendar_month: row.calendar_month, label: row.label || '', avg_income: toNum(row.avg_income),
        avg_expenses: toNum(row.avg_expenses), avg_net: toNum(row.avg_net), seasonality_index: toNum(row.seasonality_index),
      }));
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(toSheetRows(seasonalitySheetRows)), 'სეზონურობა');

      const sectorRows = sectorComparison.map((row) => ({
        metric: row.metric || '', label_ka: row.label_ka || '', your_value: toNum(row.your_value),
        sector_low: toNum(row.sector_low), sector_median: toNum(row.sector_median), sector_high: toNum(row.sector_high),
        score: toNum(row.score), assessment_ka: row.assessment_ka || '',
      }));
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(toSheetRows(sectorRows)), 'სექტორის შედარება');

      const valuationRows = [
        ['method', 'low', 'median', 'high'],
        ...valuationMethods.map((row) => [row.method || '', toNum(row.low), toNum(row.median), toNum(row.high)]),
        [], ['range', 'low', 'median', 'high'],
        ['valuation_range', toNum(valuationRange.low), toNum(valuationRange.median), toNum(valuationRange.high)],
      ];
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(valuationRows), 'ვალუაცია');

      const today = new Date();
      const stamp = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
      XLSX.writeFile(wb, `Executive_Report_${stamp}.xlsx`);
    } catch (err) {
      console.error('Export failed:', err);
      setExportError('ექსპორტი ვერ მოხერხდა: ' + err.message);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="cashflow-page executive-page exec-print-root">

      {/* Print-only header */}
      <div className="exec-print-only-header">
        <h2>{exec.company_name} — Executive Summary</h2>
        <p>{exec.period}</p>
        <p>გენერირებულია: {new Date().toLocaleDateString('ka-GE')}</p>
      </div>

      {/* ---- A. HERO HEADER ---- */}
      <div className="exec-hero">
        <div className="exec-hero-left">
          <div className="exec-company-name">{exec.company_name || 'კომპანია'}</div>
          <div className="exec-period">{exec.period}</div>
          <p className="exec-headline" style={{ borderLeftColor: isHeadlineCritical ? '#ef4444' : '#22c55e' }}>
            {exec.headline_ka}
          </p>
          <div className="exec-hero-actions">
            {objects.map((obj) => (
              <span key={obj} className="badge" style={{
                background: `${OBJECT_COLORS[obj] || '#8899aa'}22`,
                color: OBJECT_COLORS[obj] || '#8899aa',
                border: `1px solid ${OBJECT_COLORS[obj] || '#8899aa'}55`,
              }}>
                {obj}
              </span>
            ))}
            <button type="button" className="btn-download-xlsx exec-pdf-btn" onClick={handlePrintPdf}>
              📄 PDF
            </button>
            <button type="button" className="btn-download-xlsx" onClick={handleDownloadFullExcel} disabled={exporting}>
              {exporting ? 'იტვირთება...' : '📊 Excel'}
            </button>
          </div>
          {exportError && <div style={{ color: '#ef4444', marginTop: 8, fontSize: '0.9rem' }}>{exportError}</div>}
        </div>
        <div className="exec-hero-grade">
          <div
            className="exec-grade-circle"
            style={{
              background: `conic-gradient(${gradeCol} 0% ${auditScore}%, rgba(255,255,255,0.06) ${auditScore}% 100%)`,
            }}
          >
            <div className="exec-grade-circle-inner">
              <span className="exec-grade-letter" style={{ color: gradeCol }}>{grade}</span>
              <span className="exec-grade-score">{Math.round(auditScore)}/100</span>
            </div>
          </div>
          <div className="exec-grade-label">Audit Score</div>
        </div>
      </div>

      {/* ---- B. KPI DASHBOARD GRID ---- */}
      <div className="exec-kpi-grid">
        <ExecKpiCard
          icon="💰" label="წლიური შემოსავალი"
          value={fmt(kpis.annual_revenue)}
          sub={`YoY ${yoy >= 0 ? '▲' : '▼'} ${fmtPct(yoy, true)}`}
          bottomColor="#22c55e"
        />
        <ExecKpiCard
          icon="📈" label="წლიური Net"
          value={fmt(kpis.annual_net)}
          sub="შემოსავალი − ხარჯი"
          bottomColor={toNum(kpis.annual_net) >= 0 ? '#22c55e' : '#ef4444'}
        />
        <ExecKpiCard
          icon="📊" label="Net Margin"
          value={fmtPct(netMargin)}
          sub={
            <span>
              <span className="ratio-gauge" style={{ display: 'inline-block', width: '80%', verticalAlign: 'middle', marginRight: 6 }}>
                <span className="ratio-gauge-fill" style={{ width: `${Math.min(100, netMargin)}%`, background: gmColor, display: 'block', height: '100%', borderRadius: 4 }} />
              </span>
            </span>
          }
          bottomColor={gmColor}
        />
        <ExecKpiCard
          icon="📉" label="YoY ზრდა"
          value={`${yoy >= 0 ? '▲' : '▼'} ${fmtPct(yoy, true)}`}
          sub="წინა წელთან"
          bottomColor={yoyCol}
        />
        <ExecKpiCard
          icon="⏱" label="AP Days"
          value={`${apDays} დღე`}
          sub={apDays < 45 ? '✓ კარგი' : apDays <= 90 ? '⚠ ყურადღება' : '⛔ კრიტიკული'}
          bottomColor={apDaysColor(apDays)}
          bgTint={apDays > 90 ? '239,68,68' : undefined}
        />
        <ExecKpiCard
          icon="🏢" label="მომწ. ვალით"
          value={String(Number(kpis.total_suppliers_with_debt) || 0)}
          sub={<>სულ ვალი: <span className="amount-negative">{fmt(kpis.total_debt)}</span></>}
          bottomColor="#ef4444"
        />
        <ExecKpiCard
          icon="🏆" label="ვალუაცია (Median)"
          value={fmt(kpis.valuation_median)}
          sub={`სექტ. ${Number(kpis.sector_score || 0).toFixed(1)}/5`}
          bottomColor="#a855f7"
        />
        <ExecKpiCard
          icon={kpis.budget_on_track ? '✅' : '⚠️'} label="ბიუჯეტი"
          value={kpis.budget_on_track ? 'On Track' : 'Off Track'}
          sub={kpis.budget_on_track ? 'გეგმის ფარგლებში' : 'გეგმიდან გადახვევა'}
          bottomColor={kpis.budget_on_track ? '#22c55e' : '#eab308'}
          bgTint={kpis.budget_on_track ? undefined : '234,179,8'}
        />
      </div>

      {/* ---- C. AUDIT — timeline stepper ---- */}
      <div className="chart-card chart-card--wide">
        <h3>აუდიტის მზადყოფნა — {grade} ({Math.round(auditScore)}/100)</h3>
        <div className="exec-audit-section">
          <div className="exec-audit-left">
            <div
              className="val-score-gauge exec-audit-gauge"
              style={{ background: `conic-gradient(${gradeCol} 0% ${auditScore}%, rgba(255,255,255,0.07) ${auditScore}% 100%)` }}
            >
              <div className="val-score-gauge-inner">
                <span className="val-score-gauge-value" style={{ color: gradeCol }}>{Math.round(auditScore)}</span>
                <span className="val-score-gauge-max">/ 100</span>
              </div>
            </div>
            <div className="exec-grade-badge" style={{ background: `${gradeCol}22`, color: gradeCol, border: `2px solid ${gradeCol}66` }}>
              {grade}
            </div>
          </div>
          <div className="exec-audit-stepper">
            {criteria.map((item, i) => (
              <AuditStep key={item.id || i} item={item} isLast={i === criteria.length - 1} />
            ))}
          </div>
        </div>
        {audit.recommendation_ka && (
          <div className="exec-recommendation">
            <span className="exec-rec-icon">💡</span>
            <span>{audit.recommendation_ka}</span>
          </div>
        )}
      </div>

      {/* ---- D. KEY DECISIONS — timeline ---- */}
      {keyDecisions.length > 0 && (
        <div className="chart-card chart-card--wide">
          <h3>საკვანძო გადაწყვეტილებები</h3>
          <div className="exec-timeline">
            {keyDecisions.map((d, idx) => {
              const pCol = priorityColor(d.priority);
              const isLast = idx === keyDecisions.length - 1;
              return (
                <div key={`${d.priority}-${idx}`} className="exec-timeline-item">
                  <div className="exec-timeline-left">
                    <div className="exec-timeline-dot" style={{ background: `${pCol}22`, border: `2px solid ${pCol}`, color: pCol }}>
                      {d.priority}
                    </div>
                    {!isLast && <div className="exec-timeline-line" style={{ background: `linear-gradient(180deg, ${pCol}55, transparent)` }} />}
                  </div>
                  <div className="exec-timeline-card" style={{ borderLeftColor: pCol }}>
                    <div className="exec-decision-header">
                      <span className="exec-area-badge">{d.area}</span>
                    </div>
                    <div className="exec-decision-text">{d.decision_ka}</div>
                    {d.impact_ka && <div className="exec-decision-impact">{d.impact_ka}</div>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ---- E. NEXT STEPS — interactive checklist ---- */}
      {nextSteps.length > 0 && (
        <div className="chart-card chart-card--wide">
          <h3>შემდეგი ნაბიჯები</h3>
          <ul className="exec-steps-list">
            {nextSteps.map((step, i) => (
              <li key={i} className={`exec-step-item ${i % 2 === 1 ? 'exec-step-item--alt' : ''}`}>
                <span className="exec-step-check">☐</span>
                <span className="exec-step-text">{step}</span>
                <span className="exec-step-dots">
                  {Array.from({ length: Math.max(1, 5 - i) }, (_, k) => (
                    <span key={k} className="exec-step-dot" style={{ opacity: k === 0 ? 1 : 0.35 }}>●</span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ---- F. FOOTER — minimal divider ---- */}
      {(kpis.strongest_month || kpis.weakest_month || kpis.sector_score) && (
        <>
          <div className="exec-footer-divider" />
          <div className="exec-footer-hints">
            {kpis.strongest_month && (
              <span>ძლიერი: <strong style={{ color: '#22c55e' }}>{kpis.strongest_month}</strong></span>
            )}
            {kpis.weakest_month && (
              <span>სუსტი: <strong style={{ color: '#ef4444' }}>{kpis.weakest_month}</strong></span>
            )}
            {kpis.sector_score && (
              <span>სექტ. score: <strong style={{ color: '#eab308' }}>{Number(kpis.sector_score).toFixed(1)}/5.0</strong></span>
            )}
            {kpis.payment_ratio_pct && (
              <span>Payment: <strong className={Number(kpis.payment_ratio_pct) >= 80 ? 'amount-positive' : 'amount-negative'}>{fmtPct(kpis.payment_ratio_pct)}</strong></span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
