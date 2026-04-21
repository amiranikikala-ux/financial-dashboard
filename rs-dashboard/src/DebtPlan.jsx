import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchApiJson } from './lib/api.js';

const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 0,
});
const fmt = (v) => GEL.format(Number(v) || 0);
const fmtPct = (v) => `${(Number(v) || 0).toFixed(1)}%`;

const TREND_META = {
  stable: { label: '🟢 სტაბილური', color: '#22c55e' },
  growing: { label: '🟢 იზრდება', color: '#22c55e' },
  declining: { label: '🟠 კლებულობს', color: '#f97316' },
  insufficient_history: { label: '⚪ ცოტა მონაცემია', color: '#94a3b8' },
};

const DURATION_OPTIONS = [1, 2, 3, 4, 6];
const MAX_PRIORITY_OPTIONS = [3, 4, 5, 6, 8];

function ForecastCard({ forecast }) {
  if (!forecast) return null;
  const trendMeta = TREND_META[forecast.trend] || {
    label: forecast.trend || '—',
    color: '#94a3b8',
  };
  return (
    <div style={{
      padding: 14,
      background: '#1e293b',
      border: '1px solid #334155',
      borderRadius: 10,
    }}>
      <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 2 }}>
        🏦 ყოველთვიური შემოსავლის პროგნოზი
      </div>
      <div style={{
        fontSize: 26,
        fontWeight: 700,
        color: '#e2e8f0',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {fmt(forecast.monthly_inflow_ge)}
      </div>
      <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
        დიაპაზონი: {fmt(forecast.low_ge)} — {fmt(forecast.high_ge)}
      </div>
      <div style={{ marginTop: 8, display: 'flex', gap: 6, alignItems: 'center' }}>
        <span style={{ color: trendMeta.color, fontSize: 12, fontWeight: 600 }}>
          {trendMeta.label}
        </span>
        {forecast.method && (
          <span style={{ fontSize: 10, color: '#64748b' }}>· {forecast.method}</span>
        )}
      </div>
    </div>
  );
}

function AllocationCard({ allocation }) {
  if (!allocation) return null;
  const sustainable = allocation.sustainable !== false;
  return (
    <div style={{
      padding: 14,
      background: '#1e293b',
      border: `1px solid ${sustainable ? '#22c55e40' : '#ef444480'}`,
      borderRadius: 10,
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        marginBottom: 8,
      }}>
        <div style={{ fontSize: 11, color: '#94a3b8' }}>💰 გეგმის განაწილება</div>
        <span style={{
          padding: '2px 8px',
          borderRadius: 4,
          fontSize: 11,
          fontWeight: 600,
          background: sustainable ? '#22c55e20' : '#ef444420',
          color: sustainable ? '#22c55e' : '#ef4444',
        }}>
          {sustainable ? '🟢 მდგრადი' : '🔴 არამდგრადი'}
        </span>
      </div>

      <div style={{ display: 'grid', gap: 6, fontSize: 13 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#cbd5e1' }}>⭐ პრიორიტეტული:</span>
          <span style={{ color: '#fbbf24', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
            {fmt(allocation.priority_monthly_ge)}/თვე
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#cbd5e1' }}>📦 დანარჩენი (baseline):</span>
          <span style={{ color: '#cbd5e1', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
            {fmt(allocation.non_priority_monthly_ge)}/თვე
          </span>
        </div>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          paddingTop: 6,
          borderTop: '1px solid #334155',
        }}>
          <span style={{ color: '#cbd5e1' }}>💵 Buffer:</span>
          <span style={{
            color: sustainable ? '#22c55e' : '#ef4444',
            fontWeight: 700,
            fontVariantNumeric: 'tabular-nums',
          }}>
            {fmt(allocation.buffer_ge)} ({fmtPct(allocation.buffer_pct)})
          </span>
        </div>
      </div>
    </div>
  );
}

function PriorityTable({ priorities }) {
  const rows = Array.isArray(priorities) ? priorities : [];
  if (rows.length === 0) {
    return (
      <div style={{
        padding: 20,
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: 10,
        color: '#94a3b8',
        textAlign: 'center',
        fontSize: 13,
      }}>
        პრიორიტეტული მომწოდებლები არ მოიძებნა.
      </div>
    );
  }
  return (
    <div style={{
      background: '#1e293b',
      border: '1px solid #334155',
      borderRadius: 10,
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid #334155',
        fontSize: 14,
        fontWeight: 600,
        color: '#e2e8f0',
      }}>
        ⭐ პრიორიტეტული მომწოდებლები ({rows.length})
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{
              color: '#94a3b8',
              textAlign: 'left',
              borderBottom: '1px solid #334155',
              background: '#0f172a',
            }}>
              <th style={{ padding: '8px 10px', fontWeight: 500 }}>#</th>
              <th style={{ padding: '8px 10px', fontWeight: 500 }}>მომწოდებელი</th>
              <th style={{ padding: '8px 10px', fontWeight: 500, textAlign: 'right' }}>ვალი</th>
              <th style={{ padding: '8px 10px', fontWeight: 500, textAlign: 'right' }}>ისტ./თვე</th>
              <th style={{ padding: '8px 10px', fontWeight: 500, textAlign: 'right' }}>რეკ./თვე</th>
              <th style={{ padding: '8px 10px', fontWeight: 500, textAlign: 'right' }}>კვირაში</th>
              <th style={{ padding: '8px 10px', fontWeight: 500, textAlign: 'right' }}>დღე→0</th>
              <th style={{ padding: '8px 10px', fontWeight: 500 }}>Conf.</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, idx) => (
              <PriorityRow key={r.tax_id || idx} rank={idx + 1} row={r} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PriorityRow({ rank, row }) {
  const [expanded, setExpanded] = useState(false);
  const reasons = Array.isArray(row.criticality_reasons) ? row.criticality_reasons : [];

  return (
    <>
      <tr
        style={{
          borderBottom: '1px solid #0f172a',
          cursor: 'pointer',
          background: expanded ? '#0f172a' : 'transparent',
        }}
        onClick={() => setExpanded((v) => !v)}
      >
        <td style={{ padding: '10px', color: '#94a3b8', fontVariantNumeric: 'tabular-nums' }}>
          {rank}
        </td>
        <td style={{ padding: '10px', color: '#e2e8f0' }}>
          <div style={{ fontWeight: 600 }}>{row.org || '—'}</div>
          {row.tax_id && (
            <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>
              {row.tax_id}
            </div>
          )}
        </td>
        <td style={{
          padding: '10px',
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          color: '#fbbf24',
          fontWeight: 600,
        }}>
          {fmt(row.total_debt_ge)}
        </td>
        <td style={{
          padding: '10px',
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          color: '#94a3b8',
        }}>
          {fmt(row.historical_monthly_paid_ge)}
        </td>
        <td style={{
          padding: '10px',
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          color: '#22c55e',
          fontWeight: 700,
        }}>
          {fmt(row.recommended_monthly_payment_ge)}
        </td>
        <td style={{
          padding: '10px',
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          color: '#cbd5e1',
        }}>
          {fmt(row.recommended_weekly_payment_ge)}
        </td>
        <td style={{
          padding: '10px',
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          color: '#94a3b8',
        }}>
          {row.days_to_clear_est != null ? `${row.days_to_clear_est} დღე` : '—'}
        </td>
        <td style={{ padding: '10px', fontSize: 11 }}>
          {row.confidence_label || '—'}
        </td>
      </tr>
      {expanded && (
        <tr style={{ background: '#0f172a' }}>
          <td colSpan={8} style={{ padding: '8px 14px 14px 40px' }}>
            {reasons.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
                  💡 რატომ კრიტიკული:
                </div>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: '#cbd5e1' }}>
                  {reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
            {row.rationale_ka && (
              <div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
                  📝 ანალიზი:
                </div>
                <div style={{ fontSize: 12, color: '#e2e8f0', lineHeight: 1.5 }}>
                  {row.rationale_ka}
                </div>
              </div>
            )}
            {row.days_since_last != null && (
              <div style={{ marginTop: 6, fontSize: 11, color: '#64748b' }}>
                ბოლო მიწოდება: {row.days_since_last} დღის წინ · criticality score:{' '}
                {row.criticality_score != null ? row.criticality_score.toFixed(2) : '—'}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function NonPriorityCard({ summary }) {
  if (!summary) return null;
  const count = Number(summary.supplier_count) || 0;
  if (count === 0) {
    return null;
  }
  return (
    <div style={{
      padding: 14,
      background: '#1e293b',
      border: '1px solid #334155',
      borderRadius: 10,
    }}>
      <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 2 }}>
        📦 დანარჩენი მომწოდებლები
      </div>
      <div style={{
        fontSize: 22,
        fontWeight: 700,
        color: '#e2e8f0',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {count} მომწოდებელი
      </div>
      <div style={{ fontSize: 13, color: '#cbd5e1', marginTop: 4 }}>
        Baseline: <strong>{fmt(summary.total_baseline_monthly_ge)}</strong>/თვე
      </div>
      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
        საშუალო: ~{fmt(summary.average_per_supplier_ge)}/თვე თითოზე
      </div>
      {summary.note_ka && (
        <div style={{ fontSize: 11, color: '#64748b', marginTop: 6, fontStyle: 'italic' }}>
          {summary.note_ka}
        </div>
      )}
    </div>
  );
}

function RisksBox({ risks }) {
  const items = Array.isArray(risks) ? risks.filter(Boolean) : [];
  if (items.length === 0) return null;
  return (
    <div style={{
      padding: 12,
      background: 'rgba(234, 179, 8, 0.1)',
      border: '1px solid rgba(234, 179, 8, 0.4)',
      borderRadius: 8,
      color: '#fde68a',
    }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
        ⚠️ რისკები ({items.length})
      </div>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.5 }}>
        {items.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
    </div>
  );
}

function EmptyState({ message, hint }) {
  return (
    <div style={{
      padding: 20,
      background: '#1e293b',
      border: '1px solid #334155',
      borderRadius: 8,
      color: '#fbbf24',
    }}>
      <strong>{message}</strong>
      {hint && (
        <div style={{ marginTop: 6, color: '#cbd5e1', fontSize: 13 }}>
          {hint}
        </div>
      )}
    </div>
  );
}

export default function DebtPlan() {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState(null);

  const [duration, setDuration] = useState(2);
  const [maxPriority, setMaxPriority] = useState(5);

  const abortRef = useRef(null);

  const buildTitle = useCallback((planData) => {
    const count = Array.isArray(planData?.priority_suppliers)
      ? planData.priority_suppliers.length
      : 0;
    const monthly = planData?.allocation_summary?.priority_monthly_ge ?? 0;
    const months = planData?.plan_duration_months ?? duration;
    return `📋 ვალების გეგმა — ${count} priority @ ${fmt(monthly)}/თვე (${months}-თვიანი)`;
  }, [duration]);

  const generate = useCallback(async (opts = {}) => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setSavedId(null);

    const body = {
      plan_duration_months: opts.duration ?? duration,
      max_priority_count: opts.maxPriority ?? maxPriority,
    };
    try {
      const result = await fetchApiJson('/api/debt-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!controller.signal.aborted) {
        setPlan(result);
        setLoading(false);
      }
    } catch (err) {
      if (err.name === 'AbortError') return;
      console.error('debt-plan generation failed:', err);
      setError(err.message || 'უცნობი შეცდომა');
      setLoading(false);
    }
  }, [duration, maxPriority]);

  // Auto-generate on first mount
  useEffect(() => {
    generate();
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRegenerate = () => generate();

  const handleApprove = async () => {
    if (!plan || saving) return;
    setSaving(true);
    try {
      const title = buildTitle(plan);
      const tags = [
        'phase4a',
        `duration:${plan.plan_duration_months ?? duration}mo`,
        `priority_count:${plan.priority_suppliers?.length ?? 0}`,
        `sustainable:${plan.allocation_summary?.sustainable ? 'true' : 'false'}`,
      ];
      const result = await fetchApiJson('/api/debt-plan/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, tags }),
      });
      setSavedId(result.entry_id || 'saved');
    } catch (err) {
      console.error('save failed:', err);
      setError(`შენახვა ვერ მოხერხდა: ${err.message || 'უცნობი შეცდომა'}`);
    } finally {
      setSaving(false);
    }
  };

  const planErrorMessage = useMemo(() => {
    if (!plan) return null;
    if (plan.error) return String(plan.error);
    return null;
  }, [plan]);

  return (
    <div style={{ padding: '12px 4px', color: '#e2e8f0' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 10,
        marginBottom: 12,
      }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>
          📋 ვალების გეგმა — AI-ს ავტონომიური რჩევა
        </h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ fontSize: 11, color: '#94a3b8' }}>
            ხანგრძლივობა:{' '}
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              disabled={loading}
              style={{
                background: '#0f172a',
                color: '#e2e8f0',
                border: '1px solid #334155',
                borderRadius: 6,
                padding: '4px 8px',
                fontSize: 12,
              }}
            >
              {DURATION_OPTIONS.map((n) => (
                <option key={n} value={n}>{n} თვე</option>
              ))}
            </select>
          </label>
          <label style={{ fontSize: 11, color: '#94a3b8' }}>
            პრიორიტეტი:{' '}
            <select
              value={maxPriority}
              onChange={(e) => setMaxPriority(Number(e.target.value))}
              disabled={loading}
              style={{
                background: '#0f172a',
                color: '#e2e8f0',
                border: '1px solid #334155',
                borderRadius: 6,
                padding: '4px 8px',
                fontSize: 12,
              }}
            >
              {MAX_PRIORITY_OPTIONS.map((n) => (
                <option key={n} value={n}>Top-{n}</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={loading}
            style={{
              padding: '6px 14px',
              background: loading ? '#334155' : '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? '⏳ ვამზადებ...' : '🔄 ახალი გეგმა'}
          </button>
        </div>
      </div>

      {/* Intro blurb — shows Phase 4 philosophy to user */}
      <div style={{
        padding: '8px 12px',
        background: 'rgba(59, 130, 246, 0.08)',
        border: '1px solid rgba(59, 130, 246, 0.3)',
        borderRadius: 8,
        fontSize: 12,
        color: '#cbd5e1',
        marginBottom: 14,
      }}>
        💡 <strong>AI-მ თვითონ ამოიცნო</strong> კრიტიკული მომწოდებლები data-დან
        (ვალი + ასაკი + მიწოდების სიხშირე + გადახდის დისფუნქცია) და შესთავაზა განაწილება.
        შეცვალე ხანგრძლივობა ან priority რაოდენობა და ხელახლა გამოთვალე.
      </div>

      {/* Error */}
      {error && (
        <EmptyState
          message="⚠️ შეცდომა გეგმის გენერაციისას"
          hint={error}
        />
      )}

      {/* Plan returned explicit error (e.g. no debt) */}
      {!error && planErrorMessage && (
        <EmptyState
          message="ⓘ გეგმა ვერ შედგა"
          hint={planErrorMessage}
        />
      )}

      {/* Loading skeleton */}
      {loading && !plan && (
        <div style={{
          padding: 40,
          textAlign: 'center',
          color: '#94a3b8',
          fontSize: 14,
        }}>
          ⏳ ვამზადებ გეგმას (AI ცდა 4-ფაქტორიან criticality score-ს + inflow forecast-ს)...
        </div>
      )}

      {/* Main content */}
      {plan && !planErrorMessage && !error && (
        <>
          {/* Summary strip */}
          {plan.summary_ka && (
            <div style={{
              padding: 12,
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: 8,
              fontSize: 13,
              color: '#e2e8f0',
              marginBottom: 14,
              lineHeight: 1.5,
            }}>
              {plan.summary_ka}
            </div>
          )}

          {/* 3-card strip: forecast / allocation / non-priority */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 12,
            marginBottom: 14,
          }}>
            <ForecastCard forecast={plan.forecast} />
            <AllocationCard allocation={plan.allocation_summary} />
            <NonPriorityCard summary={plan.non_priority_summary} />
          </div>

          {/* Risks */}
          {plan.risks && plan.risks.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <RisksBox risks={plan.risks} />
            </div>
          )}

          {/* Priority table */}
          <div style={{ marginBottom: 14 }}>
            <PriorityTable priorities={plan.priority_suppliers} />
          </div>

          {/* Action bar */}
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 10,
            padding: 12,
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: 10,
            alignItems: 'center',
          }}>
            <div style={{ flex: 1, minWidth: 200, fontSize: 12, color: '#94a3b8' }}>
              📝 ეთანხმები? შეინახე ჟურნალში რომ მერე დაიწყო თვალყურის დევნება.
            </div>
            <button
              type="button"
              onClick={handleApprove}
              disabled={saving || Boolean(savedId)}
              style={{
                padding: '8px 16px',
                background: savedId ? '#334155' : (saving ? '#334155' : '#22c55e'),
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                cursor: saving || savedId ? 'not-allowed' : 'pointer',
              }}
            >
              {savedId
                ? '✅ შენახულია ჟურნალში'
                : (saving ? '⏳ ვინახავ...' : '✅ ვეთანხმები — შენახვა')}
            </button>
            <button
              type="button"
              onClick={handleRegenerate}
              disabled={loading}
              style={{
                padding: '8px 16px',
                background: '#475569',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              🔄 სხვა ვერსია
            </button>
          </div>

          {/* Notes */}
          {Array.isArray(plan.notes) && plan.notes.length > 0 && (
            <div style={{ marginTop: 12, fontSize: 11, color: '#64748b' }}>
              {plan.notes.map((n, i) => (
                <div key={i} style={{ marginBottom: 2 }}>ⓘ {n}</div>
              ))}
            </div>
          )}

          {/* Footer provenance */}
          <div style={{ marginTop: 10, fontSize: 10, color: '#64748b' }}>
            წყარო: data.json · build_debt_repayment_plan (supplier_aging + monthly_pnl
            triangulation) · as of {plan.as_of_date} · duration{' '}
            {plan.plan_duration_months} თვე
          </div>
        </>
      )}
    </div>
  );
}
