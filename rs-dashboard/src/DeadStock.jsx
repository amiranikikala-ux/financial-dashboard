import { useMemo, useState } from 'react';
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 0,
});

const fmt = (v) => GEL.format(Number(v) || 0);
const fmtNumber = (v) => new Intl.NumberFormat('ka-GE').format(Number(v) || 0);

const BUCKET_LABELS = {
  stale_91_180d: { label: '🟡 91–180 დღე', color: '#eab308' },
  stale_181_365d: { label: '🟠 181–365 დღე', color: '#f97316' },
  dead_365d_plus: { label: '🔴 365+ დღე', color: '#ef4444' },
  unmatched: { label: '⚪ Unmatched', color: '#64748b' },
  active: { label: '🟢 აქტიური', color: '#22c55e' },
};

const ACTION_LABELS = {
  discount_15_pct: { label: '🟢 −15% ფასდაკლება', color: '#22c55e', priority: 1 },
  discount_30_pct: { label: '🟡 −30% ფასდაკლება', color: '#eab308', priority: 2 },
  supplier_return: { label: '🟢 მომწოდებელს დავუბრუნე', color: '#10b981', priority: 0 },
  write_off: { label: '🔴 Write-off', color: '#ef4444', priority: 3 },
};

const BUCKET_SORT_OPTIONS = [
  { value: 'all', label: 'ყველა stale' },
  { value: 'stale_181_365d', label: '181–365 დღე' },
  { value: 'dead_365d_plus', label: '365+ დღე' },
  { value: 'unmatched', label: 'Unmatched' },
];

const ACTION_SORT_OPTIONS = [
  { value: 'all', label: 'ყველა action' },
  { value: 'supplier_return', label: 'მომწოდებელს დაბრუნება' },
  { value: 'discount_15_pct', label: '−15% ფასდაკლება' },
  { value: 'discount_30_pct', label: '−30% ფასდაკლება' },
  { value: 'write_off', label: 'Write-off' },
];

function DonutTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0];
  return (
    <div className="pnl-tooltip">
      <div className="pnl-tooltip-label">{p.payload.bucketLabel}</div>
      <div>SKU: {fmtNumber(p.payload.value)}</div>
      {p.payload.amount != null && <div>თანხა: {fmt(p.payload.amount)}</div>}
    </div>
  );
}

function ActionCard({ actionKey, data }) {
  const meta = ACTION_LABELS[actionKey] || { label: actionKey, color: '#94a3b8' };
  const skuCount = Number(data?.sku_count) || 0;
  const freedCash = Number(data?.freed_cash_estimate) || 0;
  const empty = skuCount === 0;
  return (
    <div style={{
      padding: 12,
      background: empty ? '#111827' : '#1e293b',
      border: `1px solid ${empty ? '#1f2937' : meta.color}40`,
      borderRadius: 8,
      opacity: empty ? 0.55 : 1,
    }}>
      <div style={{ color: meta.color, fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
        {meta.label}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0', fontVariantNumeric: 'tabular-nums' }}>
            {fmtNumber(skuCount)}
          </div>
          <div style={{ fontSize: 11, color: '#94a3b8' }}>SKU</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#22c55e', fontVariantNumeric: 'tabular-nums' }}>
            ~{fmt(freedCash)}
          </div>
          <div style={{ fontSize: 11, color: '#94a3b8' }}>გათავისუფლდება</div>
        </div>
      </div>
    </div>
  );
}

export default function DeadStock({ deadStock }) {
  const [bucketFilter, setBucketFilter] = useState('all');
  const [actionFilter, setActionFilter] = useState('all');
  const [search, setSearch] = useState('');

  const data = deadStock && typeof deadStock === 'object' ? deadStock : null;
  const empty = !data || data.available === false || !data.summary;

  const summary = data?.summary || {};
  const byAction = data?.by_action || {};
  const topStale = useMemo(
    () => (Array.isArray(data?.top_stale_skus) ? data.top_stale_skus : []),
    [data],
  );

  const bucketData = useMemo(() => {
    const items = [
      {
        bucketKey: 'stale_91_180d',
        bucketLabel: BUCKET_LABELS.stale_91_180d.label,
        color: BUCKET_LABELS.stale_91_180d.color,
        value: Number(summary.stale_91_180d_count) || 0,
      },
      {
        bucketKey: 'stale_181_365d',
        bucketLabel: BUCKET_LABELS.stale_181_365d.label,
        color: BUCKET_LABELS.stale_181_365d.color,
        value: Number(summary.stale_181_365d_count) || 0,
      },
      {
        bucketKey: 'dead_365d_plus',
        bucketLabel: BUCKET_LABELS.dead_365d_plus.label,
        color: BUCKET_LABELS.dead_365d_plus.color,
        value: Number(summary.dead_365d_plus_count) || 0,
      },
      {
        bucketKey: 'unmatched',
        bucketLabel: BUCKET_LABELS.unmatched.label,
        color: BUCKET_LABELS.unmatched.color,
        value: Number(summary.unmatched_count) || 0,
        amount: Number(summary.unmatched_total_amount) || 0,
      },
    ];
    return items.filter((i) => i.value > 0);
  }, [summary]);

  const filteredRows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return topStale.filter((r) => {
      if (bucketFilter !== 'all' && r.stale_bucket !== bucketFilter) return false;
      if (actionFilter !== 'all' && r.recommended_action !== actionFilter) return false;
      if (needle) {
        const name = String(r.product_name || '').toLowerCase();
        const supplier = String(r.top_supplier || '').toLowerCase();
        const code = String(r.product_code || '').toLowerCase();
        if (!name.includes(needle) && !supplier.includes(needle) && !code.includes(needle)) {
          return false;
        }
      }
      return true;
    });
  }, [topStale, bucketFilter, actionFilter, search]);

  if (empty) {
    return (
      <div style={{ padding: 20, color: '#cbd5e1' }}>
        <h2 style={{ margin: 0, marginBottom: 10 }}>💀 Dead Stock</h2>
        <div style={{
          padding: 16,
          background: '#1e293b',
          border: '1px solid #334155',
          borderRadius: 8,
          color: '#fbbf24',
        }}>
          <strong>⚠️ Dead Stock ანალიზი ჯერ არ გვაქვს.</strong>
          <div style={{ marginTop: 6, color: '#cbd5e1', fontSize: 13 }}>
            {data?.reason_ka || 'imported_products ან retail_sales ცარიელია.'}
            {' '}pipeline-ის გადატრიალების შემდეგ ვიჯეტი აქ გამოჩნდება.
          </div>
        </div>
      </div>
    );
  }

  const frozenTotal = Number(summary.frozen_cash_estimate) || 0;
  const importedTotal = Number(summary.imported_total_count) || 0;
  const matchedTotal = Number(summary.matched_total_amount) || 0;
  const unmatchedCount = Number(summary.unmatched_count) || 0;
  const unmatchedPct = importedTotal > 0 ? (unmatchedCount * 100) / importedTotal : 0;
  const showUnmatchedWarning = Boolean(summary.matching_warning) || unmatchedPct >= 30;

  return (
    <div style={{ padding: '12px 4px', color: '#e2e8f0' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 12,
      }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>
          💀 Dead Stock — გაყინული კაპიტალი
        </h2>
        <div style={{ fontSize: 11, color: '#94a3b8' }}>
          Threshold: {summary.days_threshold || 180} დღე · Store: {data.store_filter || 'ჯამი'} · as of {data.as_of_date}
        </div>
      </div>

      {showUnmatchedWarning && (
        <div style={{
          padding: '10px 14px',
          background: 'rgba(234, 179, 8, 0.1)',
          border: '1px solid rgba(234, 179, 8, 0.4)',
          borderRadius: 8,
          color: '#fde68a',
          marginBottom: 14,
          fontSize: 13,
          lineHeight: 1.5,
        }}>
          <strong>⚠️ Barcode/code drift ({unmatchedPct.toFixed(1)}%):</strong>{' '}
          {summary.matching_warning ||
            `${fmtNumber(unmatchedCount)}/${fmtNumber(importedTotal)} SKU ვერ დავამთხვიე retail_sales-ს.`}
          <div style={{ marginTop: 4, fontSize: 12, color: '#fcd34d' }}>
            💡 ციფრი `frozen_cash_estimate` **ზედა შეფასებაა**, არა ზუსტი დიაგნოზი. matched_total_amount = {fmt(matchedTotal)} უფრო საიმედოა.
          </div>
        </div>
      )}

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(260px, 1fr) 2fr',
        gap: 16,
        marginBottom: 16,
      }}>
        <div style={{
          padding: 14,
          background: '#1e293b',
          border: '1px solid #334155',
          borderRadius: 10,
        }}>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 2 }}>💰 ჯამური გაყინული</div>
          <div style={{ fontSize: 26, fontWeight: 700, color: '#fbbf24', fontVariantNumeric: 'tabular-nums' }}>
            ~{fmt(frozenTotal)}
          </div>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 12 }}>
            {showUnmatchedWarning ? '🟡 ზედა შეფასება' : '🟢 ზუსტი შეფასება'}
          </div>
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={bucketData}
                  dataKey="value"
                  nameKey="bucketLabel"
                  innerRadius={45}
                  outerRadius={75}
                  paddingAngle={2}
                >
                  {bucketData.map((b) => (
                    <Cell key={b.bucketKey} fill={b.color} />
                  ))}
                </Pie>
                <Tooltip content={<DonutTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: '#cbd5e1' }}
                  formatter={(v) => <span style={{ color: '#cbd5e1' }}>{v}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
          <ActionCard actionKey="supplier_return" data={byAction.supplier_return} />
          <ActionCard actionKey="discount_15_pct" data={byAction.discount_15_pct} />
          <ActionCard actionKey="discount_30_pct" data={byAction.discount_30_pct} />
          <ActionCard actionKey="write_off" data={byAction.write_off} />
        </div>
      </div>

      <div style={{
        padding: 14,
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: 10,
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 10,
          marginBottom: 10,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>
            🎯 Top SKU-ები ({filteredRows.length})
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <select
              value={bucketFilter}
              onChange={(e) => setBucketFilter(e.target.value)}
              style={{
                background: '#0f172a',
                color: '#e2e8f0',
                border: '1px solid #334155',
                borderRadius: 6,
                padding: '6px 8px',
                fontSize: 12,
              }}
            >
              {BUCKET_SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              style={{
                background: '#0f172a',
                color: '#e2e8f0',
                border: '1px solid #334155',
                borderRadius: 6,
                padding: '6px 8px',
                fontSize: 12,
              }}
            >
              {ACTION_SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="ძიება (სახელი / კოდი / მომწოდებელი)"
              style={{
                background: '#0f172a',
                color: '#e2e8f0',
                border: '1px solid #334155',
                borderRadius: 6,
                padding: '6px 10px',
                fontSize: 12,
                minWidth: 220,
              }}
            />
          </div>
        </div>

        {filteredRows.length === 0 ? (
          <div style={{ padding: 20, color: '#94a3b8', textAlign: 'center', fontSize: 13 }}>
            შესაბამისი SKU ვერ მოვიძიე — გაათვითინე ფილტრი.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ color: '#94a3b8', textAlign: 'left', borderBottom: '1px solid #334155' }}>
                  <th style={{ padding: '6px 8px', fontWeight: 500 }}>პროდუქტი</th>
                  <th style={{ padding: '6px 8px', fontWeight: 500 }}>მომწოდებელი</th>
                  <th style={{ padding: '6px 8px', fontWeight: 500, textAlign: 'right' }}>გაყინული ₾</th>
                  <th style={{ padding: '6px 8px', fontWeight: 500, textAlign: 'right' }}>ქრაფი</th>
                  <th style={{ padding: '6px 8px', fontWeight: 500 }}>Bucket</th>
                  <th style={{ padding: '6px 8px', fontWeight: 500 }}>რეკომენდაცია</th>
                  <th style={{ padding: '6px 8px', fontWeight: 500, textAlign: 'right' }}>~გათავისუფლდება</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((r) => {
                  const bucketMeta = BUCKET_LABELS[r.stale_bucket] || { label: r.stale_bucket, color: '#64748b' };
                  const actionMeta = ACTION_LABELS[r.recommended_action] || { label: r.recommended_action, color: '#94a3b8' };
                  const days = r.days_since_last_sale;
                  return (
                    <tr key={r.product_code + (r.product_name || '')} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '6px 8px', color: '#e2e8f0' }}>
                        <div style={{ fontWeight: 500 }}>{r.product_name || '—'}</div>
                        {r.product_code && (
                          <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>{r.product_code}</div>
                        )}
                      </td>
                      <td style={{ padding: '6px 8px', color: '#cbd5e1' }}>{r.top_supplier || '—'}</td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: '#fbbf24' }}>
                        {fmt(r.imported_amount)}
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#94a3b8' }}>
                        {days != null ? `${fmtNumber(days)} დღე` : '—'}
                      </td>
                      <td style={{ padding: '6px 8px' }}>
                        <span style={{ color: bucketMeta.color, fontSize: 11, fontWeight: 600 }}>
                          {bucketMeta.label}
                        </span>
                      </td>
                      <td style={{ padding: '6px 8px' }}>
                        <span style={{ color: actionMeta.color, fontSize: 11, fontWeight: 600 }}>
                          {actionMeta.label}
                        </span>
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#22c55e' }}>
                        {fmt(r.expected_freed_cash)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div style={{ marginTop: 10, fontSize: 10, color: '#64748b' }}>
          წყარო: data.json · analyze_dead_stock (imported_products × retail_sales triangulation) · threshold 180 დღე
        </div>
      </div>

      {Array.isArray(data?.notes) && data.notes.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 11, color: '#94a3b8' }}>
          {data.notes.map((note, i) => (
            <div key={i} style={{ marginBottom: 2 }}>ⓘ {note}</div>
          ))}
        </div>
      )}
    </div>
  );
}
