import { useMemo } from 'react';

const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 0,
});

const fmt = (v) => GEL.format(Number(v) || 0);

function hhiBand(hhi) {
  const value = Number(hhi) || 0;
  if (value >= 2500) return { label: '🔴 კრიტიკული', color: '#ef4444', noteKa: 'პორტფელი ძალიან კონცენტრირებულია' };
  if (value >= 1500) return { label: '🟠 მაღალი', color: '#f97316', noteKa: 'მაღალი დამოკიდებულება Top-ზე' };
  if (value >= 500) return { label: '🟡 ზომიერი', color: '#eab308', noteKa: 'ზომიერი კონცენტრაცია' };
  return { label: '🟢 დაბალი', color: '#22c55e', noteKa: 'კარგად გაფანტული პორტფელი' };
}

function leverageBand(score) {
  const value = Number(score) || 0;
  if (value >= 70) return { label: '🟢 მაღალი', color: '#22c55e' };
  if (value >= 40) return { label: '🟡 საშუალო', color: '#eab308' };
  return { label: '🟠 დაბალი', color: '#f97316' };
}

function MiniGauge({ value, maxValue = 10000, color }) {
  const pct = Math.max(0, Math.min(100, (Number(value) || 0) * 100 / maxValue));
  return (
    <div style={{ position: 'relative', width: '100%', height: 8, background: '#1f2937', borderRadius: 4, overflow: 'hidden' }}>
      <div
        style={{
          width: `${pct}%`,
          height: '100%',
          background: color,
          transition: 'width 0.4s ease-out',
        }}
      />
    </div>
  );
}

function ConcentrationBar({ share, color }) {
  const pct = Math.max(0, Math.min(100, Number(share) || 0));
  return (
    <div style={{ position: 'relative', width: '100%', height: 6, background: '#0f172a', borderRadius: 3, overflow: 'hidden' }}>
      <div
        style={{
          width: `${pct}%`,
          height: '100%',
          background: color,
        }}
      />
    </div>
  );
}

export default function SupplierConcentrationWidget({ payload }) {
  const data = payload && typeof payload === 'object' ? payload : null;

  const empty = !data || data.available === false || !data.concentration;

  const concentration = useMemo(() => data?.concentration || {}, [data]);
  const topCandidates = useMemo(
    () => (Array.isArray(data?.top_candidates) ? data.top_candidates.slice(0, 3) : []),
    [data],
  );

  if (empty) {
    return (
      <div className="widget-card" style={{
        padding: '14px 18px',
        background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
        border: '1px solid #334155',
        borderRadius: 8,
        marginBottom: 12,
        color: '#cbd5e1',
        fontSize: 13,
      }}>
        <strong>⚠️ მომწოდებლების კონცენტრაცია</strong>
        <span style={{ marginLeft: 10, color: '#94a3b8' }}>
          {data?.reason_ka || 'პორტფელის ანალიზი ჯერ არ გვაქვს — გადაატრიალე pipeline.'}
        </span>
      </div>
    );
  }

  const band = hhiBand(concentration.hhi_index);
  const totalSpend = Number(data.total_spend_ge) || 0;
  const totalSuppliers = Number(data.total_suppliers) || 0;
  const topOne = topCandidates[0];

  return (
    <div
      className="widget-card"
      style={{
        padding: 16,
        background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
        border: '1px solid #334155',
        borderRadius: 10,
        marginBottom: 14,
        color: '#e2e8f0',
        fontSize: 13,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ fontSize: 14, fontWeight: 700 }}>
          ⚠️ მომწოდებლების კონცენტრაცია
        </div>
        <div
          style={{ fontSize: 11, color: '#94a3b8' }}
          title="HHI / Top-N გათვლა მოიცავს ყველა მომწოდებელს — archive/მოხსნილსაც"
        >
          {totalSuppliers} მომწოდებელი · სულ {fmt(totalSpend)}
          <span style={{ marginLeft: 6, fontSize: 10, color: '#64748b' }}>
            (archive/მოხსნილი ჩათვლით)
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18, marginBottom: 14 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
            <span style={{ color: '#94a3b8', fontSize: 11 }}>HHI ინდექსი</span>
            <span style={{ fontSize: 18, fontWeight: 700, color: band.color }}>
              {Math.round(Number(concentration.hhi_index) || 0)}
            </span>
            <span style={{ fontSize: 12, color: band.color }}>{band.label}</span>
          </div>
          <MiniGauge value={concentration.hhi_index} maxValue={10000} color={band.color} />
          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
            {band.noteKa}
          </div>
        </div>

        <div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {[5, 10, 20].map((n) => {
              const key = `top_${n}_share_pct`;
              const share = Number(concentration[key]) || 0;
              return (
                <div key={n} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 48, color: '#94a3b8', fontSize: 11 }}>Top-{n}:</span>
                  <div style={{ flex: 1 }}>
                    <ConcentrationBar share={share} color="#60a5fa" />
                  </div>
                  <span style={{ width: 52, textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#e2e8f0', fontWeight: 600 }}>
                    {share.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {topCandidates.length > 0 && (
        <div>
          <div style={{ color: '#94a3b8', fontSize: 11, marginBottom: 6 }}>
            🎯 Top-3 მოლაპარაკების კანდიდატი (leverage × savings-ით)
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ color: '#94a3b8', textAlign: 'left' }}>
                <th style={{ padding: '4px 6px', fontWeight: 500 }}>#</th>
                <th style={{ padding: '4px 6px', fontWeight: 500 }}>მომწოდებელი</th>
                <th style={{ padding: '4px 6px', fontWeight: 500, textAlign: 'right' }}>წილი %</th>
                <th style={{ padding: '4px 6px', fontWeight: 500 }}>ბერკეტი</th>
                <th style={{ padding: '4px 6px', fontWeight: 500, textAlign: 'right' }}>~წლიური დაზოგვა</th>
              </tr>
            </thead>
            <tbody>
              {topCandidates.map((c) => {
                const band2 = leverageBand(c.leverage_score);
                return (
                  <tr key={c.rank || c.supplier_name} style={{ borderTop: '1px solid #1e293b' }}>
                    <td style={{ padding: '6px', color: '#94a3b8', fontWeight: 600 }}>#{c.rank}</td>
                    <td style={{ padding: '6px', fontWeight: 600 }}>{c.supplier_name || '—'}</td>
                    <td style={{ padding: '6px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {(Number(c.portfolio_share_pct) || 0).toFixed(2)}%
                    </td>
                    <td style={{ padding: '6px' }}>
                      <span style={{ color: band2.color, fontWeight: 600 }}>{band2.label}</span>
                      <span style={{ color: '#64748b', marginLeft: 6 }}>({c.leverage_score}/100)</span>
                    </td>
                    <td style={{ padding: '6px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#22c55e' }}>
                      {fmt(c.estimated_annual_savings_ge)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {topOne && (
            <div style={{
              marginTop: 10,
              padding: '8px 10px',
              background: 'rgba(34, 197, 94, 0.08)',
              border: '1px solid rgba(34, 197, 94, 0.25)',
              borderRadius: 6,
              color: '#bbf7d0',
              fontSize: 12,
            }}>
              🎯 <strong>#1 პრიორიტეტი:</strong> დაიწყე <strong>{topOne.supplier_name}</strong>-დან —
              {' '}{(Number(topOne.portfolio_share_pct) || 0).toFixed(1)}% წილი, ~{fmt(topOne.estimated_annual_savings_ge)} დაზოგვა.
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: 10, fontSize: 10, color: '#64748b' }}>
        წყარო: data.json · prepare_supplier_brief (portfolio mode) · დახარისხებული ბერკეტი × დაზოგვა × ბრუნვით
      </div>
    </div>
  );
}
