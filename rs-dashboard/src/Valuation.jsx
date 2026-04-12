import { useMemo } from 'react';

const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 0,
});
const fmt = (v) => GEL.format(Number(v) || 0);
const fmtNum = (v, dec = 1) => Number(v || 0).toFixed(dec);

const OBJECT_COLORS = {
  'ოზურგეთი': '#4f8ef7',
  'დვაბზუ': '#34c97e',
};

function overallScoreColor(score) {
  const s = Number(score) || 0;
  if (s >= 4) return '#34c97e';
  if (s >= 3) return '#a3e07a';
  if (s >= 2) return '#f7d434';
  return '#e05c6e';
}

function scoreColor(s) {
  const n = Number(s) || 0;
  if (n >= 4) return { bg: 'rgba(52,201,126,0.2)', color: '#34c97e', border: '#34c97e55' };
  if (n >= 3) return { bg: 'rgba(163,224,122,0.2)', color: '#a3e07a', border: '#a3e07a55' };
  if (n >= 2) return { bg: 'rgba(247,212,52,0.2)', color: '#f7d434', border: '#f7d43455' };
  return { bg: 'rgba(224,92,110,0.2)', color: '#e05c6e', border: '#e05c6e55' };
}

function efficiencyColor(score) {
  const s = Number(score) || 0;
  if (s >= 70) return '#34c97e';
  if (s >= 50) return '#f7d434';
  return '#e05c6e';
}

// Sector range bar: shows low→high band, with your_value as marker
function SectorRangeBar({ low, high, value, score }) {
  const range = (high - low) || 1;
  // clamp value position 0–100%
  const rawPct = ((value - low) / range) * 100;
  const markerPct = Math.max(2, Math.min(98, rawPct));
  const sc = scoreColor(score);

  return (
    <div className="val-sector-bar-wrap">
      <div className="val-sector-bar-track">
        <div className="val-sector-bar-band" />
        <div
          className="val-sector-bar-marker"
          style={{ left: `${markerPct}%`, background: sc.color }}
          title={`${fmtNum(value, 1)}%`}
        />
      </div>
      <div className="val-sector-bar-labels">
        <span>{fmtNum(low, 0)}%</span>
        <span>{fmtNum(high, 0)}%</span>
      </div>
    </div>
  );
}

// Valuation method range bar
function ValRangeBar({ low, median, high }) {
  const range = (high - low) || 1;
  const medPct = Math.max(2, Math.min(96, ((median - low) / range) * 100));
  return (
    <div className="val-method-bar-wrap">
      <div className="val-method-bar-track">
        <div className="val-method-bar-fill" />
        <div
          className="val-method-bar-median"
          style={{ left: `${medPct}%` }}
          title={`Median: ${fmt(median)}`}
        />
      </div>
      <div className="val-sector-bar-labels">
        <span className="amount-negative">{fmt(low)}</span>
        <span className="amount-positive">{fmt(high)}</span>
      </div>
    </div>
  );
}

// Overall score circular-like gauge (pure CSS arc via conic-gradient)
function ScoreGauge({ score, rainbow = false }) {
  const pct = Math.min(100, Math.max(0, (Number(score) / 5) * 100));
  const color = overallScoreColor(score);
  const bgGradient = rainbow
    ? `conic-gradient(#ef4444 0%, #f7a434 ${pct * 0.4}%, #eab308 ${pct * 0.65}%, #22c55e ${pct}%, rgba(255,255,255,0.08) ${pct}% 100%)`
    : `conic-gradient(${color} 0% ${pct}%, rgba(255,255,255,0.08) ${pct}% 100%)`;
  return (
    <div className="val-score-gauge-wrap">
      <div
        className="val-score-gauge"
        style={{ background: bgGradient }}
      >
        <div className="val-score-gauge-inner">
          <span className="val-score-gauge-value" style={{ color }}>
            {fmtNum(score)}
          </span>
          <span className="val-score-gauge-max">/ 5.0</span>
        </div>
      </div>
    </div>
  );
}

function SwotItem({ item }) {
  if (!item) return null;
  const hasMetric = item.metric && item.value !== undefined && item.value !== null;
  return (
    <div className="val-swot-item">
      <span className="val-swot-text">{item.text_ka}</span>
      {hasMetric && (
        <span className="val-swot-metric-badge">
          {item.metric}:           {typeof item.value === 'number' ? fmtNum(item.value, 1) : item.value}
          {String(item.metric).includes('pct') || String(item.metric).includes('margin') || String(item.metric).includes('ratio') ? '%' : String(item.metric).includes('days') ? ' დღე' : ''}
        </span>
      )}
    </div>
  );
}

export default function Valuation({ companyValuation }) {
  const cv = companyValuation;

  const sectorComparison = useMemo(
    () => (Array.isArray(cv?.sector_comparison) ? cv.sector_comparison : []),
    [cv],
  );
  const valuation = useMemo(() => cv?.valuation || {}, [cv]);
  const swot = useMemo(() => cv?.swot || {}, [cv]);
  const objectEfficiency = useMemo(() => cv?.object_efficiency || {}, [cv]);

  if (!cv) {
    return (
      <div className="cashflow-page pnl-empty">
        <div
          className="kpi-card"
          style={{ maxWidth: 520, margin: '48px auto', textAlign: 'center' }}
        >
          <div className="kpi-label">კომპანიის შეფასება ჯერ არ არის</div>
          <div className="kpi-sub" style={{ marginTop: 12 }}>
            გაუშვი ტერმინალში:
          </div>
          <code className="pnl-code-hint">python generate_dashboard_data.py</code>
        </div>
      </div>
    );
  }

  const overallScore = Number(cv.overall_sector_score) || 0;
  const scoreCol = overallScoreColor(overallScore);
  const valMethods = Array.isArray(valuation.methods) ? valuation.methods : [];
  const skippedMethods = Array.isArray(valuation.skipped_methods) ? valuation.skipped_methods : [];
  const valRange = valuation.range || {};

  return (
    <div className="cashflow-page">

      {/* Tab Hero */}
      <div className="tab-hero">
        <span className="tab-hero-title">🏆 შეფასება — ვალუაცია + SWOT + სექტორი</span>
        <span className="tab-hero-desc">კომპანიის ბიზნეს ღირებულება · სექტორთან შედარება · ობიექტების ეფექტურობა</span>
      </div>

      {/* ---- A. Header: Overall Score + Valuation Range ---- */}
      <div className="val-header-grid">
        {/* Score — rainbow gauge */}
        <div className="val-header-score chart-card">
          <div className="kpi-label" style={{ textAlign: 'center', marginBottom: 8 }}>
            სექტორთან შედარება — საერთო შეფასება
          </div>
          <ScoreGauge score={overallScore} rainbow />
          {cv.overall_assessment_ka && (
            <p className="val-overall-assessment">{cv.overall_assessment_ka}</p>
          )}
        </div>

        {/* Valuation Range */}
        <div className="val-header-range chart-card">
          <div className="kpi-label" style={{ marginBottom: 12 }}>
            კომპანიის ვალუაცია (ბიზნეს ღირებულება)
          </div>
          <div className="val-range-row">
            <div className="val-range-item">
              <div className="val-range-label">LOW</div>
              <div className="val-range-value amount-negative">{fmt(valRange.low)}</div>
            </div>
            <div className="val-range-sep">|</div>
            <div className="val-range-item">
              <div className="val-range-label" style={{ color: scoreCol }}>MEDIAN</div>
              <div className="val-range-value" style={{ color: scoreCol }}>{fmt(valRange.median)}</div>
            </div>
            <div className="val-range-sep">|</div>
            <div className="val-range-item">
              <div className="val-range-label">HIGH</div>
              <div className="val-range-value amount-positive">{fmt(valRange.high)}</div>
            </div>
          </div>
          <div className="val-financials-row">
            <span className="kpi-sub">წლ. შემოსავალი: <strong className="amount-positive">{fmt(valuation.annual_revenue)}</strong></span>
            <span className="kpi-sub">წლ. Net: <strong className="amount-positive">{fmt(valuation.annual_net)}</strong></span>
            {valuation.annual_ebitda != null && (
              <span className="kpi-sub">EBITDA: <strong className="amount-positive">{fmt(valuation.annual_ebitda)}</strong></span>
            )}
          </div>
          {valuation.note_ka && (
            <p className="val-note">{valuation.note_ka}</p>
          )}
        </div>
      </div>

      {/* ---- B. სექტორთან შედარება ---- */}
      {sectorComparison.length > 0 && (
        <div className="chart-card chart-card--wide">
          <h3>სექტორთან შედარება — მეტრიკები</h3>
          <div className="val-sector-list">
            {sectorComparison.map((item) => {
              const sc = scoreColor(item.score);
              return (
                <div key={item.metric} className="val-sector-row">
                  <div className="val-sector-label">{item.label_ka || item.metric}</div>
                  <div className="val-sector-center">
                    <div className="val-sector-your-value">
                      {fmtNum(item.your_value, 1)}%
                    </div>
                    <SectorRangeBar
                      low={item.sector_low}
                      high={item.sector_high}
                      value={item.your_value}
                      score={item.score}
                    />
                  </div>
                  <div className="val-sector-right">
                    <span
                      className="val-score-badge"
                      style={{ background: sc.bg, color: sc.color, border: `1px solid ${sc.border}` }}
                    >
                      {item.score}/5
                    </span>
                    <span className="val-sector-assessment">{item.assessment_ka}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ---- C. ვალუაციის მეთოდები ---- */}
      {(valMethods.length > 0 || skippedMethods.length > 0) && (
        <div className="chart-card chart-card--wide">
          <h3>ვალუაციის მეთოდები</h3>
          <div className="val-methods-grid">
            {valMethods.map((m) => (
              <div className="kpi-card val-method-card" key={m.method}>
                <div className="kpi-label">{m.method}</div>
                <div className="val-method-values">
                  <div>
                    <div className="val-range-label">LOW</div>
                    <div className="amount-negative" style={{ fontSize: '0.9rem', fontWeight: 600 }}>{fmt(m.low)}</div>
                  </div>
                  <div>
                    <div className="val-range-label">MEDIAN</div>
                    <div style={{ fontSize: '1rem', fontWeight: 700, color: scoreCol }}>{fmt(m.median)}</div>
                  </div>
                  <div>
                    <div className="val-range-label">HIGH</div>
                    <div className="amount-positive" style={{ fontSize: '0.9rem', fontWeight: 600 }}>{fmt(m.high)}</div>
                  </div>
                </div>
                <ValRangeBar low={m.low} median={m.median} high={m.high} />
              </div>
            ))}
            {skippedMethods.map((m) => (
              <div className="kpi-card val-method-card" key={m.method} style={{ opacity: 0.7, borderTop: '3px solid #8899aa' }}>
                <div className="kpi-label" style={{ color: '#8899aa' }}>{m.method}</div>
                <div className="val-method-values" style={{ marginTop: 12 }}>
                  <div style={{ color: '#8899aa', fontSize: '0.9rem' }}>
                    {m.reason_ka || 'მონაცემები არასაკმარისია'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---- D. SWOT ---- */}
      {(swot.strengths || swot.weaknesses || swot.opportunities || swot.threats) && (
        <div className="chart-card chart-card--wide">
          <h3>SWOT ანალიზი</h3>
          <div className="val-swot-grid">
            {/* Strengths */}
            <div className="val-swot-quad val-swot-strengths">
              <div className="val-swot-quad-title">💪 ძლიერი მხარეები</div>
              {(swot.strengths || []).map((item, i) => (
                <SwotItem key={i} item={item} />
              ))}
            </div>
            {/* Weaknesses */}
            <div className="val-swot-quad val-swot-weaknesses">
              <div className="val-swot-quad-title">⚠️ სუსტი მხარეები</div>
              {(swot.weaknesses || []).map((item, i) => (
                <SwotItem key={i} item={item} />
              ))}
            </div>
            {/* Opportunities */}
            <div className="val-swot-quad val-swot-opportunities">
              <div className="val-swot-quad-title">🚀 შესაძლებლობები</div>
              {(swot.opportunities || []).map((item, i) => (
                <SwotItem key={i} item={item} />
              ))}
            </div>
            {/* Threats */}
            <div className="val-swot-quad val-swot-threats">
              <div className="val-swot-quad-title">🔥 საფრთხეები</div>
              {(swot.threats || []).map((item, i) => (
                <SwotItem key={i} item={item} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ---- E. ობიექტების ეფექტურობა ---- */}
      {Object.keys(objectEfficiency).length > 0 && (
        <div className="chart-card chart-card--wide">
          <h3>ობიექტების ეფექტურობა</h3>
          <div className="val-obj-eff-grid">
            {Object.entries(objectEfficiency).map(([obj, eff]) => {
              const score = Number(eff.score) || 0;
              const color = OBJECT_COLORS[obj] || '#8899aa';
              const effCol = efficiencyColor(score);
              const pct = Math.min(100, score);
              const isWarning = eff.note_ka && (
                eff.note_ka.includes('ატრიბუცია') ||
                eff.note_ka.includes('არაზუსტი') ||
                eff.note_ka.includes('გაფრთხილება')
              );
              return (
                <div
                  key={obj}
                  className="kpi-card val-obj-eff-card"
                  style={{ borderTop: `3px solid ${color}` }}
                >
                  <div className="kpi-label" style={{ color }}>{obj}</div>
                  <div className="val-obj-score-row">
                    <span style={{ fontSize: '2rem', fontWeight: 700, color: effCol }}>
                      {fmtNum(score)}
                    </span>
                    <span className="kpi-sub" style={{ alignSelf: 'flex-end' }}> / 100</span>
                  </div>
                  <div className="ratio-gauge" style={{ marginBottom: 8 }}>
                    <div className="ratio-gauge-fill" style={{ width: `${pct}%`, background: effCol }} />
                  </div>
                  {eff.note_ka && (
                    <p className={`val-obj-note ${isWarning ? 'val-obj-note--warn' : ''}`}>
                      {eff.note_ka}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
