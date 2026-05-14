import { useEffect, useMemo, useState } from 'react';
import { fetchApiJson } from './lib/api.js';

const GEL = new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL', maximumFractionDigits: 0 });
const fmtGel = (v) => GEL.format(Number(v) || 0);
const fmtGel2 = (v) => {
  const n = Number(v) || 0;
  return `${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₾`;
};
const fmtN = (v) => new Intl.NumberFormat('ka-GE').format(Number(v) || 0);
const fmtPct = (v) => {
  const n = Number(v) || 0;
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(1)}%`;
};
const fmtDayKa = (d) => {
  if (!d) return '—';
  const s = String(d).slice(0, 10);
  const parts = s.split('-');
  if (parts.length !== 3) return s;
  const months = ['იან', 'თებ', 'მარ', 'აპრ', 'მაი', 'ივნ', 'ივლ', 'აგვ', 'სექ', 'ოქტ', 'ნოე', 'დეკ'];
  const m = parseInt(parts[1], 10) - 1;
  return `${parseInt(parts[2], 10)} ${months[m] || ''} ${parts[0]}`;
};

function BankExpandableRow({ bankName, breakdown, expanded, onToggle, cashback }) {
  const fmt = (v) => `${(Number(v) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₾`;
  const b = breakdown || {};
  const cb = Number(cashback) || 0;
  const total = (b.total || 0) + cb;
  return (
    <div style={{ padding: '4px 0' }}>
      <div
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', cursor: 'pointer', userSelect: 'none' }}
      >
        <span style={{ color: '#cbd5e1', fontSize: '0.95rem', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#64748b', fontSize: '0.75rem', display: 'inline-block', width: 10, transition: 'transform 0.15s ease', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
          {bankName} ბანკი
        </span>
        <span style={{ color: '#e2e8f0', fontSize: '0.95rem', fontWeight: 600 }}>{fmt(total)}</span>
      </div>
      {expanded && (
        <div style={{ marginTop: 8, marginLeft: 16, paddingLeft: 12, borderLeft: '2px solid rgba(255,255,255,0.08)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '0.88rem' }}>
            <span style={{ color: '#94a3b8' }}>ბარათით გადახდა</span>
            <span style={{ color: '#cbd5e1' }}>{fmt(b.pos)}</span>
          </div>
          {(b.pos_gross > 0 || b.pos_fee > 0) && (() => {
            const perTxNet = (b.pos_gross || 0) - (b.pos_fee || 0);
            const lump = Math.max(0, (b.pos || 0) - perTxNet);
            return (
              <div style={{ marginLeft: 12, paddingLeft: 8, borderLeft: '1px dashed rgba(255,255,255,0.06)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: '0.82rem' }}>
                  <span style={{ color: '#64748b' }}>ბარათით გადახდილი (გროსი)</span>
                  <span style={{ color: '#94a3b8' }}>{fmt(b.pos_gross)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: '0.82rem' }}>
                  <span style={{ color: '#64748b' }}>ბანკის საკომისიო</span>
                  <span style={{ color: '#f87171' }}>−{fmt(b.pos_fee)}</span>
                </div>
                {lump > 1 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: '0.82rem' }}>
                    <span style={{ color: '#64748b' }}>Wallet/ერთიანი swap</span>
                    <span style={{ color: '#94a3b8' }}>{fmt(lump)}</span>
                  </div>
                )}
              </div>
            );
          })()}
          {b.cash_deposit > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '0.88rem' }}>
              <span style={{ color: '#94a3b8' }}>ნავაჭრის ჩარიცხვა (ნაღდი)</span>
              <span style={{ color: '#cbd5e1' }}>{fmt(b.cash_deposit)}</span>
            </div>
          )}
          {b.samurneo > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '0.88rem' }}>
              <span style={{ color: '#94a3b8' }}>სამეურნეო ხარჯიდან</span>
              <span style={{ color: '#cbd5e1' }}>{fmt(b.samurneo)}</span>
            </div>
          )}
          {b.other_total > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '0.88rem' }}>
              <span style={{ color: '#94a3b8' }}>სხვა</span>
              <span style={{ color: '#cbd5e1' }}>{fmt(b.other_total)}</span>
            </div>
          )}
          {cb > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '0.88rem' }}>
              <span style={{ color: '#94a3b8' }}>ფუდმარტი ქეშბექი</span>
              <span style={{ color: '#cbd5e1' }}>{fmt(cb)}</span>
            </div>
          )}
          {b.samurneo === 0 && b.other_total === 0 && !(b.cash_deposit > 0) && cb === 0 && (
            <div style={{ color: '#64748b', fontSize: '0.82rem', padding: '4px 0', fontStyle: 'italic' }}>
              ამ პერიოდში მხოლოდ ბარათით გადახდაა
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OutItemsExpandableRow({ label, amount, items, expanded, onToggle, expandedNote }) {
  const fmt = (v) => `${(Number(v) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₾`;
  const safe = Array.isArray(items) ? items : [];
  // Group by partner+bank for cleaner display
  const grouped = {};
  safe.forEach((it) => {
    const key = `${it.partner || it.tax_id || '—'}|${it.bank || ''}`;
    if (!grouped[key]) grouped[key] = { partner: it.partner || it.tax_id || '—', bank: it.bank || '', count: 0, sum: 0, purposes: new Set() };
    grouped[key].count += 1;
    grouped[key].sum += Number(it.amount) || 0;
    if (it.purpose) grouped[key].purposes.add(String(it.purpose).slice(0, 80));
  });
  const rows = Object.values(grouped).sort((a, b) => b.sum - a.sum);
  return (
    <div style={{ padding: '4px 0' }}>
      <div
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', cursor: 'pointer', userSelect: 'none' }}
      >
        <span style={{ color: '#cbd5e1', fontSize: '0.92rem', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#64748b', fontSize: '0.75rem', display: 'inline-block', width: 10, transition: 'transform 0.15s ease', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
          {label}
          {safe.length > 0 && <span style={{ color: '#64748b', fontSize: '0.78rem' }}>({safe.length})</span>}
        </span>
        <span style={{ color: '#e2e8f0', fontSize: '0.92rem', fontWeight: 500 }}>{fmt(amount)}</span>
      </div>
      {expanded && expandedNote && (
        <div style={{ marginTop: 8, marginLeft: 16, padding: '8px 10px', background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.2)', borderRadius: 6, color: '#fbbf24', fontSize: '0.82rem', lineHeight: 1.5 }}>
          {expandedNote}
        </div>
      )}
      {expanded && rows.length > 0 && (
        <div style={{ marginTop: 8, marginLeft: 16, overflowX: 'auto', maxHeight: 280, overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', minWidth: 300 }}>
            <thead>
              <tr style={{ color: '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                <th style={{ textAlign: 'left', padding: '5px 6px', fontWeight: 500 }}>ვინ</th>
                <th style={{ textAlign: 'left', padding: '5px 6px', fontWeight: 500 }}>ბანკი</th>
                <th style={{ textAlign: 'right', padding: '5px 6px', fontWeight: 500 }}>თანხა</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', color: '#e2e8f0' }}>
                  <td style={{ padding: '5px 6px', textAlign: 'left' }}>
                    {r.partner}{r.count > 1 ? <span style={{ color: '#64748b', fontSize: '0.75rem' }}> ×{r.count}</span> : null}
                  </td>
                  <td style={{ padding: '5px 6px', textAlign: 'left' }}>
                    {r.bank === 'TBC' && <span style={{ background: 'rgba(59,130,246,0.18)', color: '#60a5fa', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem' }}>TBC</span>}
                    {r.bank === 'BOG' && <span style={{ background: 'rgba(249,115,22,0.18)', color: '#fb923c', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem' }}>BOG</span>}
                  </td>
                  <td style={{ padding: '5px 6px', textAlign: 'right', color: '#cbd5e1' }}>{fmt(r.sum)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function OutBankExpandableRow({ bankName, breakdown, expanded, onToggle }) {
  const fmt = (v) => `${(Number(v) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₾`;
  const b = breakdown || {};
  const total = b.total || 0;
  return (
    <div style={{ padding: '4px 0' }}>
      <div
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', cursor: 'pointer', userSelect: 'none' }}
      >
        <span style={{ color: '#cbd5e1', fontSize: '0.95rem', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#64748b', fontSize: '0.75rem', display: 'inline-block', width: 10, transition: 'transform 0.15s ease', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
          {bankName} ბანკი
        </span>
        <span style={{ color: '#e2e8f0', fontSize: '0.95rem', fontWeight: 600 }}>{fmt(total)}</span>
      </div>
      {expanded && (
        <div style={{ marginTop: 8, marginLeft: 16, paddingLeft: 12, borderLeft: '2px solid rgba(255,255,255,0.08)' }}>
          {b.suppliers > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '0.88rem' }}>
              <span style={{ color: '#94a3b8' }}>მომწოდებლები</span>
              <span style={{ color: '#cbd5e1' }}>{fmt(b.suppliers)}</span>
            </div>
          )}
          {b.tax_treasury > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '0.88rem' }}>
              <span style={{ color: '#94a3b8' }}>გადასახადი / ხაზინა</span>
              <span style={{ color: '#cbd5e1' }}>{fmt(b.tax_treasury)}</span>
            </div>
          )}
          {b.bank_fees > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '0.88rem' }}>
              <span style={{ color: '#94a3b8' }}>ბანკის საკომისიო</span>
              <span style={{ color: '#cbd5e1' }}>{fmt(b.bank_fees)}</span>
            </div>
          )}
          {b.other_total > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '0.88rem' }}>
              <span style={{ color: '#94a3b8' }}>სხვა</span>
              <span style={{ color: '#cbd5e1' }}>{fmt(b.other_total)}</span>
            </div>
          )}
          {total === 0 && (
            <div style={{ color: '#64748b', fontSize: '0.82rem', padding: '4px 0', fontStyle: 'italic' }}>
              ამ პერიოდში ამ ბანკიდან გასვლა არ მომხდარა
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PosExpandableRow({ label, amount, lines, expanded, onToggle }) {
  const fmt = (v) => `${(Number(v) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₾`;
  const safeLines = Array.isArray(lines) ? lines : [];
  const visible = safeLines.slice(0, 300);
  return (
    <div style={{ padding: '4px 0' }}>
      <div
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', cursor: 'pointer', userSelect: 'none' }}
      >
        <span style={{ color: '#94a3b8', fontSize: '0.92rem', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#64748b', fontSize: '0.75rem', display: 'inline-block', width: 10, transition: 'transform 0.15s ease', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
          {label}
          <span style={{ color: '#64748b', fontSize: '0.75rem' }}>({safeLines.length} ჩეკი)</span>
        </span>
        <span style={{ color: '#cbd5e1', fontSize: '0.92rem', fontWeight: 500 }}>{fmt(amount)}</span>
      </div>
      {expanded && safeLines.length > 0 && (
        <div style={{ marginTop: 8, maxHeight: 320, overflowY: 'auto', overflowX: 'auto', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 6 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', minWidth: 280 }}>
            <thead>
              <tr style={{ color: '#94a3b8' }}>
                <th style={{ textAlign: 'left', padding: '4px 6px', fontWeight: 500 }}>დრო</th>
                <th style={{ textAlign: 'left', padding: '4px 6px', fontWeight: 500 }}>ბარათი</th>
                <th style={{ textAlign: 'right', padding: '4px 6px', fontWeight: 500 }}>თანხა</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((l, i) => (
                <tr key={i} style={{ color: '#cbd5e1', borderTop: '1px solid rgba(255,255,255,0.03)' }}>
                  <td style={{ padding: '3px 6px', textAlign: 'left', color: '#94a3b8' }}>{l.time || '—'}</td>
                  <td style={{ padding: '3px 6px', textAlign: 'left', color: '#94a3b8' }}>{l.card_brand || '—'}</td>
                  <td style={{ padding: '3px 6px', textAlign: 'right', fontWeight: 500 }}>{fmt(l.amount)}</td>
                </tr>
              ))}
              {safeLines.length > visible.length && (
                <tr><td colSpan={3} style={{ padding: '6px', textAlign: 'center', color: '#94a3b8' }}>+ {safeLines.length - visible.length} მეტი ხაზი</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ProfitExpenseRow({ label, amount, items, expanded, onToggle, note, yellow }) {
  const fmt = (v) => `${(Number(v) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₾`;
  const safe = Array.isArray(items) ? items : [];
  // Group by partner+bank for cleaner display
  const grouped = {};
  safe.forEach((it) => {
    const key = `${it.partner || it.tax_id || '—'}|${it.bank || ''}`;
    if (!grouped[key]) grouped[key] = { partner: it.partner || it.tax_id || '—', bank: it.bank || '', count: 0, sum: 0 };
    grouped[key].count += 1;
    grouped[key].sum += Number(it.amount) || 0;
  });
  const rows = Object.values(grouped).sort((a, b) => b.sum - a.sum);
  const hasDetail = rows.length > 0;
  const labelColor = yellow ? '#fbbf24' : '#cbd5e1';
  return (
    <div style={{ padding: '4px 0' }}>
      <div
        onClick={hasDetail ? onToggle : undefined}
        role={hasDetail ? 'button' : undefined}
        tabIndex={hasDetail ? 0 : undefined}
        onKeyDown={hasDetail ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } } : undefined}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', cursor: hasDetail ? 'pointer' : 'default', userSelect: 'none', color: labelColor }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {hasDetail && (
            <span style={{ color: '#64748b', fontSize: '0.7rem', display: 'inline-block', width: 10, transition: 'transform 0.15s ease', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
          )}
          {label}
        </span>
        <span>−{fmt(amount)}</span>
      </div>
      {expanded && note && (
        <div style={{ marginTop: 6, marginLeft: 16, padding: '8px 10px', background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.2)', borderRadius: 6, color: '#fbbf24', fontSize: '0.82rem', lineHeight: 1.5 }}>
          {note}
        </div>
      )}
      {expanded && hasDetail && (
        <div style={{ marginTop: 6, marginLeft: 16, overflowX: 'auto', maxHeight: 260, overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', minWidth: 280 }}>
            <thead>
              <tr style={{ color: '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                <th style={{ textAlign: 'left', padding: '5px 6px', fontWeight: 500 }}>ვის</th>
                <th style={{ textAlign: 'left', padding: '5px 6px', fontWeight: 500 }}>ბანკი</th>
                <th style={{ textAlign: 'right', padding: '5px 6px', fontWeight: 500 }}>თანხა</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', color: '#e2e8f0' }}>
                  <td style={{ padding: '5px 6px', textAlign: 'left' }}>
                    {r.partner}{r.count > 1 ? <span style={{ color: '#64748b', fontSize: '0.75rem' }}> ×{r.count}</span> : null}
                  </td>
                  <td style={{ padding: '5px 6px', textAlign: 'left' }}>
                    {r.bank === 'TBC' && <span style={{ background: 'rgba(59,130,246,0.18)', color: '#60a5fa', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem' }}>TBC</span>}
                    {r.bank === 'BOG' && <span style={{ background: 'rgba(249,115,22,0.18)', color: '#fb923c', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem' }}>BOG</span>}
                    {r.bank === 'ნაღდი' && <span style={{ background: 'rgba(251,191,36,0.18)', color: '#fbbf24', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem' }}>💵 ნაღდი</span>}
                  </td>
                  <td style={{ padding: '5px 6px', textAlign: 'right', color: '#cbd5e1' }}>−{fmt(r.sum)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CashTillRow({ label, amount, negative, expanded, onToggle, children, valueColor, indent }) {
  const fmt = (v) => `${(Number(v) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₾`;
  const hasDetail = !!children;
  const color = valueColor || (negative ? '#94a3b8' : '#cbd5e1');
  return (
    <div>
      <div
        onClick={hasDetail ? onToggle : undefined}
        role={hasDetail ? 'button' : undefined}
        tabIndex={hasDetail ? 0 : undefined}
        onKeyDown={hasDetail ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } } : undefined}
        style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', color, fontSize: '0.92rem', cursor: hasDetail ? 'pointer' : 'default', userSelect: 'none', alignItems: 'baseline' }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {hasDetail && (
            <span style={{ color: '#64748b', fontSize: '0.7rem', display: 'inline-block', width: 10, transition: 'transform 0.15s ease', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
          )}
          <span>{label}</span>
        </span>
        <span>{negative ? '−' : ''}{fmt(amount)}</span>
      </div>
      {expanded && hasDetail && (
        <div style={{ marginTop: 4, marginBottom: 6, marginLeft: indent ?? 16, overflowX: 'auto', maxHeight: 240, overflowY: 'auto' }}>
          {children}
        </div>
      )}
    </div>
  );
}

function bankBadge(bank) {
  if (bank === 'TBC') return <span style={{ background: 'rgba(59,130,246,0.18)', color: '#60a5fa', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem' }}>TBC</span>;
  if (bank === 'BOG') return <span style={{ background: 'rgba(249,115,22,0.18)', color: '#fb923c', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem' }}>BOG</span>;
  return <span>{bank}</span>;
}

function FlowRow({ label, value, hint, bold, danger, size }) {
  const fontSize = size === 'small' ? '0.85rem' : '0.92rem';
  const color = danger ? '#ef4444' : (bold ? '#f1f5f9' : '#cbd5e1');
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '4px 0', borderTop: bold ? '1px solid rgba(255,255,255,0.1)' : 'none', marginTop: bold ? 8 : 0, paddingTop: bold ? 8 : 4 }}>
      <span style={{ color: '#94a3b8', fontSize, fontWeight: bold ? 600 : 400 }}>
        {label}
        {hint && <span style={{ color: '#64748b', fontSize: '0.75rem', marginLeft: 6 }}>({hint})</span>}
      </span>
      <span style={{ color, fontSize, fontWeight: bold ? 700 : 500 }}>
        {`${(Number(value) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₾`}
      </span>
    </div>
  );
}

// "Last complete day" — the most recent day where both stores' hour coverage
// extends to 22:00 or later. MegaPlus backup ZIPs are taken mid-day, so the
// latest day in the data is always partial; the day before is the last full one.
function lastCompleteDay(retailSales) {
  const chb = Array.isArray(retailSales?.cashier_hour_breakdown) ? retailSales.cashier_hour_breakdown : [];
  const cdb = Array.isArray(retailSales?.cashier_day_breakdown) ? retailSales.cashier_day_breakdown : [];
  if (chb.length === 0 && cdb.length === 0) return '';

  // Per-day per-store max hour
  const maxHourByDayStore = new Map(); // day -> Map(store -> maxHour)
  chb.forEach((r) => {
    const d = (r.day || '').slice(0, 10);
    const obj = r.object || '—';
    const h = Number(r.hour) || 0;
    if (!d) return;
    if (!maxHourByDayStore.has(d)) maxHourByDayStore.set(d, new Map());
    const m = maxHourByDayStore.get(d);
    if (!m.has(obj) || h > m.get(obj)) m.set(obj, h);
  });

  const allDays = Array.from(new Set(cdb.map((r) => (r.day || '').slice(0, 10)).filter(Boolean))).sort();
  // walk back to find latest day where every store with data reaches hour >= 22
  for (let i = allDays.length - 1; i >= 0; i -= 1) {
    const d = allDays[i];
    const storesOnDay = maxHourByDayStore.get(d);
    if (!storesOnDay) continue;
    let complete = true;
    storesOnDay.forEach((maxH) => {
      if (maxH < 22) complete = false;
    });
    if (complete) return d;
  }
  // No complete day found — fall back to latest available
  return allDays[allDays.length - 1] || '';
}

function previousDay(yyyyMmDd) {
  if (!yyyyMmDd || yyyyMmDd.length < 10) return '';
  const [y, m, d] = yyyyMmDd.slice(0, 10).split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() - 1);
  const yy = dt.getUTCFullYear();
  const mm = String(dt.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(dt.getUTCDate()).padStart(2, '0');
  return `${yy}-${mm}-${dd}`;
}

function KpiCard({ icon, label, value, sub, color, placeholder }) {
  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 12,
        padding: '20px 22px',
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        minHeight: 96,
        borderBottom: color ? `3px solid ${color}` : '1px solid rgba(255,255,255,0.08)',
      }}
    >
      <div style={{ fontSize: '2rem', lineHeight: 1, opacity: placeholder ? 0.45 : 1 }}>{icon}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '0.78rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 4 }}>
          {label}
        </div>
        <div
          style={{
            fontSize: placeholder ? '0.95rem' : '1.55rem',
            fontWeight: 700,
            color: placeholder ? '#94a3b8' : (color || '#f1f5f9'),
            fontStyle: placeholder ? 'italic' : 'normal',
            lineHeight: 1.15,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {value}
        </div>
        {sub && (
          <div style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: 4 }}>{sub}</div>
        )}
      </div>
    </div>
  );
}

export default function Home({ retailSales, fromDate, fromTime, toDate, toTime, reloadKey }) {
  const todayDay = useMemo(() => lastCompleteDay(retailSales), [retailSales]);
  const yesterdayDay = useMemo(() => previousDay(todayDay), [todayDay]);
  const periodActive = !!(fromDate || toDate);
  const periodFrom = periodActive ? (fromDate || toDate).slice(0, 10) : '';
  const periodTo = periodActive ? (toDate || fromDate).slice(0, 10) : '';

  const dailyTrend = useMemo(
    () => (Array.isArray(retailSales?.daily_trend) ? retailSales.daily_trend : []),
    [retailSales],
  );
  const cashierDays = useMemo(
    () => (Array.isArray(retailSales?.cashier_day_breakdown) ? retailSales.cashier_day_breakdown : []),
    [retailSales],
  );

  const todayTrend = useMemo(
    () => dailyTrend.find((r) => (r.day || '').slice(0, 10) === todayDay) || null,
    [dailyTrend, todayDay],
  );
  const yesterdayTrend = useMemo(
    () => dailyTrend.find((r) => (r.day || '').slice(0, 10) === yesterdayDay) || null,
    [dailyTrend, yesterdayDay],
  );

  const todayRevenue = Number(todayTrend?.revenue_ge) || 0;
  const todayProfit = Number(todayTrend?.profit_ge) || 0;
  const yestRevenue = Number(yesterdayTrend?.revenue_ge) || 0;
  const yestProfit = Number(yesterdayTrend?.profit_ge) || 0;
  const deltaRevenuePct = yestRevenue > 0 ? ((todayRevenue - yestRevenue) / yestRevenue) * 100 : null;
  const deltaProfitPct = yestProfit > 0 ? ((todayProfit - yestProfit) / yestProfit) * 100 : null;

  // Stores table — Today rows
  const storeRowsToday = useMemo(() => {
    const today = cashierDays.filter((r) => (r.day || '').slice(0, 10) === todayDay);
    const byObj = new Map();
    today.forEach((r) => {
      const obj = r.object || '—';
      if (!byObj.has(obj)) {
        byObj.set(obj, { object: obj, cash: 0, card: 0, revenue: 0, receipts: 0 });
      }
      const acc = byObj.get(obj);
      acc.cash += Number(r.cash) || 0;
      acc.card += Number(r.card) || 0;
      acc.revenue += Number(r.revenue) || 0;
      acc.receipts += Number(r.receipts) || 0;
    });
    const rows = Array.from(byObj.values());
    rows.forEach((r) => {
      r.aov = r.receipts > 0 ? r.revenue / r.receipts : 0;
    });
    rows.sort((a, b) => b.revenue - a.revenue);
    return rows;
  }, [cashierDays, todayDay]);

  // Stores table — Period rows (when picker active)
  const storeRowsPeriod = useMemo(() => {
    if (!periodActive) return [];
    const filt = cashierDays.filter((r) => {
      const d = (r.day || '').slice(0, 10);
      return d && d >= periodFrom && d <= periodTo;
    });
    const byObj = new Map();
    filt.forEach((r) => {
      const obj = r.object || '—';
      if (!byObj.has(obj)) {
        byObj.set(obj, { object: obj, cash: 0, card: 0, revenue: 0, receipts: 0 });
      }
      const acc = byObj.get(obj);
      acc.cash += Number(r.cash) || 0;
      acc.card += Number(r.card) || 0;
      acc.revenue += Number(r.revenue) || 0;
      acc.receipts += Number(r.receipts) || 0;
    });
    const rows = Array.from(byObj.values());
    rows.forEach((r) => {
      r.aov = r.receipts > 0 ? r.revenue / r.receipts : 0;
    });
    rows.sort((a, b) => b.revenue - a.revenue);
    return rows;
  }, [cashierDays, periodActive, periodFrom, periodTo]);

  // Today's waybills — fetch independently
  const [waybills, setWaybills] = useState([]);
  const [waybillsLoading, setWaybillsLoading] = useState(true);
  const [waybillsError, setWaybillsError] = useState(null);
  const [waybillsExpanded, setWaybillsExpanded] = useState(false);

  // Daily money flow — fetched independently
  const [moneyFlowIndex, setMoneyFlowIndex] = useState({});
  const [moneyFlowLoading, setMoneyFlowLoading] = useState(true);
  const [moneyFlowError, setMoneyFlowError] = useState(null);
  const [moneyFlowExpanded, setMoneyFlowExpanded] = useState(false);
  const [moneyFlowSuppliersExpanded, setMoneyFlowSuppliersExpanded] = useState(false);
  const [moneyFlowManualExpanded, setMoneyFlowManualExpanded] = useState(false);
  const [moneyFlowPosTbcExpanded, setMoneyFlowPosTbcExpanded] = useState(false);
  const [moneyFlowPosBogExpanded, setMoneyFlowPosBogExpanded] = useState(false);
  const [moneyFlowOutTbcExpanded, setMoneyFlowOutTbcExpanded] = useState(false);
  const [moneyFlowOutBogExpanded, setMoneyFlowOutBogExpanded] = useState(false);
  const [cashExpenseModalOpen, setCashExpenseModalOpen] = useState(false);
  const [cashExpenseForm, setCashExpenseForm] = useState({ category: 'salary', amount: '', date: new Date().toISOString().slice(0, 10), comment: '' });
  const [cashExpenseStatus, setCashExpenseStatus] = useState('');
  const [cashExpenseEntries, setCashExpenseEntries] = useState([]);
  const loadCashExpenseEntries = async () => {
    try {
      const res = await fetch('/api/cash-expenses');
      const data = await res.json();
      setCashExpenseEntries(Array.isArray(data.entries) ? data.entries : []);
    } catch (e) {
      // ignore
    }
  };
  useEffect(() => {
    if (cashExpenseModalOpen) loadCashExpenseEntries();
  }, [cashExpenseModalOpen]);
  const [outCatExpanded, setOutCatExpanded] = useState({ salary: false, rent: false, owner: false, service: false, refund: false, unmatched: false, other: false });
  const toggleOutCat = (k) => setOutCatExpanded((s) => ({ ...s, [k]: !s[k] }));
  const [profitExpExpanded, setProfitExpExpanded] = useState({ salary: false, rent: false, owner: false, service: false, refund: false });
  const toggleProfitExp = (k) => setProfitExpExpanded((s) => ({ ...s, [k]: !s[k] }));

  // Bank balances (TBC + BOG) — populated as a side-effect of /api/banks/refresh
  const [bankBalance, setBankBalance] = useState({});
  useEffect(() => {
    let active = true;
    fetch('/api/bank-balance')
      .then((r) => r.json())
      .then((data) => { if (active) setBankBalance(data || {}); })
      .catch(() => {});
    return () => { active = false; };
  }, [reloadKey]);

  // Data freshness — bank cache + Megaplus ingest state
  const [freshness, setFreshness] = useState(null);
  useEffect(() => {
    let active = true;
    fetch('/api/freshness')
      .then((r) => r.json())
      .then((data) => { if (active) setFreshness(data || null); })
      .catch(() => {});
    return () => { active = false; };
  }, [reloadKey]);

  // Per-store cash till — uses active period from picker, falls back to last 14 days
  const [cashTill, setCashTill] = useState(null);
  const [cashTillExpanded, setCashTillExpanded] = useState({});
  const toggleCashTill = (key) => setCashTillExpanded((p) => ({ ...p, [key]: !p[key] }));
  useEffect(() => {
    let active = true;
    const qs = periodActive ? `?from=${periodFrom}&to=${periodTo}` : '';
    fetch(`/api/cash-till${qs}`)
      .then((r) => r.json())
      .then((data) => { if (active) setCashTill(data || null); })
      .catch(() => {});
    return () => { active = false; };
  }, [reloadKey, periodActive, periodFrom, periodTo]);

  useEffect(() => {
    let active = true;
    setMoneyFlowLoading(true);
    setMoneyFlowError(null);
    fetchApiJson('/api/data?tab=daily_money_flow')
      .then((json) => {
        if (!active) return;
        setMoneyFlowIndex(json?.daily_money_flow_index || {});
        setMoneyFlowLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        console.error('Home: failed to load daily_money_flow', err);
        setMoneyFlowError(err.message);
        setMoneyFlowLoading(false);
      });
    return () => { active = false; };
  }, [reloadKey]);

  useEffect(() => {
    let active = true;
    setWaybillsLoading(true);
    setWaybillsError(null);
    fetchApiJson('/api/data?tab=waybills')
      .then((json) => {
        if (!active) return;
        setWaybills(Array.isArray(json?.waybills) ? json.waybills : []);
        setWaybillsLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        console.error('Home: failed to load waybills', err);
        setWaybillsError(err.message);
        setWaybillsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reloadKey]);

  const waybillsForDate = useMemo(() => {
    const targetDay = periodActive ? periodTo : todayDay;
    if (!targetDay) return [];
    // Waybills carry `date` (YYYY-MM-DD HH:MM:SS). If period active,
    // include waybills with date in [periodFrom, periodTo].
    return waybills.filter((w) => {
      const d = (w.date || '').slice(0, 10);
      if (!d) return false;
      if (periodActive) return d >= periodFrom && d <= periodTo;
      return d === targetDay;
    });
  }, [waybills, periodActive, periodFrom, periodTo, todayDay]);

  // Split waybills into regular (incoming) and returns. RS.ge convention:
  // `is_return` true means "უკან დაბრუნება" — the goods went back, amount
  // typically negative. Owner wants returns surfaced separately, not netted.
  const regularWaybills = useMemo(
    () => waybillsForDate.filter((w) => !w.is_return),
    [waybillsForDate],
  );
  const returnWaybills = useMemo(
    () => waybillsForDate.filter((w) => w.is_return),
    [waybillsForDate],
  );
  const waybillsRegularTotal = useMemo(
    () => regularWaybills.reduce((acc, w) => acc + (Number(w.effective_amount) || 0), 0),
    [regularWaybills],
  );
  const waybillsReturnsTotal = useMemo(
    () => returnWaybills.reduce((acc, w) => acc + (Number(w.effective_amount) || 0), 0),
    [returnWaybills],
  );

  // Daily money flow — aggregate across the active period (or single day)
  const moneyFlow = useMemo(() => {
    const days = [];
    if (periodActive) {
      Object.keys(moneyFlowIndex).forEach((d) => {
        if (d >= periodFrom && d <= periodTo) days.push(d);
      });
    } else if (todayDay && moneyFlowIndex[todayDay]) {
      days.push(todayDay);
    }
    if (days.length === 0) return null;

    // Aggregate
    const agg = {
      date_label: days.length === 1 ? days[0] : `${days[0]} → ${days[days.length - 1]}`,
      day_count: days.length,
      in: { cash_megaplus: 0, card_megaplus: 0, pos_bank_deposit: 0, pos_bank_deposit_tbc: 0, pos_bank_deposit_bog: 0, pos_lines_tbc: [], pos_lines_bog: [], foodmart_cashback: 0, other: [], bank_total: 0, total: 0, tbc: { pos: 0, pos_gross: 0, pos_fee: 0, cash_deposit: 0, samurneo: 0, other_total: 0, total: 0 }, bog: { pos: 0, pos_gross: 0, pos_fee: 0, cash_deposit: 0, samurneo: 0, other_total: 0, total: 0 } },
      out: { suppliers: {}, suppliers_total_bank: 0, suppliers_total_manual: 0, tax_treasury: 0, bank_fees: 0, salary: 0, salary_bank: 0, salary_items: [], rent: 0, rent_bank: 0, rent_items: [], owner_withdraw: 0, owner_withdraw_bank: 0, owner_withdraw_items: [], service: 0, service_bank: 0, service_items: [], refund: 0, refund_bank: 0, refund_items: [], unmatched_suppliers: 0, unmatched_suppliers_bank: 0, unmatched_supplier_items: [], other: [], bank_total: 0, cash_journal_total: 0, total: 0, tbc: { suppliers: 0, tax_treasury: 0, bank_fees: 0, other_total: 0, total: 0 }, bog: { suppliers: 0, tax_treasury: 0, bank_fees: 0, other_total: 0, total: 0 } },
      internal: { own_bank_transfers: 0, cash_to_bank: 0 },
      info: { waybills_regular_count: 0, waybills_regular_total: 0, waybills_returns_count: 0, waybills_returns_total: 0 },
      bank_net: 0,
      net: 0,
      warnings: [],
    };
    days.forEach((d) => {
      const m = moneyFlowIndex[d];
      if (!m) return;
      agg.in.cash_megaplus += m.in.cash_megaplus;
      agg.in.card_megaplus += m.in.card_megaplus;
      agg.in.pos_bank_deposit += m.in.pos_bank_deposit;
      agg.in.pos_bank_deposit_tbc += (m.in.pos_bank_deposit_tbc || 0);
      agg.in.pos_bank_deposit_bog += (m.in.pos_bank_deposit_bog || 0);
      if (Array.isArray(m.in.pos_lines_tbc)) agg.in.pos_lines_tbc.push(...m.in.pos_lines_tbc);
      if (Array.isArray(m.in.pos_lines_bog)) agg.in.pos_lines_bog.push(...m.in.pos_lines_bog);
      agg.in.foodmart_cashback += m.in.foodmart_cashback;
      agg.in.other.push(...m.in.other);
      agg.in.bank_total += (m.in.bank_total || 0);
      agg.in.total += m.in.total;
      agg.out.suppliers_total_bank += m.out.suppliers_total_bank;
      agg.out.suppliers_total_manual += m.out.suppliers_total_manual;
      agg.out.tax_treasury += m.out.tax_treasury;
      agg.out.bank_fees += m.out.bank_fees;
      agg.out.salary += (m.out.salary || 0);
      agg.out.salary_bank += (m.out.salary_bank || 0);
      if (Array.isArray(m.out.salary_items)) agg.out.salary_items.push(...m.out.salary_items);
      agg.out.rent += (m.out.rent || 0);
      agg.out.rent_bank += (m.out.rent_bank || 0);
      if (Array.isArray(m.out.rent_items)) agg.out.rent_items.push(...m.out.rent_items);
      agg.out.owner_withdraw += (m.out.owner_withdraw || 0);
      agg.out.owner_withdraw_bank += (m.out.owner_withdraw_bank || 0);
      if (Array.isArray(m.out.owner_withdraw_items)) agg.out.owner_withdraw_items.push(...m.out.owner_withdraw_items);
      agg.out.service += (m.out.service || 0);
      agg.out.service_bank += (m.out.service_bank || 0);
      if (Array.isArray(m.out.service_items)) agg.out.service_items.push(...m.out.service_items);
      agg.out.refund += (m.out.refund || 0);
      agg.out.refund_bank += (m.out.refund_bank || 0);
      if (Array.isArray(m.out.refund_items)) agg.out.refund_items.push(...m.out.refund_items);
      agg.out.unmatched_suppliers += (m.out.unmatched_suppliers || 0);
      agg.out.unmatched_suppliers_bank += (m.out.unmatched_suppliers_bank || 0);
      if (Array.isArray(m.out.unmatched_supplier_items)) agg.out.unmatched_supplier_items.push(...m.out.unmatched_supplier_items);
      agg.out.other.push(...m.out.other);
      agg.out.bank_total += (m.out.bank_total || 0);
      agg.out.cash_journal_total += (m.out.cash_journal_total || 0);
      agg.out.total += m.out.total;
      agg.internal.own_bank_transfers += m.internal.own_bank_transfers;
      agg.internal.cash_to_bank += m.internal.cash_to_bank;
      agg.info.waybills_regular_count += m.info.waybills_regular_count;
      agg.info.waybills_regular_total += m.info.waybills_regular_total;
      agg.info.waybills_returns_count += m.info.waybills_returns_count;
      agg.info.waybills_returns_total += m.info.waybills_returns_total;
      agg.bank_net += (m.bank_net || 0);
      agg.net += m.net;
      if (Array.isArray(m.warnings) && m.warnings.length > 0) {
        m.warnings.forEach((w) => agg.warnings.push({ day: d, msg: w }));
      }
      // Per-bank sub-totals (IN)
      ['tbc', 'bog'].forEach((b) => {
        const src = (m.in && m.in[b]) || {};
        agg.in[b].pos += (src.pos || 0);
        agg.in[b].pos_gross += (src.pos_gross || 0);
        agg.in[b].pos_fee += (src.pos_fee || 0);
        agg.in[b].cash_deposit += (src.cash_deposit || 0);
        agg.in[b].samurneo += (src.samurneo || 0);
        agg.in[b].other_total += (src.other_total || 0);
        agg.in[b].total += (src.total || 0);
      });
      // Per-bank sub-totals (OUT)
      ['tbc', 'bog'].forEach((b) => {
        const src = (m.out && m.out[b]) || {};
        agg.out[b].suppliers += (src.suppliers || 0);
        agg.out[b].tax_treasury += (src.tax_treasury || 0);
        agg.out[b].bank_fees += (src.bank_fees || 0);
        agg.out[b].other_total += (src.other_total || 0);
        agg.out[b].total += (src.total || 0);
      });
      // Merge suppliers by tax_id; track earliest ap_before and latest ap_after
      (m.out.suppliers || []).forEach((s) => {
        const cur = agg.out.suppliers[s.tax_id];
        if (!cur) {
          agg.out.suppliers[s.tax_id] = {
            tax_id: s.tax_id, supplier_name: s.supplier_name,
            amount: s.amount, amount_bank: s.amount_bank,
            amount_bank_tbc: s.amount_bank_tbc || 0,
            amount_bank_bog: s.amount_bank_bog || 0,
            amount_manual: s.amount_manual,
            ap_before: s.ap_before, // first time we see supplier — earliest day's start
            ap_after: s.ap_after,
            returns_today: s.returns_today,
          };
        } else {
          cur.amount += s.amount;
          cur.amount_bank += s.amount_bank;
          cur.amount_bank_tbc += (s.amount_bank_tbc || 0);
          cur.amount_bank_bog += (s.amount_bank_bog || 0);
          cur.amount_manual += s.amount_manual;
          cur.ap_after = s.ap_after; // latest day's AP
          cur.returns_today += s.returns_today;
        }
      });
    });
    // Flatten suppliers map → sorted array
    agg.out.suppliers_list = Object.values(agg.out.suppliers).sort((a, b) =>
      (b.amount + Math.abs(b.returns_today)) - (a.amount + Math.abs(a.returns_today))
    );

    // სამეურნეო netting (per calendar month): BOG-დან "სამეურნეო" გასვლა +
    // TBC-ში "სამეურნეო" შემოსვლა — owner ფიზიკურად ნაღდს გადააქვს BOG → TBC.
    // იმავე თვის შიგნით დაბრუნებული = შიდა გადარიცხვა; რაც არ დაბრუნდა = რეალური ხარჯი.
    // (Owner confirmed 2026-05-13.)
    const monthBuckets = {};
    days.forEach((d) => {
      const m = moneyFlowIndex[d];
      if (!m) return;
      const ym = d.slice(0, 7);
      if (!monthBuckets[ym]) monthBuckets[ym] = { samurneoIn: 0, ownerOut: 0 };
      monthBuckets[ym].samurneoIn += (m.in.tbc?.samurneo || 0) + (m.in.bog?.samurneo || 0);
      monthBuckets[ym].ownerOut += (m.out.owner_withdraw || 0);
    });
    let samurneoInternal = 0;
    Object.values(monthBuckets).forEach((b) => {
      samurneoInternal += Math.min(b.samurneoIn, b.ownerOut);
    });
    agg.samurneo_internal = samurneoInternal;
    // Subtract from headline IN/OUT
    agg.in.bank_total -= samurneoInternal;
    agg.out.bank_total -= samurneoInternal;
    agg.bank_net = agg.in.bank_total - agg.out.bank_total;
    // Subtract owner_withdraw portion that's actually internal (applies to BOTH
    // the total and the bank-only sub-total — internal is a bank-side movement).
    agg.out.owner_withdraw = Math.max(0, agg.out.owner_withdraw - samurneoInternal);
    agg.out.owner_withdraw_bank = Math.max(0, agg.out.owner_withdraw_bank - samurneoInternal);
    // Subtract samurneo from per-bank totals (proportionally between TBC and BOG)
    const samurneoInTotal = (agg.in.tbc?.samurneo || 0) + (agg.in.bog?.samurneo || 0);
    if (samurneoInTotal > 0 && samurneoInternal > 0) {
      const tbcShare = (agg.in.tbc.samurneo || 0) / samurneoInTotal;
      const bogShare = (agg.in.bog.samurneo || 0) / samurneoInTotal;
      const tbcAdj = samurneoInternal * tbcShare;
      const bogAdj = samurneoInternal * bogShare;
      agg.in.tbc.samurneo = Math.max(0, agg.in.tbc.samurneo - tbcAdj);
      agg.in.bog.samurneo = Math.max(0, agg.in.bog.samurneo - bogAdj);
      agg.in.tbc.total = Math.max(0, agg.in.tbc.total - tbcAdj);
      agg.in.bog.total = Math.max(0, agg.in.bog.total - bogAdj);
    }

    // AP delta — TOTAL debt across ALL suppliers (active + inactive), not just
    // suppliers touched in the period. Uses pre-computed total_ap_before of the
    // FIRST day and total_ap_after of the LAST day so headline equals real
    // total debt, not an active-only subset (per aggregate-vs-source rule).
    const firstDay = days[0];
    const lastDay = days[days.length - 1];
    const firstMf = moneyFlowIndex[firstDay] || {};
    const lastMf = moneyFlowIndex[lastDay] || {};
    agg.ap_start = (firstMf.total_ap_before != null) ? firstMf.total_ap_before
                   : agg.out.suppliers_list.reduce((sum, s) => sum + (s.ap_before || 0), 0);
    agg.ap_end = (lastMf.total_ap_after != null) ? lastMf.total_ap_after
                 : agg.out.suppliers_list.reduce((sum, s) => sum + (s.ap_after || 0), 0);
    agg.ap_change = agg.ap_end - agg.ap_start;

    // Real net cash flow — counts each ₾ once. agg.in.total adds card+cash+bank_in
    // which DOUBLE-counts (POS deposits = card sales reaching bank; cash deposits
    // = cash sales rotated). True "new money" = customer sales + non-rotation bank inflows.
    const sales = (agg.in.cash_megaplus || 0) + (agg.in.card_megaplus || 0);
    const otherNew = (agg.in.foodmart_cashback || 0) +
                     ((agg.in.tbc?.samurneo || 0) + (agg.in.bog?.samurneo || 0)) +
                     (agg.in.other || []).reduce((a, r) => a + (r.amount || 0), 0);
    agg.true_in = sales + otherNew;
    agg.true_in_sales = sales;
    agg.true_in_other = otherNew;
    agg.true_out_bank = agg.out.bank_total;
    agg.true_out_cash_journal = agg.out.cash_journal_total || 0;
    agg.true_out_cash_expenses = (agg.out.salary_items || []).filter((it) => it.bank === 'ნაღდი').reduce((a, it) => a + it.amount, 0)
      + (agg.out.rent_items || []).filter((it) => it.bank === 'ნაღდი').reduce((a, it) => a + it.amount, 0)
      + (agg.out.owner_withdraw_items || []).filter((it) => it.bank === 'ნაღდი').reduce((a, it) => a + it.amount, 0)
      + (agg.out.service_items || []).filter((it) => it.bank === 'ნაღდი').reduce((a, it) => a + it.amount, 0)
      + (agg.out.unmatched_supplier_items || []).filter((it) => it.bank === 'ნაღდი').reduce((a, it) => a + it.amount, 0)
      + (agg.out.other || []).filter((it) => it.bank === 'ნაღდი').reduce((a, it) => a + it.amount, 0);
    agg.true_out = agg.true_out_bank + agg.true_out_cash_journal + agg.true_out_cash_expenses;
    agg.true_net = agg.true_in - agg.true_out;

    // Cash till residual — sum of cash sales minus all known cash outflows.
    // Positive = cash unaccounted for (likely unlogged ops expense); near zero = all reconciled.
    // Only meaningful for multi-day periods (single-day residual skewed by next-day deposit lag).
    const tillCashDepositTotal = (agg.in.tbc?.cash_deposit || 0) + (agg.in.bog?.cash_deposit || 0);
    agg.cash_residual = (agg.in.cash_megaplus || 0)
      - tillCashDepositTotal
      - (agg.out.cash_journal_total || 0)
      - agg.true_out_cash_expenses;

    // Real Net Profit breakdown — what owner ACTUALLY earned in the period
    // after operating expenses, NOT counting supplier payments (those are
    // COGS already netted via Megaplus per-sale cost).
    //
    //   revenue − COGS         = gross_profit
    //   + cashback             = total_gain
    //   − operating_expenses   = real_net_profit
    //
    // Operating expenses = salary + rent + owner_withdraw + services + tax +
    // bank fees + refund (each bank+cash combined). Excludes supplier payments
    // and the "unmatched supplier" bucket (those are AP-side).
    let cogs = 0;
    let rev_from_trend = 0;
    dailyTrend.forEach((r) => {
      const d = (r.day || '').slice(0, 10);
      if (!d) return;
      let inPeriod = false;
      if (periodActive) {
        inPeriod = d >= periodFrom && d <= periodTo;
      } else {
        inPeriod = d === todayDay;
      }
      if (!inPeriod) return;
      cogs += Number(r.cost_ge) || 0;
      rev_from_trend += Number(r.revenue_ge) || 0;
    });
    const op_salary = agg.out.salary || 0;
    const op_rent = agg.out.rent || 0;
    const op_owner = agg.out.owner_withdraw || 0;
    const op_service = agg.out.service || 0;
    const op_tax = agg.out.tax_treasury || 0;
    const op_fees = agg.out.bank_fees || 0;
    const op_refund = agg.out.refund || 0;
    const op_total = op_salary + op_rent + op_owner + op_service + op_tax + op_fees + op_refund;
    const gross_profit = rev_from_trend - cogs;
    const cashback = agg.in.foodmart_cashback || 0;
    agg.profit_breakdown = {
      revenue: rev_from_trend,
      cogs,
      gross_profit,
      cashback,
      op_salary,
      op_rent,
      op_owner,
      op_service,
      op_tax,
      op_fees,
      op_refund,
      op_total,
      real_net_profit: gross_profit + cashback - op_total,
    };

    // Legacy: keep net_in_out as agg.in.total - agg.out.total (over-counts, do not use for headline)
    agg.net_in_out = agg.in.total - agg.out.total;
    return agg;
  }, [moneyFlowIndex, periodActive, periodFrom, periodTo, todayDay, dailyTrend]);

  // Color palette per store
  const storeColor = (obj) => {
    if (obj === 'დვაბზუ') return '#3b82f6';
    if (obj === 'ოზურგეთი') return '#10b981';
    return '#94a3b8';
  };

  const dataReady = !!retailSales && Array.isArray(retailSales.daily_trend);

  if (!dataReady) {
    return (
      <div style={{ padding: 24, color: '#94a3b8', fontSize: '1rem', textAlign: 'center' }}>
        იტვირთება მთავარი გვერდის მონაცემები...
      </div>
    );
  }

  if (!todayDay) {
    return (
      <div style={{ padding: 24, color: '#94a3b8', textAlign: 'center' }}>
        ჯერ მონაცემი არ შემოსულა — სალარო ცარიელია.
      </div>
    );
  }

  const headerLabel = periodActive
    ? `${fmtDayKa(periodFrom)} — ${fmtDayKa(periodTo)}`
    : `${fmtDayKa(todayDay)}`;

  const periodLabel = periodActive ? 'არჩეული პერიოდი' : 'ბოლო სრული დღე';

  const rowsToShow = periodActive ? storeRowsPeriod : storeRowsToday;

  // KPI sub line: delta vs yesterday (only when no period picked)
  const revenueSub = periodActive
    ? null
    : (deltaRevenuePct === null
      ? 'წინა დღე — მონაცემი არ არის'
      : `გუშინდელთან ${deltaRevenuePct >= 0 ? '▲' : '▼'} ${fmtPct(deltaRevenuePct)}`);
  const profitSub = periodActive
    ? null
    : (deltaProfitPct === null
      ? 'წინა დღე — მონაცემი არ არის'
      : `გუშინდელთან ${deltaProfitPct >= 0 ? '▲' : '▼'} ${fmtPct(deltaProfitPct)}`);

  const profitColor = todayProfit >= 0 ? '#22c55e' : '#ef4444';

  return (
    <div style={{ padding: '0 4px' }}>
      {/* Header row — period summary + title */}
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div>
          <div style={{ fontSize: '1.45rem', fontWeight: 700, color: '#f1f5f9' }}>
            მთავარი — დღევანდელი სურათი
          </div>
          <div style={{ color: '#94a3b8', fontSize: '0.92rem', marginTop: 2 }}>
            {periodLabel}: <strong style={{ color: '#cbd5e1' }}>{headerLabel}</strong>
          </div>
          {freshness && (() => {
            const banks = freshness.banks || {};
            const bankTimes = ['tbc', 'bog', 'rsge']
              .map((k) => banks[k]?.last_completed_at)
              .filter(Boolean)
              .map((iso) => new Date(iso).getTime())
              .filter((n) => !isNaN(n));
            // Use the STALEST bank (Math.min of completion timestamps), not the freshest —
            // otherwise a fresh BOG hides a stale TBC. The dot/badge should reflect
            // the worst-case freshness across all bank sources.
            const bankLatest = bankTimes.length ? Math.min(...bankTimes) : null;
            const mpDates = Object.values(freshness.megaplus || {})
              .map((s) => s?.last_backup_date)
              .filter(Boolean);
            const mpEarliest = mpDates.length ? mpDates.sort()[0] : null;
            const fmtAgo = (ms) => {
              const diff = Date.now() - ms;
              if (diff < 0) return 'ახლახან';
              const min = Math.floor(diff / 60000);
              if (min < 60) return `${min} წთ წინ`;
              const hr = Math.floor(min / 60);
              if (hr < 24) return `${hr} სთ წინ`;
              return `${Math.floor(hr / 24)} დღის წინ`;
            };
            const bankColor = bankLatest && (Date.now() - bankLatest) < 6 * 3600 * 1000 ? '#10b981' : (bankLatest && (Date.now() - bankLatest) < 24 * 3600 * 1000 ? '#f59e0b' : '#ef4444');
            const mpColor = mpEarliest && mpEarliest >= todayDay ? '#10b981' : (mpEarliest && new Date(mpEarliest).getTime() > Date.now() - 2 * 86400000 ? '#f59e0b' : '#ef4444');
            return (
              <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                {bankLatest && (
                  <span><span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: 4, background: bankColor, marginRight: 5, verticalAlign: 'middle' }} />ბანკი: {fmtAgo(bankLatest)}</span>
                )}
                {mpEarliest && (
                  <span><span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: 4, background: mpColor, marginRight: 5, verticalAlign: 'middle' }} />Megaplus: {fmtDayKa(mpEarliest)}-მდე</span>
                )}
              </div>
            );
          })()}
        </div>
      </div>

      {/* ----- ZONE 1: 3 KPI cards ----- */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: 14,
          marginBottom: 24,
        }}
      >
        <KpiCard
          icon="💰"
          label={periodActive ? 'პერიოდის ნავაჭრი' : 'დღევანდელი ნავაჭრი'}
          value={fmtGel2(
            periodActive ? rowsToShow.reduce((a, r) => a + r.revenue, 0) : todayRevenue,
          )}
          sub={revenueSub}
          color="#22c55e"
        />
        <KpiCard
          icon="📈"
          label={periodActive ? 'პერიოდის მოგება' : 'დღევანდელი მოგება'}
          value={fmtGel2(
            periodActive
              ? dailyTrend
                  .filter((r) => {
                    const d = (r.day || '').slice(0, 10);
                    return d && d >= periodFrom && d <= periodTo;
                  })
                  .reduce((a, r) => a + (Number(r.profit_ge) || 0), 0)
              : todayProfit,
          )}
          sub={profitSub}
          color={profitColor}
        />
        {(() => {
          const tbc = bankBalance.tbc;
          const bog = bankBalance.bog;
          const fmtFetchedAgo = (iso) => {
            if (!iso) return null;
            const ms = Date.now() - new Date(iso).getTime();
            if (isNaN(ms) || ms < 0) return null;
            const min = Math.floor(ms / 60000);
            if (min < 1) return 'ახლახან';
            if (min < 60) return `${min} წთ წინ`;
            const hr = Math.floor(min / 60);
            if (hr < 24) return `${hr} სთ წინ`;
            const days = Math.floor(hr / 24);
            return `${days} დღის წინ`;
          };
          return (
            <>
              <KpiCard
                icon="🏦"
                label="TBC ნაშთი"
                value={tbc ? fmtGel2(tbc.closing_balance) : '—'}
                sub={tbc ? `განახლდა ${fmtFetchedAgo(tbc.fetched_at) || ''}` : 'ჯერ არ განახლებულა — დააწექი „განახლება"'}
                color={tbc ? '#3b82f6' : '#64748b'}
                placeholder={!tbc}
              />
              <KpiCard
                icon="🏦"
                label="BOG ნაშთი"
                value={bog ? fmtGel2(bog.current) : '—'}
                sub={bog ? `განახლდა ${fmtFetchedAgo(bog.fetched_at) || ''}` : 'ჯერ არ განახლებულა — დააწექი „განახლება"'}
                color={bog ? '#f59e0b' : '#64748b'}
                placeholder={!bog}
              />
            </>
          );
        })()}
      </div>

      {/* ----- Cash till per store ----- */}
      {cashTill && cashTill.stores && (() => {
        const stores = cashTill.stores;
        const totals = cashTill.totals;
        const periodLabel2 = `${fmtDayKa(cashTill.period.from)} → ${fmtDayKa(cashTill.period.to)}`;
        const storeEntries = Object.entries(stores).filter(([_, s]) => (s.cash_sales || 0) > 0 || (s.cash_deposits || 0) > 0);
        if (storeEntries.length === 0) return null;
        const thS = { color: '#94a3b8', textAlign: 'left', padding: '4px 6px', fontWeight: 500, borderBottom: '1px solid rgba(255,255,255,0.08)', fontSize: '0.78rem' };
        const tdS = { padding: '4px 6px', color: '#e2e8f0', borderBottom: '1px solid rgba(255,255,255,0.04)' };
        const tblS = { width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', minWidth: 220 };
        return (
          <div style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 12,
            padding: '18px 20px',
            marginBottom: 24,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f1f5f9' }}>
                💵 ნაღდი ფული საფიცარში
              </h3>
              <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>{periodLabel2}</div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
              {storeEntries.map(([name, s]) => {
                const tillColor = s.till_change >= 0 ? '#10b981' : '#ef4444';
                const salesLines = s.sales_lines || [];
                const depositLines = s.deposit_lines || [];
                const salesTable = salesLines.length > 0 ? (
                  <table style={tblS}>
                    <thead><tr>
                      <th style={thS}>დღე</th>
                      <th style={{ ...thS, textAlign: 'right' }}>თანხა</th>
                    </tr></thead>
                    <tbody>
                      {salesLines.map((r, i) => (
                        <tr key={i}>
                          <td style={tdS}>{fmtDayKa(r.day)}</td>
                          <td style={{ ...tdS, textAlign: 'right' }}>{fmtGel2(r.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : null;
                const depositTable = depositLines.length > 0 ? (
                  <table style={tblS}>
                    <thead><tr>
                      <th style={thS}>გაყიდვის დღე</th>
                      <th style={thS}>ბანკი</th>
                      <th style={{ ...thS, textAlign: 'right' }}>თანხა</th>
                    </tr></thead>
                    <tbody>
                      {depositLines.map((r, i) => (
                        <tr key={i}>
                          <td style={tdS}>
                            {fmtDayKa(r.day)}
                            {r.bank_day && r.bank_day !== r.day && (
                              <div style={{ fontSize: '0.72rem', color: '#64748b' }}>ბანკში: {fmtDayKa(r.bank_day)}</div>
                            )}
                          </td>
                          <td style={tdS}>{bankBadge(r.bank)}</td>
                          <td style={{ ...tdS, textAlign: 'right' }}>{fmtGel2(r.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : null;
                return (
                  <div key={name}>
                    <div style={{ color: '#f1f5f9', fontSize: '1rem', fontWeight: 600, marginBottom: 8 }}>{name}</div>
                    <CashTillRow
                      label="გაიყიდა ნაღდად"
                      amount={s.cash_sales}
                      expanded={!!cashTillExpanded[`sales_${name}`]}
                      onToggle={() => toggleCashTill(`sales_${name}`)}
                    >
                      {salesTable}
                    </CashTillRow>
                    <CashTillRow
                      label="− ბანკში ჩაიდო"
                      amount={s.cash_deposits}
                      negative
                      expanded={!!cashTillExpanded[`deposits_${name}`]}
                      onToggle={() => toggleCashTill(`deposits_${name}`)}
                    >
                      {depositTable}
                    </CashTillRow>
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', margin: '6px 0' }} />
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', color: tillColor, fontWeight: 700, fontSize: '1.05rem' }}>
                      <span>საფიცარში დარჩა</span>
                      <span>{s.till_change > 0 ? '+' : ''}{fmtGel2(s.till_change)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.10)', marginTop: 14, paddingTop: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: '#94a3b8', fontSize: '0.92rem' }}>სალაროდან ბანკში გასული (ჯამი)</span>
              <span style={{ color: '#cbd5e1', fontSize: '0.95rem' }}>
                {totals.till_change > 0 ? '+' : ''}{fmtGel2(totals.till_change)}
              </span>
            </div>
            {(totals.unattributed_deposits || 0) > 0 && (() => {
              const lines = totals.unattributed_deposit_lines || [];
              const unattrTable = lines.length > 0 ? (
                <table style={tblS}>
                  <thead><tr>
                    <th style={thS}>გაყიდვის დღე</th>
                    <th style={thS}>ბანკი</th>
                    <th style={thS}>დანიშნულება</th>
                    <th style={{ ...thS, textAlign: 'right' }}>თანხა</th>
                  </tr></thead>
                  <tbody>
                    {lines.map((r, i) => (
                      <tr key={i}>
                        <td style={tdS}>
                          {fmtDayKa(r.day)}
                          {r.bank_day && r.bank_day !== r.day && (
                            <div style={{ fontSize: '0.72rem', color: '#64748b' }}>ბანკში: {fmtDayKa(r.bank_day)}</div>
                          )}
                        </td>
                        <td style={tdS}>{bankBadge(r.bank)}</td>
                        <td style={{ ...tdS, fontSize: '0.78rem', color: '#94a3b8' }}>{r.purpose}</td>
                        <td style={{ ...tdS, textAlign: 'right' }}>{fmtGel2(r.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null;
              return (
                <div style={{ marginTop: 4, padding: '6px 10px', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 6 }}>
                  <CashTillRow
                    label={`⚠️ მაღაზიის გარეშე ჩარიცხული (${lines.length} ჩანაწერი)`}
                    amount={totals.unattributed_deposits}
                    valueColor="#fbbf24"
                    expanded={!!cashTillExpanded.unattributed}
                    onToggle={() => toggleCashTill('unattributed')}
                    indent={0}
                  >
                    {unattrTable}
                  </CashTillRow>
                </div>
              );
            })()}
            {totals.cash_supplier_paid > 0 && (() => {
              const lines = totals.supplier_paid_lines || [];
              const supplierTable = lines.length > 0 ? (
                <table style={tblS}>
                  <thead><tr>
                    <th style={thS}>თარიღი</th>
                    <th style={thS}>მომწოდებელი</th>
                    <th style={{ ...thS, textAlign: 'right' }}>თანხა</th>
                  </tr></thead>
                  <tbody>
                    {lines.map((r, i) => (
                      <tr key={i}>
                        <td style={tdS}>{fmtDayKa(r.date)}</td>
                        <td style={tdS}>{r.name}</td>
                        <td style={{ ...tdS, textAlign: 'right', color: '#f87171' }}>−{fmtGel2(r.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null;
              return (
                <CashTillRow
                  label="− ხელით მომწოდებლებს ნაღდად"
                  amount={totals.cash_supplier_paid}
                  negative
                  valueColor="#f87171"
                  expanded={!!cashTillExpanded.supplier_paid}
                  onToggle={() => toggleCashTill('supplier_paid')}
                  indent={0}
                >
                  {supplierTable}
                </CashTillRow>
              );
            })()}
            {totals.cash_expenses_paid > 0 && (() => {
              const lines = totals.cash_expense_lines || [];
              const expenseTable = lines.length > 0 ? (
                <table style={tblS}>
                  <thead><tr>
                    <th style={thS}>თარიღი</th>
                    <th style={thS}>კატეგორია</th>
                    <th style={thS}>კომენტარი</th>
                    <th style={{ ...thS, textAlign: 'right' }}>თანხა</th>
                  </tr></thead>
                  <tbody>
                    {lines.map((r, i) => (
                      <tr key={i}>
                        <td style={tdS}>{fmtDayKa(r.date)}</td>
                        <td style={tdS}>{r.category_label}</td>
                        <td style={{ ...tdS, fontSize: '0.78rem', color: '#94a3b8' }}>{r.comment}</td>
                        <td style={{ ...tdS, textAlign: 'right', color: '#f87171' }}>−{fmtGel2(r.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null;
              return (
                <CashTillRow
                  label="− ნაღდი ხარჯი (ხელფასი / ქირა / სხვა)"
                  amount={totals.cash_expenses_paid}
                  negative
                  valueColor="#f87171"
                  expanded={!!cashTillExpanded.cash_expenses}
                  onToggle={() => toggleCashTill('cash_expenses')}
                  indent={0}
                >
                  {expenseTable}
                </CashTillRow>
              );
            })()}
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.10)', marginTop: 6, paddingTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: '#f1f5f9', fontWeight: 600, fontSize: '0.95rem' }}>რეალური სალაროს ცვლილება</span>
              <span style={{ color: totals.real_till_change >= 0 ? '#10b981' : '#ef4444', fontWeight: 700, fontSize: '1.2rem' }}>
                {totals.real_till_change > 0 ? '+' : ''}{fmtGel2(totals.real_till_change)}
              </span>
            </div>
            <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: 6, fontStyle: 'italic' }}>
              ⓘ ხელფასი/იჯარა ნაღდად, თუ ჟურნალში ცალკე ჩაწერე — აქ ჯერ არ ჩანს, რომელი მაღაზიის სალაროდან წავიდა.
            </div>
          </div>
        );
      })()}

      {/* ----- Real Net Profit breakdown ----- */}
      {moneyFlow && moneyFlow.profit_breakdown && (periodActive || todayDay) && (() => {
        const pb = moneyFlow.profit_breakdown;
        const rowS = { display: 'flex', justifyContent: 'space-between', padding: '4px 0', color: '#cbd5e1' };
        const subS = { ...rowS, paddingLeft: 20, color: '#94a3b8', fontSize: '0.88rem' };
        const sepS = { borderTop: '1px solid rgba(255,255,255,0.08)', margin: '6px 0' };
        const netColor = pb.real_net_profit >= 0 ? '#10b981' : '#ef4444';
        return (
          <div style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 12,
            padding: '18px 20px',
            marginBottom: 24,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f1f5f9' }}>
                📊 რეალური მოგება — საიდან მოდის
              </h3>
              <div style={{ fontSize: '1.3rem', fontWeight: 700, color: netColor }}>
                {fmtGel2(pb.real_net_profit)}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
              {/* IN side */}
              <div>
                <div style={{ color: '#10b981', fontSize: '0.9rem', fontWeight: 600, marginBottom: 6 }}>↗ შემოვიდა</div>
                <div style={rowS}><span>ნავაჭრი</span><span>{fmtGel2(pb.revenue)}</span></div>
                <div style={subS}><span>− საქონლის ფასი (COGS)</span><span>−{fmtGel2(pb.cogs)}</span></div>
                <div style={sepS} />
                <div style={{ ...rowS, color: '#f1f5f9', fontWeight: 600 }}>
                  <span>ბრუტო მოგება</span>
                  <span>{fmtGel2(pb.gross_profit)}</span>
                </div>
                {pb.cashback > 0 && (
                  <div style={{ ...rowS, color: '#10b981' }}>
                    <span>+ ფუდმარტი ქეშბექი</span>
                    <span>+{fmtGel2(pb.cashback)}</span>
                  </div>
                )}
                <div style={sepS} />
                <div style={{ ...rowS, color: '#10b981', fontWeight: 600 }}>
                  <span>სულ მოგება გასახარჯად</span>
                  <span>{fmtGel2(pb.gross_profit + pb.cashback)}</span>
                </div>
              </div>

              {/* OUT side */}
              <div>
                <div style={{ color: '#ef4444', fontSize: '0.9rem', fontWeight: 600, marginBottom: 6 }}>↘ ოპერაციული ხარჯი</div>
                {pb.op_salary > 0 && (
                  <ProfitExpenseRow
                    label="ხელფასი (ბანკი + ნაღდი)"
                    amount={pb.op_salary}
                    items={moneyFlow.out.salary_items}
                    expanded={profitExpExpanded.salary}
                    onToggle={() => toggleProfitExp('salary')}
                  />
                )}
                {pb.op_rent > 0 && (
                  <ProfitExpenseRow
                    label="ქირა"
                    amount={pb.op_rent}
                    items={moneyFlow.out.rent_items}
                    expanded={profitExpExpanded.rent}
                    onToggle={() => toggleProfitExp('rent')}
                  />
                )}
                {pb.op_owner > 0 && (
                  <ProfitExpenseRow
                    label="⚠ მფლობელი (შენ მიიღე)"
                    amount={pb.op_owner}
                    items={moneyFlow.out.owner_withdraw_items}
                    expanded={profitExpExpanded.owner}
                    onToggle={() => toggleProfitExp('owner')}
                    yellow
                    note={moneyFlow.samurneo_internal > 0 ? (
                      <>
                        ⓘ ცხრილში ჯამი {fmtGel2(pb.op_owner + moneyFlow.samurneo_internal)} გამოვა — აქედან <strong>{fmtGel2(moneyFlow.samurneo_internal)}</strong> შიდა გადარიცხვაა (BOG-დან ნაღდად აიღე და TBC-ში დააბრუნე სამეურნეო-დ).<br/>
                        ე.ი. რეალურად შენ მიიღე <strong>{fmtGel2(pb.op_owner)}</strong>.
                      </>
                    ) : null}
                  />
                )}
                {pb.op_service > 0 && (
                  <ProfitExpenseRow
                    label="სერვისები / კომუნ."
                    amount={pb.op_service}
                    items={moneyFlow.out.service_items}
                    expanded={profitExpExpanded.service}
                    onToggle={() => toggleProfitExp('service')}
                  />
                )}
                {pb.op_tax > 0 && <div style={rowS}><span>გადასახადი (ხაზინა)</span><span>−{fmtGel2(pb.op_tax)}</span></div>}
                {pb.op_fees > 0 && <div style={rowS}><span>ბანკის საკომისიო</span><span>−{fmtGel2(pb.op_fees)}</span></div>}
                {pb.op_refund > 0 && (
                  <ProfitExpenseRow
                    label="დაბრუნება (refund)"
                    amount={pb.op_refund}
                    items={moneyFlow.out.refund_items}
                    expanded={profitExpExpanded.refund}
                    onToggle={() => toggleProfitExp('refund')}
                  />
                )}
                <div style={sepS} />
                <div style={{ ...rowS, color: '#ef4444', fontWeight: 600 }}>
                  <span>სულ ხარჯი</span>
                  <span>−{fmtGel2(pb.op_total)}</span>
                </div>
              </div>
            </div>

            <div style={{ ...sepS, marginTop: 14, marginBottom: 10 }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0' }}>
              <span style={{ color: '#f1f5f9', fontSize: '1rem', fontWeight: 700 }}>
                რეალური წმინდა მოგება
              </span>
              <span style={{ color: netColor, fontSize: '1.4rem', fontWeight: 700 }}>
                {fmtGel2(pb.real_net_profit)}
              </span>
            </div>
            {periodActive && moneyFlow.day_count > 1 && Math.abs(moneyFlow.cash_residual) > 50 && (
              <div style={{ color: '#fbbf24', fontSize: '0.82rem', marginTop: 4 }}>
                {moneyFlow.cash_residual > 0 ? (
                  <>⚠ შესაძლოა ~{fmtGel2(moneyFlow.cash_residual)} ნაღდი ჟურნალში ვერ ჩაიწერა — რეალური ციფრი ამდენით ნაკლები შეიძლება იყოს.</>
                ) : (
                  <>⚠ ჟურნალში ~{fmtGel2(Math.abs(moneyFlow.cash_residual))}-ით მეტი ნაღდი ხარჯი ჩანს, ვიდრე ფაქტობრივი ნაღდი — გადახედე ჩანაწერებს.</>
                )}
              </div>
            )}
            {periodActive && moneyFlow.day_count > 1 && Math.abs(moneyFlow.cash_residual) <= 50 && (
              <div style={{ color: '#10b981', fontSize: '0.82rem', marginTop: 4 }}>
                ✓ ნაღდის ჯამი ფაქტობრივ ნაშთს ემთხვევა — დამატებითი აღურიცხავი არ ჩანს.
              </div>
            )}
            <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: 4, fontStyle: 'italic' }}>
              მომწოდებლების გადახდა ცალკე ანგარიშია — COGS-ში უკვე ჩათვლილია საქონლის ფასი, ე.ი. დუბლი არ ხდება.
            </div>
          </div>
        );
      })()}

      {/* ----- Month-end summary: where did the money go ----- */}
      {periodActive && moneyFlow && moneyFlow.day_count > 1 && moneyFlow.profit_breakdown && (() => {
        const pb = moneyFlow.profit_breakdown;
        const profit = pb.real_net_profit || 0;
        const netPurchases = (moneyFlow.info.waybills_regular_total || 0) + (moneyFlow.info.waybills_returns_total || 0);
        const inventoryChange = netPurchases - (pb.cogs || 0);
        const ownerPocket = moneyFlow.out.owner_withdraw || 0;
        const tillResidual = cashTill?.totals?.real_till_change || 0;
        const apChange = moneyFlow.ap_change || 0;
        const bankNet = moneyFlow.bank_net || 0;

        const apUp = apChange > 0;
        const tillNeg = tillResidual < -50;
        const bankUp = bankNet > 0;
        let verdict, verdictColor;
        if (apUp && tillNeg) {
          verdict = '⚠️ ვალი იზრდება და სალაროდან გვაკლია — გადასამოწმებელია';
          verdictColor = '#ef4444';
        } else if (!apUp && bankUp && inventoryChange >= 0) {
          verdict = '✅ ბიზნესი იზრდება — მოგება ბალანსირებულად ჩაიდო ბანკში და მარაგში';
          verdictColor = '#10b981';
        } else if (apUp || tillNeg) {
          verdict = '🟡 მოგებაა, მაგრამ ფული თაროზე ან ვალში გადადის';
          verdictColor = '#fbbf24';
        } else {
          verdict = 'ℹ️ მონაცემები შერეულია — გადახედე ცალკეულ ციფრს';
          verdictColor = '#94a3b8';
        }

        const rowS = { display: 'flex', justifyContent: 'space-between', padding: '8px 0', alignItems: 'baseline', borderBottom: '1px solid rgba(255,255,255,0.05)', gap: 12 };
        const labelS = { color: '#cbd5e1', fontSize: '0.95rem' };
        const hintS = { color: '#64748b', fontSize: '0.78rem', display: 'block', marginTop: 2 };

        return (
          <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, padding: '18px 20px', marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f1f5f9' }}>
                🎯 თვის შემაჯამე — ფული სად წავიდა
              </h3>
              <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                {fmtDayKa(periodFrom)} → {fmtDayKa(periodTo)} ({moneyFlow.day_count} დღე)
              </div>
            </div>

            <div style={{ marginBottom: 14, padding: '12px 14px', background: 'rgba(16,185,129,0.06)', borderRadius: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 8 }}>
              <span style={{ color: '#94a3b8', fontSize: '0.92rem' }}>წმინდა მოგება (P&L)</span>
              <span style={{ color: profit >= 0 ? '#10b981' : '#ef4444', fontSize: '1.3rem', fontWeight: 700 }}>
                {profit >= 0 ? '+' : ''}{fmtGel2(profit)}
              </span>
            </div>

            <div style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: 8 }}>ფული ფაქტობრივად სად მოექცა:</div>

            <div style={rowS}>
              <div>
                <span style={labelS}>💵 ჯიბეში (შენ აიღე)</span>
                <span style={hintS}>სამეურნეო ხარჯიდან, შიდა გადარიცხვა გამოაკლდა</span>
              </div>
              <span style={{ color: '#fbbf24', fontWeight: 600, fontSize: '1.05rem' }}>
                {ownerPocket > 0 ? '+' : ''}{fmtGel2(ownerPocket)}
              </span>
            </div>

            <div style={rowS}>
              <div>
                <span style={labelS}>📦 საქონელში (თაროზე)</span>
                <span style={hintS}>ნაყიდი ზედნადებები − გაყიდულის COGS</span>
              </div>
              <span style={{ color: inventoryChange > 0 ? '#cbd5e1' : '#10b981', fontWeight: 600, fontSize: '1.05rem' }}>
                {inventoryChange > 0 ? '+' : ''}{fmtGel2(inventoryChange)}
              </span>
            </div>

            <div style={rowS}>
              <div>
                <span style={labelS}>🪙 სალაროებში / უხსნელი</span>
                <span style={hintS}>ნაღდი ფული, ბანკში/ხარჯში ვერ ვიპოვეთ</span>
              </div>
              <span style={{ color: Math.abs(tillResidual) <= 50 ? '#10b981' : '#fbbf24', fontWeight: 600, fontSize: '1.05rem' }}>
                {tillResidual > 0 ? '+' : ''}{fmtGel2(tillResidual)}
              </span>
            </div>

            <div style={rowS}>
              <div>
                <span style={labelS}>📈 ვალში გადადო</span>
                <span style={hintS}>მომწოდებლების ვალის ცვლილება</span>
              </div>
              <span style={{ color: apChange > 0 ? '#ef4444' : '#10b981', fontWeight: 600, fontSize: '1.05rem' }}>
                {apChange > 0 ? '+' : ''}{fmtGel2(apChange)}
              </span>
            </div>

            <div style={{ ...rowS, borderBottom: 'none' }}>
              <div>
                <span style={labelS}>🏦 ბანკში დარჩა</span>
                <span style={hintS}>TBC + BOG ნაშთის ცვლილება</span>
              </div>
              <span style={{ color: bankNet >= 0 ? '#10b981' : '#ef4444', fontWeight: 600, fontSize: '1.05rem' }}>
                {bankNet > 0 ? '+' : ''}{fmtGel2(bankNet)}
              </span>
            </div>

            <div style={{ color: verdictColor, fontSize: '0.98rem', fontWeight: 600, padding: '12px 14px', background: 'rgba(255,255,255,0.04)', borderRadius: 6, marginTop: 14 }}>
              {verdict}
            </div>

            <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: 8, fontStyle: 'italic' }}>
              ⓘ ეს 5 ცხრილი მოგებას 1:1 არ ჯამდება — სხვადასხვა შრე ფინანსური სურათისა. სრული თვისთვის მონიშნე 1-დან 30/31-მდე.
            </div>
          </div>
        );
      })()}

      {/* ----- ZONE 2: Stores comparison table ----- */}
      <div
        style={{
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 12,
          padding: '18px 20px',
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
          <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f1f5f9' }}>
            მაღაზიების შედარება
          </h3>
          <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>{headerLabel}</div>
        </div>

        {rowsToShow.length === 0 ? (
          <div style={{ color: '#94a3b8', textAlign: 'center', padding: '32px 0' }}>
            ამ პერიოდისთვის გაყიდვის მონაცემი არ მოიძებნა.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 600 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8', fontSize: '0.85rem', textAlign: 'right' }}>
                  <th style={{ textAlign: 'left', padding: '8px 6px' }}>მაღაზია</th>
                  <th style={{ padding: '8px 6px' }}>ნაღდი</th>
                  <th style={{ padding: '8px 6px' }}>ბარათი</th>
                  <th style={{ padding: '8px 6px' }}>ჯამი</th>
                  <th style={{ padding: '8px 6px' }}>ჩეკები</th>
                  <th style={{ padding: '8px 6px' }}>საშ. კალათა</th>
                </tr>
              </thead>
              <tbody>
                {rowsToShow.map((r) => {
                  const col = storeColor(r.object);
                  return (
                    <tr key={r.object} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', color: '#e2e8f0' }}>
                      <td style={{ padding: '10px 6px', textAlign: 'left' }}>
                        <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 4, background: col, marginRight: 8, verticalAlign: 'middle' }} />
                        <strong>{r.object}</strong>
                      </td>
                      <td style={{ padding: '10px 6px', textAlign: 'right' }}>{fmtGel2(r.cash)}</td>
                      <td style={{ padding: '10px 6px', textAlign: 'right' }}>{fmtGel2(r.card)}</td>
                      <td style={{ padding: '10px 6px', textAlign: 'right', fontWeight: 600, color: col }}>{fmtGel2(r.revenue)}</td>
                      <td style={{ padding: '10px 6px', textAlign: 'right' }}>{fmtN(r.receipts)}</td>
                      <td style={{ padding: '10px 6px', textAlign: 'right' }}>{fmtGel2(r.aov)}</td>
                    </tr>
                  );
                })}
                {rowsToShow.length > 1 && (
                  <tr style={{ borderTop: '1px solid rgba(255,255,255,0.15)', color: '#f1f5f9', fontWeight: 600 }}>
                    <td style={{ padding: '10px 6px', textAlign: 'left' }}>ჯამი</td>
                    <td style={{ padding: '10px 6px', textAlign: 'right' }}>{fmtGel2(rowsToShow.reduce((a, r) => a + r.cash, 0))}</td>
                    <td style={{ padding: '10px 6px', textAlign: 'right' }}>{fmtGel2(rowsToShow.reduce((a, r) => a + r.card, 0))}</td>
                    <td style={{ padding: '10px 6px', textAlign: 'right' }}>{fmtGel2(rowsToShow.reduce((a, r) => a + r.revenue, 0))}</td>
                    <td style={{ padding: '10px 6px', textAlign: 'right' }}>{fmtN(rowsToShow.reduce((a, r) => a + r.receipts, 0))}</td>
                    <td style={{ padding: '10px 6px', textAlign: 'right' }}>—</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ----- ZONE 3: Today's waybills ----- */}
      <div
        style={{
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 12,
          padding: '18px 20px',
          marginBottom: 24,
        }}
      >
        <div
          onClick={() => setWaybillsExpanded((v) => !v)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setWaybillsExpanded((v) => !v); } }}
          style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: waybillsExpanded ? 14 : 0, flexWrap: 'wrap', gap: 8, cursor: 'pointer', userSelect: 'none' }}
        >
          <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#94a3b8', fontSize: '0.85rem', display: 'inline-block', width: 12, transition: 'transform 0.15s ease', transform: waybillsExpanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
            {periodActive ? 'პერიოდის ზედნადებები' : 'დღევანდელი ზედნადებები'}
          </h3>
          {!waybillsLoading && (
            <div style={{ color: '#94a3b8', fontSize: '0.85rem', display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
              <span>
                {fmtN(regularWaybills.length)} ცალი · ჯამი{' '}
                <strong style={{ color: '#e2e8f0' }}>{fmtGel2(waybillsRegularTotal)}</strong>
              </span>
              {returnWaybills.length > 0 && (
                <span style={{ color: '#ef4444', fontWeight: 600 }}>
                  დაბრუნება: {fmtGel2(waybillsReturnsTotal)} ({fmtN(returnWaybills.length)})
                </span>
              )}
            </div>
          )}
          {waybillsLoading && <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>იტვირთება...</div>}
        </div>

        {waybillsExpanded && waybillsError && (
          <div style={{ color: '#ef4444', padding: '12px 0', fontSize: '0.9rem' }}>
            ზედნადებების ჩატვირთვის შეცდომა: {waybillsError}
          </div>
        )}

        {waybillsExpanded && !waybillsLoading && !waybillsError && waybillsForDate.length === 0 && (
          <div style={{ color: '#94a3b8', textAlign: 'center', padding: '24px 0' }}>
            ამ თარიღით ზედნადები არ მოიძებნა.
          </div>
        )}

        {waybillsExpanded && waybillsForDate.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 540 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8', fontSize: '0.85rem' }}>
                  <th style={{ textAlign: 'left', padding: '8px 6px' }}>დრო</th>
                  <th style={{ textAlign: 'left', padding: '8px 6px' }}>მომწოდებელი</th>
                  <th style={{ textAlign: 'left', padding: '8px 6px' }}>მაღაზია</th>
                  <th style={{ textAlign: 'right', padding: '8px 6px' }}>თანხა</th>
                </tr>
              </thead>
              <tbody>
                {waybillsForDate.slice(0, 25).map((w, i) => {
                  const isReturn = !!w.is_return;
                  const rowColor = isReturn ? '#fca5a5' : '#e2e8f0';
                  return (
                    <tr
                      key={`${w.waybill_number || i}-${w.supplier || ''}`}
                      style={{
                        borderBottom: '1px solid rgba(255,255,255,0.05)',
                        color: rowColor,
                        background: isReturn ? 'rgba(239,68,68,0.06)' : 'transparent',
                      }}
                    >
                      <td style={{ padding: '9px 6px', textAlign: 'left', color: isReturn ? '#fca5a5' : '#94a3b8' }}>
                        {(w.date || '').slice(0, 16)}
                      </td>
                      <td style={{ padding: '9px 6px', textAlign: 'left' }}>
                        {isReturn && <span style={{ color: '#ef4444', marginRight: 6 }}>↩</span>}
                        {w.supplier || '—'}
                      </td>
                      <td style={{ padding: '9px 6px', textAlign: 'left', color: isReturn ? '#fca5a5' : '#94a3b8' }}>
                        {w.store || '—'}
                      </td>
                      <td style={{ padding: '9px 6px', textAlign: 'right', fontWeight: 600, color: isReturn ? '#ef4444' : '#e2e8f0' }}>
                        {fmtGel2(w.effective_amount)}
                      </td>
                    </tr>
                  );
                })}
                {waybillsForDate.length > 25 && (
                  <tr>
                    <td colSpan={4} style={{ padding: '10px 6px', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
                      +{fmtN(waybillsForDate.length - 25)} მეტი · სრული სია „ზედნადებები" გვერდზე
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ----- ZONE 4: Daily money flow ----- */}
      <div
        style={{
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 12,
          padding: '18px 20px',
          marginBottom: 24,
        }}
      >
        <div
          onClick={() => setMoneyFlowExpanded((v) => !v)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setMoneyFlowExpanded((v) => !v); } }}
          style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: moneyFlowExpanded ? 16 : 0, flexWrap: 'wrap', gap: 8, cursor: 'pointer', userSelect: 'none' }}
        >
          <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#94a3b8', fontSize: '0.85rem', display: 'inline-block', width: 12, transition: 'transform 0.15s ease', transform: moneyFlowExpanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
            🏦 ბანკის ფული — შემოვიდა / გავიდა
          </h3>
          {!moneyFlowLoading && moneyFlow && (
            <div style={{ color: '#94a3b8', fontSize: '0.85rem', display: 'flex', alignItems: 'baseline', gap: 14, flexWrap: 'wrap' }}>
              <span style={{ color: '#10b981' }}>↗ შემოვიდა <strong>{fmtGel2(moneyFlow.in.bank_total)}</strong></span>
              <span style={{ color: '#ef4444' }}>↘ გავიდა <strong>{fmtGel2(moneyFlow.out.bank_total)}</strong></span>
              <span style={{ color: moneyFlow.bank_net >= 0 ? '#10b981' : '#ef4444' }}>წმინდა <strong>{fmtGel2(moneyFlow.bank_net)}</strong></span>
              <button
                onClick={(e) => { e.stopPropagation(); setCashExpenseModalOpen(true); }}
                style={{ marginLeft: 'auto', background: '#0ea5e9', color: '#ffffff', border: 'none', borderRadius: 6, padding: '6px 12px', fontSize: '0.85rem', cursor: 'pointer', fontWeight: 500 }}
                title="ნაღდი ხარჯი — ხელფასი, იჯარა, სამეურნეო და ა.შ."
              >
                ➕ ნაღდი ხარჯი ჩამიწერე
              </button>
            </div>
          )}
          {moneyFlowLoading && <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>იტვირთება...</div>}
        </div>

        {!moneyFlowLoading && moneyFlow && Array.isArray(moneyFlow.warnings) && moneyFlow.warnings.length > 0 && (
          <div style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.35)', borderRadius: 8, padding: '10px 14px', marginTop: 10, marginBottom: 6, color: '#fca5a5', fontSize: '0.88rem' }}>
            <div style={{ fontWeight: 600, marginBottom: 6, color: '#fecaca' }}>⚠️ ციფრები ერთმანეთს არ ემთხვევა — გადასამოწმებელია</div>
            {moneyFlow.warnings.slice(0, 5).map((w, i) => (
              <div key={i} style={{ marginTop: 2 }}>· <span style={{ color: '#fbbf24' }}>{w.day}</span> — {w.msg}</div>
            ))}
            {moneyFlow.warnings.length > 5 && (
              <div style={{ marginTop: 4, color: '#94a3b8', fontStyle: 'italic' }}>+ კიდევ {moneyFlow.warnings.length - 5} ანალოგიური</div>
            )}
          </div>
        )}

        {moneyFlowExpanded && moneyFlowError && (
          <div style={{ color: '#ef4444', padding: '12px 0', fontSize: '0.9rem' }}>
            ფულის მოძრაობა ვერ ჩაიტვირთა: {moneyFlowError}
          </div>
        )}

        {moneyFlowExpanded && !moneyFlowError && !moneyFlow && !moneyFlowLoading && (
          <div style={{ color: '#94a3b8', textAlign: 'center', padding: '24px 0' }}>
            ამ თარიღით მონაცემი არ მოიძებნა.
          </div>
        )}

        {moneyFlowExpanded && moneyFlow && (
          <div>
            {/* BANK IN + OUT columns (real bank movement) */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
              {/* BANK IN */}
              <div style={{ background: 'rgba(16,185,129,0.04)', borderRadius: 10, padding: '14px 16px', border: '1px solid rgba(16,185,129,0.15)' }}>
                <div style={{ color: '#10b981', fontSize: '0.95rem', fontWeight: 600, marginBottom: 10 }}>↗ ბანკში შემოვიდა</div>
                {moneyFlow.in.tbc.total > 0 && (
                  <BankExpandableRow
                    bankName="TBC"
                    breakdown={moneyFlow.in.tbc}
                    expanded={moneyFlowPosTbcExpanded}
                    onToggle={() => setMoneyFlowPosTbcExpanded((v) => !v)}
                  />
                )}
                {(moneyFlow.in.bog.total > 0 || moneyFlow.in.foodmart_cashback > 0) && (
                  <BankExpandableRow
                    bankName="BOG"
                    breakdown={moneyFlow.in.bog}
                    cashback={moneyFlow.in.foodmart_cashback}
                    expanded={moneyFlowPosBogExpanded}
                    onToggle={() => setMoneyFlowPosBogExpanded((v) => !v)}
                  />
                )}
                {moneyFlow.in.other.length > 0 && (
                  <FlowRow label={`სხვა (${moneyFlow.in.other.length})`} value={moneyFlow.in.other.reduce((a, r) => a + r.amount, 0)} />
                )}
                <FlowRow label="სულ ბანკში" value={moneyFlow.in.bank_total} bold />
              </div>

              {/* BANK OUT */}
              <div style={{ background: 'rgba(239,68,68,0.04)', borderRadius: 10, padding: '14px 16px', border: '1px solid rgba(239,68,68,0.15)' }}>
                <div style={{ color: '#ef4444', fontSize: '0.95rem', fontWeight: 600, marginBottom: 10 }}>↘ ბანკიდან გავიდა</div>
                <FlowRow label="მომწოდებლები" value={moneyFlow.out.suppliers_total_bank} />
                {moneyFlow.out.salary_bank > 0 && (
                  <OutItemsExpandableRow
                    label="ხელფასი"
                    amount={moneyFlow.out.salary_bank}
                    items={moneyFlow.out.salary_items.filter((it) => it.bank !== 'ნაღდი')}
                    expanded={outCatExpanded.salary}
                    onToggle={() => toggleOutCat('salary')}
                  />
                )}
                {moneyFlow.out.rent_bank > 0 && (
                  <OutItemsExpandableRow
                    label="იჯარა"
                    amount={moneyFlow.out.rent_bank}
                    items={moneyFlow.out.rent_items.filter((it) => it.bank !== 'ნაღდი')}
                    expanded={outCatExpanded.rent}
                    onToggle={() => toggleOutCat('rent')}
                  />
                )}
                {moneyFlow.out.owner_withdraw_bank > 0 && (
                  <OutItemsExpandableRow
                    label="სამეურნეო ხარჯი (შენი)"
                    amount={moneyFlow.out.owner_withdraw_bank}
                    items={moneyFlow.out.owner_withdraw_items.filter((it) => it.bank !== 'ნაღდი')}
                    expanded={outCatExpanded.owner}
                    onToggle={() => toggleOutCat('owner')}
                    expandedNote={moneyFlow.samurneo_internal > 0 ? (
                      <>
                        ⓘ ცხრილში ჯამი {fmtGel2(moneyFlow.out.owner_withdraw_bank + moneyFlow.samurneo_internal)} გამოვა — აქედან <strong>{fmtGel2(moneyFlow.samurneo_internal)}</strong> შიდა გადარიცხვაა (BOG-დან ნაღდად აიღე და TBC-ში დააბრუნე სამეურნეო-დ).<br/>
                        ე.ი. რეალურად შენ მიიღე <strong>{fmtGel2(moneyFlow.out.owner_withdraw_bank)}</strong>.
                      </>
                    ) : null}
                  />
                )}
                {moneyFlow.out.service_bank > 0 && (
                  <OutItemsExpandableRow
                    label="საკომუნალო/მომსახურება"
                    amount={moneyFlow.out.service_bank}
                    items={moneyFlow.out.service_items.filter((it) => it.bank !== 'ნაღდი')}
                    expanded={outCatExpanded.service}
                    onToggle={() => toggleOutCat('service')}
                  />
                )}
                {moneyFlow.out.tax_treasury > 0 && (
                  <FlowRow
                    label={`გადასახადი / ხაზინა${
                      moneyFlow.out.bog.tax_treasury > 0 && moneyFlow.out.tbc.tax_treasury === 0 ? ' (BOG)'
                      : moneyFlow.out.tbc.tax_treasury > 0 && moneyFlow.out.bog.tax_treasury === 0 ? ' (TBC)'
                      : ''
                    }`}
                    value={moneyFlow.out.tax_treasury}
                  />
                )}
                {moneyFlow.out.bank_fees > 0 && (
                  <FlowRow
                    label={`ბანკის საკომისიო${
                      moneyFlow.out.bog.bank_fees > 0 && moneyFlow.out.tbc.bank_fees === 0 ? ' (BOG)'
                      : moneyFlow.out.tbc.bank_fees > 0 && moneyFlow.out.bog.bank_fees === 0 ? ' (TBC)'
                      : ''
                    }`}
                    value={moneyFlow.out.bank_fees}
                  />
                )}
                {moneyFlow.out.refund_bank > 0 && (
                  <OutItemsExpandableRow
                    label="გაუქმება / refund"
                    amount={moneyFlow.out.refund_bank}
                    items={moneyFlow.out.refund_items.filter((it) => it.bank !== 'ნაღდი')}
                    expanded={outCatExpanded.refund}
                    onToggle={() => toggleOutCat('refund')}
                  />
                )}
                {moneyFlow.out.unmatched_suppliers_bank > 0 && (
                  <OutItemsExpandableRow
                    label="მომწოდებლები (ვერ ცნობილი)"
                    amount={moneyFlow.out.unmatched_suppliers_bank}
                    items={moneyFlow.out.unmatched_supplier_items.filter((it) => it.bank !== 'ნაღდი')}
                    expanded={outCatExpanded.unmatched}
                    onToggle={() => toggleOutCat('unmatched')}
                  />
                )}
                {(() => {
                  const bankOther = moneyFlow.out.other.filter((r) => r.bank !== 'ნაღდი');
                  return bankOther.length > 0 && (
                    <OutItemsExpandableRow
                      label="სხვა"
                      amount={bankOther.reduce((a, r) => a + r.amount, 0)}
                      items={bankOther}
                      expanded={outCatExpanded.other}
                      onToggle={() => toggleOutCat('other')}
                    />
                  );
                })()}
                <FlowRow label="სულ ბანკიდან" value={moneyFlow.out.bank_total} bold />
              </div>
            </div>

            {/* Non-bank info — context depends on period selection */}
            {periodActive && moneyFlow.day_count > 1 ? (
              /* Past period summary — "did you make progress this period?" */
              (() => {
                const net = moneyFlow.true_net;
                const apChange = moneyFlow.ap_change;
                const netGood = net > 0;
                const apGood = apChange < 0;
                let verdict = '';
                let verdictColor = '#94a3b8';
                if (netGood && apGood) {
                  verdict = '✅ წახვედი წინ — ფული მეტი დარჩა და ვალიც შემცირდა';
                  verdictColor = '#10b981';
                } else if (netGood && !apGood) {
                  verdict = '🟡 ფული მეტი დარჩა, მაგრამ ვალი გაიზარდა';
                  verdictColor = '#fbbf24';
                } else if (!netGood && apGood) {
                  verdict = '🟡 ფული ნაკლები დარჩა, მაგრამ ვალი მაინც შემცირდა';
                  verdictColor = '#fbbf24';
                } else {
                  verdict = '⚠️ წახვედი უკან — ფული გავიდა მეტი და ვალიც გაიზარდა';
                  verdictColor = '#ef4444';
                }
                const rowStyle = { display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '0.88rem' };
                const subStyle = { ...rowStyle, paddingLeft: 18, fontSize: '0.82rem', color: '#94a3b8' };
                return (
                  <div style={{ marginTop: 14, background: 'rgba(59,130,246,0.04)', borderRadius: 10, padding: '14px 18px', border: '1px solid rgba(59,130,246,0.15)' }}>
                    <div style={{ color: '#60a5fa', fontSize: '0.95rem', fontWeight: 600, marginBottom: 12 }}>📊 სრული ფინანსური სურათი — {moneyFlow.date_label}</div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16, marginBottom: 14 }}>
                      {/* IN column */}
                      <div>
                        <div style={{ color: '#10b981', fontSize: '0.9rem', fontWeight: 600, marginBottom: 8 }}>↗ ფული შემოვიდა</div>
                        <div style={{ ...rowStyle, color: '#cbd5e1' }}>
                          <span>🛒 ნავაჭრი</span><span>{fmtGel2(moneyFlow.true_in_sales)}</span>
                        </div>
                        <div style={subStyle}>
                          <span>ნაღდი</span><span>{fmtGel2(moneyFlow.in.cash_megaplus)}</span>
                        </div>
                        <div style={subStyle}>
                          <span>ბარათით</span><span>{fmtGel2(moneyFlow.in.card_megaplus)}</span>
                        </div>
                        {moneyFlow.true_in_other > 0 && (
                          <>
                            <div style={{ ...rowStyle, color: '#cbd5e1', marginTop: 4 }}>
                              <span>💰 სხვა შემოსავალი</span><span>{fmtGel2(moneyFlow.true_in_other)}</span>
                            </div>
                            {moneyFlow.in.foodmart_cashback > 0 && (
                              <div style={subStyle}>
                                <span>ფუდმარტი ქეშბექი</span><span>{fmtGel2(moneyFlow.in.foodmart_cashback)}</span>
                              </div>
                            )}
                            {((moneyFlow.in.tbc?.samurneo || 0) + (moneyFlow.in.bog?.samurneo || 0)) > 0 && (
                              <div style={subStyle}>
                                <span>სამეურნეო</span><span>{fmtGel2((moneyFlow.in.tbc?.samurneo || 0) + (moneyFlow.in.bog?.samurneo || 0))}</span>
                              </div>
                            )}
                          </>
                        )}
                        <div style={{ ...rowStyle, color: '#10b981', fontWeight: 600, marginTop: 6, borderTop: '1px solid rgba(16,185,129,0.2)', paddingTop: 6 }}>
                          <span>სულ</span><span>{fmtGel2(moneyFlow.true_in)}</span>
                        </div>
                      </div>

                      {/* OUT column */}
                      <div>
                        <div style={{ color: '#ef4444', fontSize: '0.9rem', fontWeight: 600, marginBottom: 8 }}>↘ ფული გავიდა</div>
                        <div style={{ ...rowStyle, color: '#cbd5e1' }}>
                          <span>🏦 ბანკიდან</span><span>{fmtGel2(moneyFlow.true_out_bank)}</span>
                        </div>
                        <div style={subStyle}>
                          <span>აქედან მომწოდებლებზე</span><span>{fmtGel2(moneyFlow.out.suppliers_total_bank)}</span>
                        </div>
                        <div style={subStyle}>
                          <span>აქედან სხვა (ხელფასი, ქირა, გადასახ.)</span><span>{fmtGel2(moneyFlow.true_out_bank - moneyFlow.out.suppliers_total_bank)}</span>
                        </div>
                        {moneyFlow.true_out_cash_journal > 0 && (
                          <div style={{ ...rowStyle, color: '#cbd5e1', marginTop: 4 }}>
                            <span>💵 ნაღდი — მომწოდებლებზე</span><span>{fmtGel2(moneyFlow.true_out_cash_journal)}</span>
                          </div>
                        )}
                        {moneyFlow.true_out_cash_expenses > 0 && (
                          <div style={{ ...rowStyle, color: '#cbd5e1', marginTop: 4 }}>
                            <span>💵 ნაღდი — სხვა ხარჯი (ჟურნალი)</span><span>{fmtGel2(moneyFlow.true_out_cash_expenses)}</span>
                          </div>
                        )}
                        <div style={{ ...rowStyle, color: '#ef4444', fontWeight: 600, marginTop: 6, borderTop: '1px solid rgba(239,68,68,0.2)', paddingTop: 6 }}>
                          <span>სულ</span><span>{fmtGel2(moneyFlow.true_out)}</span>
                        </div>
                      </div>
                    </div>

                    {/* Summary numbers */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 10 }}>
                      <div>
                        <div style={{ color: '#94a3b8', fontSize: '0.82rem', marginBottom: 4 }}>წმინდა ფული (შემოვიდა − გავიდა)</div>
                        <div style={{ color: net >= 0 ? '#10b981' : '#ef4444', fontSize: '1.4rem', fontWeight: 700 }}>
                          {net >= 0 ? '+' : ''}{fmtGel2(net)}
                        </div>
                      </div>
                      <div>
                        <div style={{ color: '#94a3b8', fontSize: '0.82rem', marginBottom: 4 }}>მისაცემი მომწოდებლებზე — ცვლა</div>
                        <div style={{ color: apChange < 0 ? '#10b981' : (apChange > 0 ? '#ef4444' : '#94a3b8'), fontSize: '1.4rem', fontWeight: 700 }}>
                          {apChange > 0 ? '+' : ''}{fmtGel2(apChange)}
                        </div>
                        <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: 2 }}>
                          {fmtGel2(moneyFlow.ap_start)} → {fmtGel2(moneyFlow.ap_end)}
                        </div>
                      </div>
                    </div>
                    <div style={{ color: verdictColor, fontSize: '0.95rem', fontWeight: 600, padding: '10px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 6 }}>
                      {verdict}
                    </div>
                  </div>
                );
              })()
            ) : (
              /* Today / single-day view — what's not yet in bank + manual cash payments */
              <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 14 }}>
                <div style={{ background: 'rgba(251,191,36,0.04)', borderRadius: 10, padding: '12px 14px', border: '1px solid rgba(251,191,36,0.15)' }}>
                  <div style={{ color: '#fbbf24', fontSize: '0.9rem', fontWeight: 600, marginBottom: 8 }}>💰 დღევანდელი გაყიდვა (ჯერ არ ბანკშია)</div>
                  <FlowRow label="სალარო ნაღდი" value={moneyFlow.in.cash_megaplus} hint="სალაროში დევს" size="small" />
                  <FlowRow label="ბარათით გაყიდვა" value={moneyFlow.in.card_megaplus} hint="ბანკში იმავე დღეს" size="small" />
                </div>
                {moneyFlow.out.cash_journal_total > 0 && (
                  <div style={{ background: 'rgba(251,191,36,0.04)', borderRadius: 10, padding: '12px 14px', border: '1px solid rgba(251,191,36,0.15)' }}>
                    <div style={{ color: '#fbbf24', fontSize: '0.9rem', fontWeight: 600, marginBottom: 8 }}>📝 ნაღდი გადახდები (ჟურნალი)</div>
                    <FlowRow label="მომწოდებლებზე ხელით გადახდილი" value={moneyFlow.out.cash_journal_total} hint="ნაღდი, ბანკიდან არ გასულა" size="small" />
                  </div>
                )}
              </div>
            )}

            {/* Suppliers detail — expandable */}
            {moneyFlow.out.suppliers_list.length > 0 && (
              <div style={{ marginTop: 14, padding: '12px 16px', background: 'rgba(255,255,255,0.02)', borderRadius: 10 }}>
                <div
                  onClick={() => setMoneyFlowSuppliersExpanded((v) => !v)}
                  role="button"
                  tabIndex={0}
                  style={{ cursor: 'pointer', userSelect: 'none', color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}
                >
                  <span style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'inline-block', width: 10, transition: 'transform 0.15s ease', transform: moneyFlowSuppliersExpanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
                  მომწოდებლების სია — {moneyFlow.out.suppliers_list.length} მომწოდებელი
                </div>
                {moneyFlowSuppliersExpanded && (
                  <div style={{ overflowX: 'auto', marginTop: 12 }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 700 }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8', fontSize: '0.85rem' }}>
                          <th style={{ textAlign: 'left', padding: '6px 6px' }}>მომწოდებელი</th>
                          <th style={{ textAlign: 'left', padding: '6px 6px' }}>ბანკი</th>
                          <th style={{ textAlign: 'right', padding: '6px 6px' }}>ბანკით</th>
                          <th style={{ textAlign: 'right', padding: '6px 6px' }}>ხელით</th>
                          <th style={{ textAlign: 'right', padding: '6px 6px' }}>დაბრუნება</th>
                          <th style={{ textAlign: 'right', padding: '6px 6px' }}>იყო</th>
                          <th style={{ textAlign: 'right', padding: '6px 6px' }}>დარჩა</th>
                        </tr>
                      </thead>
                      <tbody>
                        {moneyFlow.out.suppliers_list.slice(0, 50).map((s) => {
                          const tbc = s.amount_bank_tbc || 0;
                          const bog = s.amount_bank_bog || 0;
                          const bankBadge = tbc > 0 && bog > 0
                            ? <span><span style={{ background: 'rgba(59,130,246,0.18)', color: '#60a5fa', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem', marginRight: 4 }}>TBC</span><span style={{ background: 'rgba(249,115,22,0.18)', color: '#fb923c', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem' }}>BOG</span></span>
                            : tbc > 0
                              ? <span style={{ background: 'rgba(59,130,246,0.18)', color: '#60a5fa', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem' }}>TBC</span>
                              : bog > 0
                                ? <span style={{ background: 'rgba(249,115,22,0.18)', color: '#fb923c', padding: '1px 6px', borderRadius: 4, fontSize: '0.75rem' }}>BOG</span>
                                : <span style={{ color: '#475569', fontSize: '0.75rem' }}>—</span>;
                          return (
                          <tr key={s.tax_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', color: '#e2e8f0' }}>
                            <td style={{ padding: '7px 6px', textAlign: 'left' }}>{s.supplier_name || s.tax_id}</td>
                            <td style={{ padding: '7px 6px', textAlign: 'left' }}>{bankBadge}</td>
                            <td style={{ padding: '7px 6px', textAlign: 'right', color: s.amount_bank > 0 ? '#e2e8f0' : '#64748b' }}>
                              {s.amount_bank > 0 ? fmtGel2(s.amount_bank) : '—'}
                            </td>
                            <td style={{ padding: '7px 6px', textAlign: 'right', color: s.amount_manual > 0 ? '#fbbf24' : '#64748b' }}>
                              {s.amount_manual > 0 ? fmtGel2(s.amount_manual) : '—'}
                            </td>
                            <td style={{ padding: '7px 6px', textAlign: 'right', color: s.returns_today !== 0 ? '#ef4444' : '#64748b' }}>
                              {s.returns_today !== 0 ? fmtGel2(s.returns_today) : '—'}
                            </td>
                            <td style={{ padding: '7px 6px', textAlign: 'right', color: '#94a3b8' }}>{fmtGel2(s.ap_before)}</td>
                            <td style={{ padding: '7px 6px', textAlign: 'right', color: s.ap_after > 0 ? '#fbbf24' : '#10b981', fontWeight: 600 }}>
                              {fmtGel2(s.ap_after)}
                            </td>
                          </tr>
                          );
                        })}
                        {moneyFlow.out.suppliers_list.length > 50 && (
                          <tr><td colSpan={7} style={{ padding: '8px 6px', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>+{moneyFlow.out.suppliers_list.length - 50} მეტი</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Internal + info */}
            <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
              <div style={{ background: 'rgba(148,163,184,0.04)', borderRadius: 10, padding: '12px 14px', border: '1px solid rgba(148,163,184,0.15)' }}>
                <div style={{ color: '#94a3b8', fontSize: '0.9rem', fontWeight: 600, marginBottom: 8 }}>🔁 შიდა მოძრაობა</div>
                <FlowRow label="ანგარიშებს შორის" value={moneyFlow.internal.own_bank_transfers} size="small" />
                {moneyFlow.internal.cash_to_bank > 0 && (
                  <FlowRow label="სალაროდან ბანკში" value={moneyFlow.internal.cash_to_bank} size="small" />
                )}
                {moneyFlow.samurneo_internal > 0 && (
                  <FlowRow label="BOG → TBC (სამეურნეო ნაღდით)" value={moneyFlow.samurneo_internal} size="small" />
                )}
              </div>
              <div style={{ background: 'rgba(59,130,246,0.04)', borderRadius: 10, padding: '12px 14px', border: '1px solid rgba(59,130,246,0.15)' }}>
                <div style={{ color: '#60a5fa', fontSize: '0.9rem', fontWeight: 600, marginBottom: 8 }}>📦 დღის ზედნადებები (ვალის ცვლა)</div>
                <FlowRow label={`შემოვიდა ${fmtN(moneyFlow.info.waybills_regular_count)} ცალი`} value={moneyFlow.info.waybills_regular_total} size="small" />
                {moneyFlow.info.waybills_returns_count > 0 && (
                  <FlowRow label={`დაბრუნება ${fmtN(moneyFlow.info.waybills_returns_count)} ცალი`} value={moneyFlow.info.waybills_returns_total} size="small" danger />
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Cash expense modal */}
      {cashExpenseModalOpen && (
        <div
          onClick={() => setCashExpenseModalOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ background: '#0f172a', borderRadius: 12, padding: '24px 28px', width: 'min(440px, 92vw)', border: '1px solid #334155' }}
          >
            <h3 style={{ margin: '0 0 16px 0', color: '#f1f5f9', fontSize: '1.05rem' }}>➕ ნაღდი ხარჯი ჩამიწერე</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>კატეგორია</span>
                <select
                  value={cashExpenseForm.category}
                  onChange={(e) => setCashExpenseForm({ ...cashExpenseForm, category: e.target.value })}
                  style={{ padding: '8px 10px', background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 6, fontSize: '0.95rem' }}
                >
                  <option value="salary">ხელფასი</option>
                  <option value="rent">იჯარა</option>
                  <option value="owner">სამეურნეო (პერსონალური)</option>
                  <option value="service">საკომუნალო / მომსახურება</option>
                  <option value="supplier_cash">ნაღდი მომწოდებელი</option>
                  <option value="other">სხვა</option>
                </select>
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>თანხა (₾)</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={cashExpenseForm.amount}
                  onChange={(e) => setCashExpenseForm({ ...cashExpenseForm, amount: e.target.value })}
                  placeholder="მაგ. 3200"
                  style={{ padding: '8px 10px', background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 6, fontSize: '0.95rem' }}
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>თარიღი</span>
                <input
                  type="date"
                  value={cashExpenseForm.date}
                  onChange={(e) => setCashExpenseForm({ ...cashExpenseForm, date: e.target.value })}
                  style={{ padding: '8px 10px', background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 6, fontSize: '0.95rem' }}
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>კომენტარი</span>
                <input
                  type="text"
                  value={cashExpenseForm.comment}
                  onChange={(e) => setCashExpenseForm({ ...cashExpenseForm, comment: e.target.value })}
                  placeholder="მაგ. დვაბზუ აპრილი"
                  style={{ padding: '8px 10px', background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 6, fontSize: '0.95rem' }}
                />
              </label>
              {cashExpenseStatus && (
                <div style={{ color: cashExpenseStatus.startsWith('✓') ? '#10b981' : '#ef4444', fontSize: '0.88rem' }}>
                  {cashExpenseStatus}
                </div>
              )}
              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
                <button
                  onClick={() => { setCashExpenseModalOpen(false); setCashExpenseStatus(''); }}
                  style={{ background: '#334155', color: '#cbd5e1', border: 'none', borderRadius: 6, padding: '8px 14px', cursor: 'pointer', fontSize: '0.9rem' }}
                >
                  გაუქმება
                </button>
                <button
                  onClick={async () => {
                    const amt = Number(cashExpenseForm.amount);
                    if (!amt || amt <= 0) {
                      setCashExpenseStatus('თანხა > 0 უნდა იყოს');
                      return;
                    }
                    try {
                      const res = await fetch('/api/cash-expenses', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                          category: cashExpenseForm.category,
                          amount: amt,
                          date: cashExpenseForm.date,
                          comment: cashExpenseForm.comment,
                        }),
                      });
                      if (res.ok) {
                        setCashExpenseStatus('✓ ჩაიწერა — შემდეგი მონაცემთა განახლების შემდეგ ცხრილში გამოჩნდება');
                        setCashExpenseForm({ category: 'salary', amount: '', date: new Date().toISOString().slice(0, 10), comment: '' });
                        loadCashExpenseEntries();
                      } else {
                        const err = await res.json().catch(() => ({}));
                        setCashExpenseStatus('შეცდომა: ' + (err.detail || res.status));
                      }
                    } catch (e) {
                      setCashExpenseStatus('სერვერთან კავშირი ვერ მოხერხდა');
                    }
                  }}
                  style={{ background: '#0ea5e9', color: '#ffffff', border: 'none', borderRadius: 6, padding: '8px 14px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500 }}
                >
                  ჩაწერა
                </button>
              </div>

              {/* Existing entries list */}
              {cashExpenseEntries.length > 0 && (
                <div style={{ marginTop: 18, borderTop: '1px solid #334155', paddingTop: 14 }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: 8 }}>
                    უკვე ჩაწერილი ({cashExpenseEntries.length})
                  </div>
                  <div style={{ maxHeight: 240, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {cashExpenseEntries.slice().sort((a, b) => (b.date || '').localeCompare(a.date || '')).map((e) => {
                      const catLabel = {
                        salary: 'ხელფასი',
                        rent: 'იჯარა',
                        owner: 'პერსონალური',
                        service: 'მომსახ.',
                        supplier_cash: 'მომწოდ.',
                        other: 'სხვა',
                      }[e.category] || e.category;
                      return (
                        <div key={e.id} style={{
                          display: 'flex', alignItems: 'center', gap: 8,
                          background: '#1e293b', padding: '8px 10px', borderRadius: 6,
                          fontSize: '0.85rem', color: '#cbd5e1',
                        }}>
                          <span style={{ color: '#94a3b8', minWidth: 78 }}>{e.date}</span>
                          <span style={{ minWidth: 78, color: '#fbbf24' }}>{catLabel}</span>
                          <span style={{ flex: 1, fontWeight: 600 }}>{Number(e.amount).toFixed(2)} ₾</span>
                          <span style={{ flex: 2, color: '#64748b', fontSize: '0.78rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {e.comment || ''}
                          </span>
                          <button
                            onClick={async () => {
                              if (!window.confirm(`წაშალე ეს ჩანაწერი?\n${e.date} ${catLabel} ${Number(e.amount).toFixed(2)} ₾`)) return;
                              try {
                                const r = await fetch(`/api/cash-expenses/${e.id}`, { method: 'DELETE' });
                                if (r.ok) {
                                  setCashExpenseStatus('✓ წაიშალა — შემდეგი მონაცემთა განახლების შემდეგ ცხრილში გამოჩნდება');
                                  loadCashExpenseEntries();
                                } else {
                                  setCashExpenseStatus('წაშლა ვერ მოხერხდა');
                                }
                              } catch (err) {
                                setCashExpenseStatus('სერვერთან კავშირი ვერ მოხერხდა');
                              }
                            }}
                            style={{
                              background: 'transparent', color: '#ef4444', border: '1px solid #ef4444',
                              borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: '0.8rem',
                            }}
                            title="წაშლა"
                          >
                            ✕
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
