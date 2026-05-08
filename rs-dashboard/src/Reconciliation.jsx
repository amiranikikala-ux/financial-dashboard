import { Fragment, useMemo, useState } from 'react';

const formatGel = (v) => {
  const n = Number(v) || 0;
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + ' ₾';
};

const formatGelShort = (v) => {
  const n = Number(v) || 0;
  if (Math.abs(n) >= 1000) return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n) + ' ₾';
  return formatGel(n);
};

function Card({ title, value, hint, color = '#e2e8f0', accent = '#3b82f6' }) {
  return (
    <div style={{
      background: '#0f172a', border: `1px solid ${accent}`, borderRadius: 8,
      padding: 16, minHeight: 110, display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
    }}>
      <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
      {hint && <div style={{ fontSize: 12, color: '#64748b', marginTop: 6 }}>{hint}</div>}
    </div>
  );
}

const STATUS_LABEL = {
  match: { label: '✅ ემთხვევა', color: '#22c55e' },
  over_invoice: { label: '🔴 ფაქტურა მეტია', color: '#ef4444' },
  over_waybill: { label: '🔵 ზედნადები მეტია', color: '#3b82f6' },
};

const FILTERS = [
  { key: 'all', label: 'ყველა' },
  { key: 'flagged', label: '🔴 + 🔵 (სხვაობით)' },
  { key: 'match', label: '✅ ემთხვევა' },
  { key: 'over_invoice', label: '🔴 ფაქტურა მეტია' },
  { key: 'over_waybill', label: '🔵 ზედნადები მეტია' },
  { key: 'missing', label: '👻 ცხრილში არ ჩანს' },
];

function buildMonthlyBreakdown(supplierInvoices, waybillLines) {
  const months = {};
  const ensure = (ym) => {
    if (!months[ym]) months[ym] = { invoice: 0, waybill: 0, inv_count: 0, wb_count: 0 };
    return months[ym];
  };
  for (const inv of supplierInvoices || []) {
    const date = (inv.date_op || inv.date_issued || '').slice(0, 7);
    if (!date) continue;
    const m = ensure(date);
    m.invoice += Number(inv.amount || 0);
    m.inv_count += 1;
  }
  for (const wb of waybillLines || []) {
    const date = (wb.date || '').slice(0, 7);
    if (!date) continue;
    const m = ensure(date);
    m.waybill += Number(wb.amount || 0);
    if (!wb.is_return) m.wb_count += 1;
  }
  return Object.entries(months)
    .map(([ym, v]) => ({
      month: ym,
      invoice: v.invoice,
      waybill: v.waybill,
      gap: v.invoice - v.waybill,
      inv_count: v.inv_count,
      wb_count: v.wb_count,
    }))
    .sort((a, b) => b.month.localeCompare(a.month));
}

export default function Reconciliation({ data }) {
  const bundle = data?.supplier_reconciliation || { rows: [], summary: {} };
  const rows = bundle.rows || [];
  const summary = bundle.summary || {};
  const supplierInvoices = data?.supplier_invoices || {};
  const waybillLines = data?.supplier_waybill_lines || {};

  const [filter, setFilter] = useState('flagged');
  const [search, setSearch] = useState('');
  const [expandedTid, setExpandedTid] = useState(null);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (filter === 'flagged' && r.status === 'match') return false;
      if (filter === 'match' && r.status !== 'match') return false;
      if (filter === 'over_invoice' && r.status !== 'over_invoice') return false;
      if (filter === 'over_waybill' && r.status !== 'over_waybill') return false;
      if (filter === 'missing' && r.in_suppliers_table) return false;
      if (q) {
        const hay = ((r.name || '') + ' ' + (r.tax_id || '')).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [rows, filter, search]);

  return (
    <div style={{ padding: 16, color: '#e2e8f0' }}>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 22, color: '#f1f5f9' }}>
          ფაქტურა ↔ ზედნადები რეკონცილიაცია
        </h2>
        <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 4 }}>
          ყოველ მომწოდებელზე — ჯამური ფაქტურა vs ჯამური ზედნადები (ყველა დრო).
          ზღვარი: 100 ₾.
        </div>
      </div>

      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: 12, marginBottom: 16,
      }}>
        <Card title="სულ მომწოდებელი" value={summary.total_suppliers ?? 0} accent="#64748b" />
        <Card title="✅ ემთხვევა" value={summary.match_count ?? 0}
              hint={`< ${summary.match_threshold_ge ?? 100} ₾ სხვაობა`}
              accent="#22c55e" color="#86efac" />
        <Card title="🔴 ფაქტურა მეტია" value={summary.over_invoice_count ?? 0}
              hint="ფაქტურა > ზედნადები"
              accent="#ef4444" color="#fca5a5" />
        <Card title="🔵 ზედნადები მეტია" value={summary.over_waybill_count ?? 0}
              hint="ზედნადები > ფაქტურა"
              accent="#3b82f6" color="#93c5fd" />
        <Card title="👻 ცხრილში არ ჩანს" value={summary.missing_from_suppliers_count ?? 0}
              hint="მომსახურება/იჯარა/შიდა"
              accent="#a855f7" color="#d8b4fe" />
      </div>

      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 12, marginBottom: 16,
      }}>
        <Card title="ფაქტურა ჯამში" value={formatGelShort(summary.total_invoice_ge)} accent="#475569" />
        <Card title="ზედნადები ჯამში" value={formatGelShort(summary.total_waybill_ge)} accent="#475569" />
        <Card title="სხვაობა"
              value={formatGelShort(summary.total_gap_ge)}
              hint="ფაქტურა − ზედნადები"
              accent={(summary.total_gap_ge ?? 0) >= 0 ? '#ef4444' : '#3b82f6'}
              color={(summary.total_gap_ge ?? 0) >= 0 ? '#fca5a5' : '#93c5fd'} />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        {FILTERS.map((f) => (
          <button key={f.key} onClick={() => setFilter(f.key)}
            style={{
              padding: '6px 12px', borderRadius: 6,
              border: '1px solid ' + (filter === f.key ? '#3b82f6' : '#334155'),
              background: filter === f.key ? '#1e3a8a' : '#0f172a',
              color: '#e2e8f0', cursor: 'pointer', fontSize: 13,
            }}>
            {f.label}
          </button>
        ))}
        <input
          type="text" placeholder="ფირმის სახელი ან საიდ. ნომერი..."
          value={search} onChange={(e) => setSearch(e.target.value)}
          style={{
            marginLeft: 'auto', padding: '6px 10px', borderRadius: 6,
            border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0',
            fontSize: 13, minWidth: 240,
          }}
        />
      </div>

      <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 8 }}>
        ნაჩვენებია {filtered.length} / {rows.length} მომწოდებელი
      </div>

      <div style={{ overflowX: 'auto', border: '1px solid #334155', borderRadius: 8 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#1e293b', color: '#cbd5e1' }}>
              <th style={{ padding: 10, textAlign: 'left' }}>#</th>
              <th style={{ padding: 10, textAlign: 'left' }}>მომწოდებელი</th>
              <th style={{ padding: 10, textAlign: 'right' }}>ფაქტურა</th>
              <th style={{ padding: 10, textAlign: 'right' }}>ც.</th>
              <th style={{ padding: 10, textAlign: 'right' }}>ზედნადები</th>
              <th style={{ padding: 10, textAlign: 'right' }}>ც.</th>
              <th style={{ padding: 10, textAlign: 'right' }}>სხვაობა</th>
              <th style={{ padding: 10, textAlign: 'right' }}>ratio</th>
              <th style={{ padding: 10, textAlign: 'left' }}>სტატუსი</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => {
              const status = STATUS_LABEL[r.status] || { label: r.status, color: '#94a3b8' };
              const isExpanded = expandedTid === r.tax_id;
              const monthly = isExpanded
                ? buildMonthlyBreakdown(supplierInvoices[r.tax_id], waybillLines[r.tax_id])
                : null;
              return (
                <Fragment key={r.tax_id}>
                <tr onClick={() => setExpandedTid(isExpanded ? null : r.tax_id)}
                    style={{
                      borderTop: '1px solid #1e293b',
                      background: isExpanded ? '#1e293b' : (i % 2 === 0 ? '#0f172a' : '#0b1220'),
                      opacity: r.in_suppliers_table ? 1 : 0.75,
                      cursor: 'pointer',
                    }}>
                  <td style={{ padding: 8, color: '#64748b' }}>
                    <span style={{ display: 'inline-block', width: 14, color: '#3b82f6' }}>
                      {isExpanded ? '▼' : '▶'}
                    </span>
                    {i + 1}
                  </td>
                  <td style={{ padding: 8 }}>
                    {r.name || (
                      <span style={{ color: '#a855f7', fontStyle: 'italic' }}>
                        ({r.tax_id}) ცხრილში არ ჩანს
                      </span>
                    )}
                  </td>
                  <td style={{ padding: 8, textAlign: 'right', fontFamily: 'monospace' }}>
                    {formatGelShort(r.invoice_total)}
                  </td>
                  <td style={{ padding: 8, textAlign: 'right', color: '#64748b' }}>{r.invoice_count}</td>
                  <td style={{ padding: 8, textAlign: 'right', fontFamily: 'monospace' }}>
                    {formatGelShort(r.waybill_total)}
                  </td>
                  <td style={{ padding: 8, textAlign: 'right', color: '#64748b' }}>{r.waybill_count}</td>
                  <td style={{
                    padding: 8, textAlign: 'right', fontFamily: 'monospace', fontWeight: 600,
                    color: r.status === 'match' ? '#94a3b8' : status.color,
                  }}>
                    {formatGelShort(r.gap)}
                  </td>
                  <td style={{ padding: 8, textAlign: 'right', color: '#94a3b8', fontFamily: 'monospace' }}>
                    {r.ratio == null ? '—' : r.ratio.toFixed(2) + '×'}
                  </td>
                  <td style={{ padding: 8, color: status.color }}>{status.label}</td>
                </tr>
                {isExpanded && (
                  <tr style={{ background: '#0b1220' }}>
                    <td colSpan={9} style={{ padding: 12 }}>
                      <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 8 }}>
                        თვეების მიხედვით — {r.name || `(${r.tax_id})`}
                      </div>
                      {monthly && monthly.length > 0 ? (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                          <thead>
                            <tr style={{ color: '#94a3b8' }}>
                              <th style={{ padding: 6, textAlign: 'left' }}>თვე</th>
                              <th style={{ padding: 6, textAlign: 'right' }}>ფაქტურა</th>
                              <th style={{ padding: 6, textAlign: 'right' }}>ც.</th>
                              <th style={{ padding: 6, textAlign: 'right' }}>ზედნადები</th>
                              <th style={{ padding: 6, textAlign: 'right' }}>ც.</th>
                              <th style={{ padding: 6, textAlign: 'right' }}>სხვაობა</th>
                              <th style={{ padding: 6, textAlign: 'right' }}>ratio</th>
                            </tr>
                          </thead>
                          <tbody>
                            {monthly.map((m) => {
                              const mRatio = m.waybill > 0 ? m.invoice / m.waybill : null;
                              const mStatus = Math.abs(m.gap) < 100 ? 'match'
                                : m.gap > 0 ? 'over_invoice' : 'over_waybill';
                              const mColor = mStatus === 'match' ? '#94a3b8'
                                : mStatus === 'over_invoice' ? '#fca5a5' : '#93c5fd';
                              return (
                                <tr key={m.month} style={{ borderTop: '1px solid #1e293b' }}>
                                  <td style={{ padding: 6 }}>{m.month}</td>
                                  <td style={{ padding: 6, textAlign: 'right', fontFamily: 'monospace' }}>
                                    {formatGelShort(m.invoice)}
                                  </td>
                                  <td style={{ padding: 6, textAlign: 'right', color: '#64748b' }}>
                                    {m.inv_count || '—'}
                                  </td>
                                  <td style={{ padding: 6, textAlign: 'right', fontFamily: 'monospace' }}>
                                    {formatGelShort(m.waybill)}
                                  </td>
                                  <td style={{ padding: 6, textAlign: 'right', color: '#64748b' }}>
                                    {m.wb_count || '—'}
                                  </td>
                                  <td style={{
                                    padding: 6, textAlign: 'right', fontFamily: 'monospace',
                                    color: mColor, fontWeight: 600,
                                  }}>
                                    {formatGelShort(m.gap)}
                                  </td>
                                  <td style={{ padding: 6, textAlign: 'right', color: '#94a3b8', fontFamily: 'monospace' }}>
                                    {mRatio == null ? '—' : mRatio.toFixed(2) + '×'}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      ) : (
                        <div style={{ color: '#64748b', fontSize: 13 }}>
                          ამ მომწოდებელზე დეტალური მონაცემი არ არის (შესაძლოა ფაქტურები ცარიელია ან ფაილი არ არსებობს).
                        </div>
                      )}
                    </td>
                  </tr>
                )}
                </Fragment>
              );
            })}
            {filtered.length === 0 && (
              <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>
                შედეგი არ არის — ცადე სხვა ფილტრი.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 16, fontSize: 12, color: '#64748b', lineHeight: 1.6 }}>
        <div><strong style={{ color: '#cbd5e1' }}>როგორ ვკითხულობ:</strong></div>
        <div>• <strong>✅ ემთხვევა</strong> — ფაქტურა და ზედნადები ერთნაირია (≤ 100 ₾ ცდომილება).</div>
        <div>• <strong>🔴 ფაქტურა მეტია</strong> — ფაქტურის თანხა აღემატება ზედნადებების ჯამს. ხშირი მიზეზი: მომსახურება ფაქტურაშია, ზედნადებზე არ არის (მაგ. ფუდმარტი).</div>
        <div>• <strong>🔵 ზედნადები მეტია</strong> — ზედნადები არსებობს, ფაქტურა ჯერ არ გამოწერილა (timing).</div>
        <div>• <strong>👻 ცხრილში არ ჩანს</strong> — ფაქტურა გვაქვს, მაგრამ მომწოდებელთა მთავარ ცხრილში არ მონაწილეობს (იჯარა, შიდა გადატანა, მცირე მომსახურება).</div>
      </div>
    </div>
  );
}
