import { useMemo, useState } from 'react';

const NUM = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 0 });
const NUM2 = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 2 });
const fmtNum = (v) => (Number.isFinite(Number(v)) ? NUM.format(Number(v)) : '—');
const fmtMoney = (v) => (Number.isFinite(Number(v)) ? `${NUM2.format(Number(v))} ₾` : '—');

const STORE_COLOR = {
  დვაბზუ: '#a855f7',
  ოზურგეთი: '#3b82f6',
  '—': '#64748b',
};

const CATEGORY_META = {
  missing: {
    label: '🔴 არ მიღებული',
    color: '#ef4444',
    desc: 'რს.გე-ზე აქტიურია, MegaPlus-ში არ მიგიღია — საქონელი ან მიიღო, ან გააუქმვინე მომწოდებელს',
  },
  wrong_store: {
    label: '🔄 არასწორი მაღაზია',
    color: '#ec4899',
    desc: 'რს.გე-ზე ერთ მაღაზიას არის გამოწერილი, MegaPlus-ში სხვა მაღაზიამ მიიღო (ან ორივემ მიიღო) — ოპერატორმა drop-down-ში არასწორი მაღაზია აირჩია',
  },
  amount_mismatch: {
    label: '🟠 ფასების სხვაობა',
    color: '#f59e0b',
    desc: 'რს.გე-ზე ერთი თანხა, MegaPlus-ში სხვა — დააფიქსირე რომელია სწორი',
  },
  ghost_ap: {
    label: '👻 GHOST AP',
    color: '#8b5cf6',
    desc: 'MegaPlus-ში მიიღე, მაგრამ მომწოდებელმა მერე გააუქმა რს.გე-ზე — პრობლემური ფაქტურა',
  },
  returns_not_recorded: {
    label: '🟡 დაბრუნება არ ჩაიწერა',
    color: '#eab308',
    desc: 'რს.გე-ზე გააფორმე დაბრუნება, MegaPlus-ში არ ასახე',
  },
  sub_waybills_not_recorded: {
    label: '🟡 ქვე-ზედნადები',
    color: '#ca8a04',
    desc: 'რს.გე-ზე ქვე-ზედნადები (მაგ: 0789696472/6), MegaPlus-ში არ ფიქსირდება',
  },
  possible_replacements: {
    label: '⚠️ შესაძლოა ჩანაცვლება',
    color: '#06b6d4',
    desc: 'იმავე მომწოდებელს ±14 დღეში სხვა ნომრით აქვს მსგავსი თანხის შეძენა — სავარაუდოდ ჩანაცვლება, ხელით გადაამოწმე',
  },
  rs_data_stale: {
    label: '🆕 რს.გე ფაილი ძველია',
    color: '#10b981',
    desc: 'MegaPlus-ში მიიღე, მაგრამ რს.გე-ის ფაილში არ ჩანს — ჩამოტვირთე ახალი რს.გე ექსპორტი',
  },
};

function SummaryCard({ label, value, sub, accent }) {
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
        {fmtNum(value)}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: '#64748b', marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function ProblemSection({ rows, category, supplierFilter, storeFilter, hideIfkli }) {
  const meta = CATEGORY_META[category];
  const filtered = useMemo(() => {
    return (rows || [])
      .filter((r) => supplierFilter === 'all' || r.tax_id === supplierFilter || r.rs_tax_id === supplierFilter)
      .filter((r) => {
        if (storeFilter === 'all') return true;
        const s = r.store_id || r.matched_get_store;
        if (Array.isArray(r.stores)) return r.stores.includes(storeFilter);
        return s === storeFilter;
      })
      .filter((r) => {
        if (!hideIfkli) return true;
        const name = (r.supplier_name || r.rs_supplier_name || '').toLowerCase();
        return !name.includes('იფქლი');
      });
  }, [rows, supplierFilter, storeFilter, hideIfkli]);

  if (!filtered.length) {
    return (
      <details style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, marginBottom: 12, padding: 12 }}>
        <summary style={{ cursor: 'pointer', color: '#64748b', fontSize: 13 }}>
          {meta.label} — 0 ხაზი ფილტრის შემდეგ
        </summary>
      </details>
    );
  }

  return (
    <details open={category === 'missing' || category === 'wrong_store' || category === 'amount_mismatch' || category === 'ghost_ap'}
             style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, marginBottom: 12 }}>
      <summary style={{
        padding: 14, cursor: 'pointer', listStyle: 'none', userSelect: 'none',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600, color: meta.color }}>
            {meta.label} <span style={{ color: '#94a3b8', fontWeight: 400, marginLeft: 8 }}>({fmtNum(filtered.length)} ხაზი)</span>
          </div>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>{meta.desc}</div>
        </div>
      </summary>

      <div style={{ overflowX: 'auto', borderTop: '1px solid #334155' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead style={{ background: '#0f172a' }}>
            <tr>
              <th style={thStyle}>{category === 'wrong_store' ? 'რს.გე მაღაზია' : 'მაღაზია'}</th>
              {category === 'wrong_store' && (
                <th style={thStyle}>MegaPlus მიიღო</th>
              )}
              <th style={thStyle}>ზედნადები</th>
              <th style={thStyle}>მომწოდებელი</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>თანხა</th>
              {(category === 'amount_mismatch' || category === 'ghost_ap') && (
                <th style={{ ...thStyle, textAlign: 'right' }}>MegaPlus თანხა</th>
              )}
              {category === 'amount_mismatch' && (
                <th style={{ ...thStyle, textAlign: 'right' }}>სხვაობა</th>
              )}
              {category === 'wrong_store' && (
                <th style={thStyle}>შემთხვევა</th>
              )}
              {category === 'possible_replacements' && (
                <>
                  <th style={thStyle}>MegaPlus ნომერი</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>MegaPlus თანხა</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>დღე</th>
                </>
              )}
              <th style={thStyle}>თარიღი</th>
              <th style={thStyle}>ტიპი</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, idx) => {
              const storeName = r.store_name || (Array.isArray(r.store_names) ? r.store_names.join(', ') : '—');
              const storeColor = STORE_COLOR[storeName] || '#cbd5e1';
              const zed = r.zed || r.rs_zed || '—';
              const supplier = r.supplier_name || r.rs_supplier_name || '—';
              const amount = r.amount ?? r.rs_amount ?? 0;
              const mpAmount = r.get_total ?? r.gacera_total;
              const diff = mpAmount != null ? amount - mpAmount : null;
              const receivedNames = Array.isArray(r.received_store_names) ? r.received_store_names.join(' + ') : '—';
              const wrongKindLabel = r.kind === 'duplicate' ? 'ორივე მაღაზიამ მიიღო' : 'მხოლოდ სხვა მაღაზიამ';
              const wrongKindColor = r.kind === 'duplicate' ? '#f59e0b' : '#ec4899';

              return (
                <tr key={`${zed}-${idx}`} style={{ borderTop: '1px solid #1e293b' }}>
                  <td style={{ ...tdStyle, color: storeColor, fontWeight: 600 }}>{storeName}</td>
                  {category === 'wrong_store' && (
                    <td style={{ ...tdStyle, color: '#22d3ee', fontWeight: 600 }}>{receivedNames}</td>
                  )}
                  <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: 11, color: '#94a3b8' }}>{zed}</td>
                  <td style={tdStyle}>{supplier}</td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: amount < 0 ? '#f87171' : '#e2e8f0' }}>
                    {fmtMoney(amount)}
                  </td>
                  {(category === 'amount_mismatch' || category === 'ghost_ap') && (
                    <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#fbbf24' }}>
                      {fmtMoney(mpAmount)}
                    </td>
                  )}
                  {category === 'amount_mismatch' && (
                    <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#f87171', fontWeight: 600 }}>
                      {diff != null ? fmtMoney(Math.abs(diff)) : '—'}
                    </td>
                  )}
                  {category === 'wrong_store' && (
                    <td style={{ ...tdStyle, color: wrongKindColor, fontWeight: 600 }}>{wrongKindLabel}</td>
                  )}
                  {category === 'possible_replacements' && (
                    <>
                      <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: 11, color: '#22d3ee' }}>{r.matched_get_zed}</td>
                      <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#22d3ee' }}>{fmtMoney(r.matched_get_amount)}</td>
                      <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: r.days_offset >= 0 ? '#10b981' : '#fbbf24' }}>
                        {r.days_offset >= 0 ? `+${r.days_offset}` : r.days_offset}
                      </td>
                    </>
                  )}
                  <td style={{ ...tdStyle, color: '#94a3b8' }}>{r.act_date || r.rs_date || r.matched_get_date || '—'}</td>
                  <td style={{ ...tdStyle, color: '#64748b', fontSize: 11 }}>{r.type || ''}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export default function WaybillReconciliation({ data }) {
  const wr = data?.waybill_reconciliation;

  const [supplierFilter, setSupplierFilter] = useState('all');
  const [storeFilter, setStoreFilter] = useState('all');
  const [hideIfkli, setHideIfkli] = useState(false);

  if (!wr || !wr.totals) {
    return (
      <div style={{ padding: 24, color: '#94a3b8' }}>
        <h1 style={{ color: '#e2e8f0', marginTop: 0 }}>ზედნადებების შემოწმება</h1>
        <p>მონაცემი ჯერ არ არის — pipeline-ის შემდეგი გაშვების მერე გამოჩნდება.</p>
      </div>
    );
  }

  const t = wr.totals;
  const totalProblems = (t.missing || 0) + (t.wrong_store || 0) + (t.amount_mismatch || 0) + (t.ghost_ap || 0) + (t.returns_not_recorded || 0) + (t.sub_waybills_not_recorded || 0);

  const supplierOptions = useMemo(() => {
    return (wr.by_supplier || []).map((s) => ({
      value: s.tax_id || s.supplier_name,
      label: `${s.supplier_name} (${s.total_count})`,
    }));
  }, [wr.by_supplier]);

  return (
    <div style={{ padding: 20, color: '#e2e8f0' }}>
      <h1 style={{ marginTop: 0, marginBottom: 8 }}>ზედნადებების შემოწმება</h1>
      <p style={{ color: '#94a3b8', marginTop: 0, marginBottom: 20, maxWidth: 900 }}>
        რს.გე-ის ყველა აქტიური ზედნადები MegaPlus-ის GET ცხრილს უნდა ემთხვეოდეს.
        ცხრილში ჩანს მხოლოდ <strong style={{ color: '#fbbf24' }}>პრობლემური</strong> შემთხვევები — რაც გასწორებულია, აქ აღარ გამოჩნდება.
        გასწორების შემდეგ ცხრილი ცარიელდება შემდეგი pipeline-ის გაშვებისას.
      </p>

      {/* Summary cards */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
        <SummaryCard label="🔴 არ მიღებული" value={t.missing} sub={fmtMoney(t.missing_amount_sum)} accent="#ef4444" />
        <SummaryCard
          label="🔄 არასწორი მაღაზია"
          value={t.wrong_store}
          sub={`${fmtNum(t.wrong_store_only_other || 0)} სხვა მაღაზიაში · ${fmtNum(t.wrong_store_duplicate || 0)} ორმაგი`}
          accent="#ec4899"
        />
        <SummaryCard label="🟠 ფასი ≠" value={t.amount_mismatch} sub={fmtMoney(t.amount_mismatch_amount_sum)} accent="#f59e0b" />
        <SummaryCard label="👻 GHOST AP" value={t.ghost_ap} sub={fmtMoney(t.ghost_ap_amount_sum)} accent="#8b5cf6" />
        <SummaryCard label="🟡 დაბრუნება" value={t.returns_not_recorded} accent="#eab308" />
        <SummaryCard label="🟡 ქვე-ზედნადები" value={t.sub_waybills_not_recorded} accent="#ca8a04" />
        <SummaryCard label="⚠️ ჩანაცვლება?" value={t.possible_replacements} accent="#06b6d4" />
        <SummaryCard label="🆕 რს.გე ფაილი ძველია" value={t.rs_data_stale} accent="#10b981" />
      </div>

      <div style={{ padding: 12, background: '#0f172a', border: '1px solid #334155', borderRadius: 8, marginBottom: 16, fontSize: 12, color: '#94a3b8' }}>
        <div>ჯამი რს.გე-ზე აქტიური: <strong style={{ color: '#e2e8f0' }}>{fmtNum(t.rs_active_total)}</strong></div>
        <div>აქტიურ მაღაზიებზე ფილტრის შემდეგ: <strong style={{ color: '#e2e8f0' }}>{fmtNum(t.rs_active_in_active_stores)}</strong></div>
        <div>გამოიფილტრა (დახურული თბილისის ფილიალები): <strong style={{ color: '#64748b' }}>{fmtNum(t.filtered_closed_stores)}</strong></div>
        <div>ჯამი პრობლემა გასარკვევი: <strong style={{ color: '#fbbf24' }}>{fmtNum(totalProblems)}</strong></div>
      </div>

      {/* Filters */}
      <div style={{
        display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap',
        marginBottom: 16, padding: 12, background: '#1e293b',
        border: '1px solid #334155', borderRadius: 8,
      }}>
        <div>
          <label style={{ fontSize: 12, color: '#94a3b8', marginRight: 8 }}>მაღაზია:</label>
          <select
            value={storeFilter}
            onChange={(e) => setStoreFilter(e.target.value)}
            style={{ padding: '6px 10px', background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 4 }}
          >
            <option value="all">ყველა</option>
            <option value="1329">დვაბზუ</option>
            <option value="1301">ოზურგეთი</option>
          </select>
        </div>

        <div>
          <label style={{ fontSize: 12, color: '#94a3b8', marginRight: 8 }}>მომწოდებელი:</label>
          <select
            value={supplierFilter}
            onChange={(e) => setSupplierFilter(e.target.value)}
            style={{ padding: '6px 10px', background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 4, minWidth: 240 }}
          >
            <option value="all">ყველა მომწოდებელი</option>
            {supplierOptions.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>

        <label style={{ fontSize: 12, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6 }}>
          <input
            type="checkbox"
            checked={hideIfkli}
            onChange={(e) => setHideIfkli(e.target.checked)}
          />
          იფქლის დამალე (პატარა-პატარა მიწოდება)
        </label>
      </div>

      {/* Problem sections */}
      <ProblemSection rows={wr.missing} category="missing" supplierFilter={supplierFilter} storeFilter={storeFilter} hideIfkli={hideIfkli} />
      <ProblemSection rows={wr.wrong_store} category="wrong_store" supplierFilter={supplierFilter} storeFilter={storeFilter} hideIfkli={hideIfkli} />
      <ProblemSection rows={wr.amount_mismatch} category="amount_mismatch" supplierFilter={supplierFilter} storeFilter={storeFilter} hideIfkli={hideIfkli} />
      <ProblemSection rows={wr.ghost_ap} category="ghost_ap" supplierFilter={supplierFilter} storeFilter={storeFilter} hideIfkli={hideIfkli} />
      <ProblemSection rows={wr.returns_not_recorded} category="returns_not_recorded" supplierFilter={supplierFilter} storeFilter={storeFilter} hideIfkli={hideIfkli} />
      <ProblemSection rows={wr.sub_waybills_not_recorded} category="sub_waybills_not_recorded" supplierFilter={supplierFilter} storeFilter={storeFilter} hideIfkli={hideIfkli} />
      <ProblemSection rows={wr.possible_replacements} category="possible_replacements" supplierFilter={supplierFilter} storeFilter={storeFilter} hideIfkli={hideIfkli} />
      <ProblemSection rows={wr.rs_data_stale} category="rs_data_stale" supplierFilter={supplierFilter} storeFilter={storeFilter} hideIfkli={false} />

      {/* Per-supplier summary */}
      {wr.by_supplier && wr.by_supplier.length > 0 && (
        <details style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, marginTop: 24 }}>
          <summary style={{ padding: 14, cursor: 'pointer', fontSize: 16, fontWeight: 600 }}>
            მომწოდებლის სიხშირე ({wr.by_supplier.length})
          </summary>
          <div style={{ overflowX: 'auto', borderTop: '1px solid #334155' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead style={{ background: '#0f172a' }}>
                <tr>
                  <th style={thStyle}>მომწოდებელი</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>ჯამი</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>🔴 არ მიღებული</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>თანხა</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>🔄 არასწორი მაღაზია</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>🟠 ფასი ≠</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>🟡 დაბრუნება</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>🟡 ქვე-ზედნადები</th>
                </tr>
              </thead>
              <tbody>
                {wr.by_supplier.map((s, i) => (
                  <tr key={`${s.tax_id}-${i}`} style={{ borderTop: '1px solid #1e293b' }}>
                    <td style={tdStyle}>
                      {s.supplier_name}
                      {s.tax_id && <span style={{ color: '#64748b', marginLeft: 6, fontSize: 11 }}>({s.tax_id})</span>}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{fmtNum(s.total_count)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', color: '#ef4444', fontVariantNumeric: 'tabular-nums' }}>{fmtNum(s.missing_count)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', color: '#ef4444', fontVariantNumeric: 'tabular-nums' }}>{fmtMoney(s.missing_amount)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', color: '#ec4899', fontVariantNumeric: 'tabular-nums' }}>{fmtNum(s.wrong_store_count || 0)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', color: '#f59e0b', fontVariantNumeric: 'tabular-nums' }}>{fmtNum(s.amount_mismatch_count)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', color: '#eab308', fontVariantNumeric: 'tabular-nums' }}>{fmtNum(s.returns_not_recorded_count)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', color: '#ca8a04', fontVariantNumeric: 'tabular-nums' }}>{fmtNum(s.sub_waybills_not_recorded_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  );
}

const thStyle = {
  textAlign: 'left',
  padding: '10px 12px',
  fontSize: 11,
  color: '#94a3b8',
  fontWeight: 600,
  borderBottom: '1px solid #334155',
  whiteSpace: 'nowrap',
};

const tdStyle = {
  padding: '8px 12px',
  verticalAlign: 'top',
};
