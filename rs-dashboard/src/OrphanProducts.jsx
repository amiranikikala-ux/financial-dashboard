import { useMemo, useState } from 'react';
import { fetchApiJson } from './lib/api.js';

const NUM = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 0 });
const NUM2 = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 2 });
const fmtNum = (v) => (Number.isFinite(Number(v)) ? NUM.format(Number(v)) : '—');
const fmtMoney = (v) => (Number.isFinite(Number(v)) ? `${NUM2.format(Number(v))} ₾` : '—');

const STORE_COLOR = {
  დვაბზუ: '#a855f7',
  ოზურგეთი: '#3b82f6',
};

const RESOLUTION_LABEL = {
  resolved_single: 'ცნობილი',
  multi_candidate: '2+ ვარიანტი',
  no_match: 'უცნობი',
};

const RESOLUTION_COLOR = {
  resolved_single: '#22c55e',
  multi_candidate: '#f59e0b',
  no_match: '#ef4444',
};


function SummaryCard({ label, value, accent, sub }) {
  return (
    <div style={{
      padding: 14, background: '#1e293b', border: '1px solid #334155',
      borderRadius: 8, minWidth: 180, flex: '1 1 180px',
    }}>
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>{label}</div>
      <div style={{
        fontSize: 26, fontWeight: 700, color: accent || '#e2e8f0',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}


export default function OrphanProducts({ orphanProducts }) {
  const op = orphanProducts;

  const [storeFilter, setStoreFilter] = useState('all');
  const [resolutionFilter, setResolutionFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('active');
  const [search, setSearch] = useState('');
  const [pendingKey, setPendingKey] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  // Local override map so toggles take effect without a pipeline run.
  // Key = "store::product_id"; value = "ignored" | "active" (replaces row.user_status)
  const [overrides, setOverrides] = useState({});

  const rows = useMemo(() => {
    if (!op?.rows) return [];
    return op.rows.map((r) => {
      const key = `${r.store}::${r.product_id}`;
      const overridden = overrides[key];
      return overridden ? { ...r, user_status: overridden } : r;
    });
  }, [op?.rows, overrides]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (storeFilter !== 'all' && r.store !== storeFilter) return false;
      if (resolutionFilter !== 'all' && r.resolution_bucket !== resolutionFilter) return false;
      if (statusFilter !== 'all' && r.user_status !== statusFilter) return false;
      if (q) {
        const hay = `${r.product_name || ''} ${r.best_supplier_name || ''} ${r.barcode || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [rows, storeFilter, resolutionFilter, statusFilter, search]);

  const liveCounts = useMemo(() => {
    let active = 0, ignored = 0;
    let activeRev = 0, ignoredRev = 0;
    for (const r of rows) {
      if (r.user_status === 'ignored') {
        ignored += 1;
        ignoredRev += Number(r.lifetime_revenue_ge || 0);
      } else {
        active += 1;
        activeRev += Number(r.lifetime_revenue_ge || 0);
      }
    }
    return { active, ignored, activeRev, ignoredRev };
  }, [rows]);

  if (!op || !op.summary) {
    return (
      <div style={{ padding: 24, color: '#94a3b8' }}>
        <h2 style={{ color: '#e2e8f0', marginBottom: 12 }}>⚠️ შეუსაბამო პროდუქცია</h2>
        <p>მონაცემი ჯერ არ აიგო. გაუშვი pipeline.</p>
      </div>
    );
  }

  async function toggleIgnored(row) {
    const key = `${row.store}::${row.product_id}`;
    const becomeIgnored = row.user_status !== 'ignored';
    setPendingKey(key);
    setErrorMsg(null);
    try {
      await fetchApiJson('/api/orphan-products/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          store: row.store,
          product_id: row.product_id,
          ignored: becomeIgnored,
        }),
      });
      setOverrides((prev) => ({ ...prev, [key]: becomeIgnored ? 'ignored' : 'active' }));
    } catch (err) {
      setErrorMsg(`ვერ შეინახა: ${err?.message || err}`);
    } finally {
      setPendingKey(null);
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h2 style={{ color: '#e2e8f0', marginBottom: 6 }}>
        ⚠️ შეუსაბამო პროდუქცია
      </h2>
      <p style={{ color: '#94a3b8', marginTop: 0, marginBottom: 16, fontSize: 14 }}>
        პროდუქტები რომლებსაც MegaPlus-ში მომწოდებელი არ უწერია.
        ცხრილის გვერდით რომელი ფირმა შეიძლება იყოს — მხოლოდ ვარაუდი.
        როცა MegaPlus-ში გაასწორებ, მომდევნო განახლების შემდეგ სიიდან გაქრება.
      </p>

      {/* Summary cards */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
        <SummaryCard
          label="სულ შეუსაბამო"
          value={fmtNum(op.summary.total_count)}
          sub={fmtMoney(op.summary.total_revenue_ge)}
        />
        <SummaryCard
          label="ცნობილი მომწოდებელი"
          value={fmtNum(op.summary.by_resolution.resolved_single)}
          accent="#22c55e"
        />
        <SummaryCard
          label="2+ ვარიანტი"
          value={fmtNum(op.summary.by_resolution.multi_candidate)}
          accent="#f59e0b"
        />
        <SummaryCard
          label="უცნობი"
          value={fmtNum(op.summary.by_resolution.no_match)}
          accent="#ef4444"
        />
        <SummaryCard
          label="უგულებელყოფილი"
          value={fmtNum(liveCounts.ignored)}
          accent="#64748b"
          sub={fmtMoney(liveCounts.ignoredRev)}
        />
      </div>

      {/* Filters */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 14,
        padding: 12, background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8,
      }}>
        <FilterSelect label="მაღაზია" value={storeFilter} onChange={setStoreFilter} options={[
          { value: 'all', label: 'ყველა' },
          { value: 'დვაბზუ', label: 'დვაბზუ' },
          { value: 'ოზურგეთი', label: 'ოზურგეთი' },
        ]} />
        <FilterSelect label="მომწოდებელი" value={resolutionFilter} onChange={setResolutionFilter} options={[
          { value: 'all', label: 'ყველა' },
          { value: 'resolved_single', label: 'ცნობილი' },
          { value: 'multi_candidate', label: '2+ ვარიანტი' },
          { value: 'no_match', label: 'უცნობი' },
        ]} />
        <FilterSelect label="სტატუსი" value={statusFilter} onChange={setStatusFilter} options={[
          { value: 'active', label: 'გასასწორებელი' },
          { value: 'ignored', label: 'უგულებელყოფილი' },
          { value: 'all', label: 'ყველა' },
        ]} />
        <div style={{ flex: '1 1 200px', minWidth: 200 }}>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>ძიება</div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="პროდუქტი / ფირმა / ბარკოდი"
            style={{
              width: '100%', padding: '6px 10px',
              background: '#1e293b', color: '#e2e8f0',
              border: '1px solid #334155', borderRadius: 6,
              fontSize: 14,
            }}
          />
        </div>
      </div>

      {errorMsg && (
        <div style={{
          padding: 10, marginBottom: 12, borderRadius: 6,
          background: '#7f1d1d', color: '#fee2e2', fontSize: 13,
        }}>
          {errorMsg}
        </div>
      )}

      <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 8 }}>
        ნაჩვენებია <b style={{ color: '#e2e8f0' }}>{fmtNum(filtered.length)}</b> /
        {' '}{fmtNum(rows.length)} ცალი
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto', border: '1px solid #1e293b', borderRadius: 8 }}>
        <table style={{
          width: '100%', borderCollapse: 'collapse', fontSize: 13,
          background: '#0f172a', color: '#e2e8f0',
        }}>
          <thead>
            <tr style={{ background: '#1e293b', textAlign: 'left' }}>
              <th style={th}>მაღაზია</th>
              <th style={th}>პროდუქტი</th>
              <th style={{ ...th, textAlign: 'right' }}>გაყიდვა</th>
              <th style={th}>ვინ ვვარაუდობთ</th>
              <th style={{ ...th, textAlign: 'center' }}>მოქმედება</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 500).map((r) => {
              const key = `${r.store}::${r.product_id}`;
              const isIgnored = r.user_status === 'ignored';
              const pending = pendingKey === key;
              return (
                <tr key={key} style={{
                  borderTop: '1px solid #1e293b',
                  background: isIgnored ? '#0b1220' : 'transparent',
                  opacity: isIgnored ? 0.6 : 1,
                }}>
                  <td style={td}>
                    <span style={{
                      display: 'inline-block', padding: '2px 8px', borderRadius: 12,
                      fontSize: 11, color: '#fff',
                      background: STORE_COLOR[r.store] || '#475569',
                    }}>{r.store}</span>
                  </td>
                  <td style={td}>
                    <div style={{ fontWeight: 500 }}>{r.product_name || '—'}</div>
                    <div style={{ fontSize: 11, color: '#64748b' }}>
                      {r.barcode ? `ბარკოდი: ${r.barcode}` : ''}
                      {r.last_sale_at ? `  ·  ბოლო: ${r.last_sale_at}` : ''}
                    </div>
                  </td>
                  <td style={{ ...td, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {fmtMoney(r.lifetime_revenue_ge)}
                    <div style={{ fontSize: 11, color: '#64748b' }}>
                      {fmtNum(r.sale_lines)} ჯერ
                    </div>
                  </td>
                  <td style={td}>
                    {r.best_supplier_name ? (
                      <>
                        <div style={{ fontWeight: 500 }}>{r.best_supplier_name}</div>
                        <div style={{ fontSize: 11 }}>
                          <span style={{
                            color: RESOLUTION_COLOR[r.resolution_bucket],
                          }}>
                            ● {RESOLUTION_LABEL[r.resolution_bucket] || r.resolution_bucket}
                          </span>
                          {r.best_tin ? <span style={{ color: '#64748b' }}>  ·  ს/კ {r.best_tin}</span> : null}
                        </div>
                      </>
                    ) : (
                      <span style={{ color: RESOLUTION_COLOR.no_match }}>● უცნობი</span>
                    )}
                  </td>
                  <td style={{ ...td, textAlign: 'center' }}>
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() => toggleIgnored(r)}
                      style={{
                        padding: '6px 12px', borderRadius: 6, fontSize: 12,
                        cursor: pending ? 'wait' : 'pointer',
                        border: '1px solid ' + (isIgnored ? '#475569' : '#dc2626'),
                        background: isIgnored ? '#1e293b' : '#7f1d1d',
                        color: isIgnored ? '#cbd5e1' : '#fee2e2',
                      }}
                    >
                      {pending ? '...' : isIgnored ? '↩ დააბრუნე' : 'უგულებელყოფა'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length > 500 && (
          <div style={{
            padding: 12, fontSize: 13, color: '#94a3b8',
            background: '#1e293b', borderTop: '1px solid #334155',
          }}>
            სიის შემცირება — ფილტრი ან ძიება გამოიყენე. (ჯერ ნაჩვენები პირველი 500)
          </div>
        )}
      </div>
    </div>
  );
}


function FilterSelect({ label, value, onChange, options }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>{label}</div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: '6px 10px', background: '#1e293b', color: '#e2e8f0',
          border: '1px solid #334155', borderRadius: 6, fontSize: 14,
          cursor: 'pointer',
        }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}


const th = {
  padding: '10px 12px', fontWeight: 600, fontSize: 12,
  textTransform: 'uppercase', letterSpacing: '0.04em',
  color: '#94a3b8',
};

const td = {
  padding: '10px 12px', verticalAlign: 'top',
};
