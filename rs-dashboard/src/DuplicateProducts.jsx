import { useMemo, useState } from 'react';

const NUM = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 0 });
const NUM2 = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 2 });
const fmtNum = (v) => (Number.isFinite(Number(v)) ? NUM.format(Number(v)) : '—');
const fmtMoney = (v) => (Number.isFinite(Number(v)) ? `${NUM2.format(Number(v))} ₾` : '—');

const STORE_COLOR = {
  დვაბზუ: '#a855f7',
  ოზურგეთი: '#3b82f6',
};

const KIND_LABEL = {
  active: 'აქტიური',
  phantom: 'ცრუ მარაგი',
  dormant: 'მკვდარი',
};

const KIND_COLOR = {
  active: '#22c55e',
  phantom: '#ef4444',
  dormant: '#64748b',
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


export default function DuplicateProducts({ duplicateProducts }) {
  const dp = duplicateProducts;

  const [storeFilter, setStoreFilter] = useState('all');
  const [phantomOnly, setPhantomOnly] = useState('phantom');
  const [search, setSearch] = useState('');

  const clusters = useMemo(() => {
    if (!dp?.clusters) return [];
    return dp.clusters;
  }, [dp]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return clusters.filter((c) => {
      if (storeFilter !== 'all' && c.store !== storeFilter) return false;
      if (phantomOnly === 'phantom' && !c.has_phantom) return false;
      if (phantomOnly === 'no_phantom' && c.has_phantom) return false;
      if (q) {
        const hay = (c.barcode + ' ' + c.variants.map(v => v.name || '').join(' ')).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [clusters, storeFilter, phantomOnly, search]);

  if (!dp || !dp.summary) {
    return (
      <div style={{ padding: 24, color: '#94a3b8' }}>
        <h2 style={{ color: '#e2e8f0', marginBottom: 12 }}>👥 დუბლირებული პროდუქცია</h2>
        <p>მონაცემი ჯერ არ აიგო. გაუშვი pipeline.</p>
      </div>
    );
  }

  const s = dp.summary;

  return (
    <div style={{ padding: 16 }}>
      <h2 style={{ color: '#e2e8f0', marginBottom: 6 }}>
        👥 დუბლირებული პროდუქცია
      </h2>
      <p style={{ color: '#94a3b8', marginTop: 0, marginBottom: 16, fontSize: 14 }}>
        ერთი და იგივე ბარკოდი 2 (ან მეტი) ჩანაწერით MegaPlus-ში.
        წითლად მონიშნული — „ცრუ მარაგი": ჩანაწერს მარაგი უწერია, მაგრამ
        გაყიდვა მეორე ჩანაწერში მიდის. ფიქსი — MegaPlus-ში ერთი ჩანაწერი
        წაშალე ან გააერთიანე, სიიდან თვითონ მოშორდება.
      </p>

      {/* Summary cards */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
        <SummaryCard
          label="დუბლიკატი ბარკოდი"
          value={fmtNum(s.cluster_count)}
        />
        <SummaryCard
          label="ცრუ-მარაგის შემთხვევა"
          value={fmtNum(s.phantom_cluster_count)}
          accent="#ef4444"
        />
        <SummaryCard
          label="ცრუ ერთეული"
          value={fmtNum(s.phantom_units)}
          accent="#f59e0b"
        />
        <SummaryCard
          label="ცრუ ფული (გასაყიდი)"
          value={fmtMoney(s.phantom_value_sell_ge)}
          accent="#ef4444"
          sub={`ნაყიდი ფასით: ${fmtMoney(s.phantom_value_get_ge)}`}
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
        <FilterSelect label="ხედი" value={phantomOnly} onChange={setPhantomOnly} options={[
          { value: 'phantom', label: 'მხოლოდ ცრუ მარაგი' },
          { value: 'all', label: 'ყველა დუბლიკატი' },
          { value: 'no_phantom', label: 'მხოლოდ მკვდარი' },
        ]} />
        <div style={{ flex: '1 1 200px', minWidth: 200 }}>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>ძიება</div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="ბარკოდი / პროდუქტის სახელი"
            style={{
              width: '100%', padding: '6px 10px',
              background: '#1e293b', color: '#e2e8f0',
              border: '1px solid #334155', borderRadius: 6,
              fontSize: 14,
            }}
          />
        </div>
      </div>

      <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 8 }}>
        ნაჩვენებია <b style={{ color: '#e2e8f0' }}>{fmtNum(filtered.length)}</b> /
        {' '}{fmtNum(clusters.length)} დუბლიკატი ბარკოდი
      </div>

      {/* Cluster list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {filtered.slice(0, 200).map((c) => (
          <div
            key={`${c.store}::${c.barcode}`}
            style={{
              border: c.has_phantom ? '1px solid #7f1d1d' : '1px solid #1e293b',
              borderRadius: 8, overflow: 'hidden',
              background: '#0f172a',
            }}
          >
            <div style={{
              padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 12,
              background: c.has_phantom ? '#3f1d20' : '#1e293b',
              borderBottom: c.has_phantom ? '1px solid #7f1d1d' : '1px solid #334155',
            }}>
              <span style={{
                display: 'inline-block', padding: '2px 8px', borderRadius: 12,
                fontSize: 11, color: '#fff',
                background: STORE_COLOR[c.store] || '#475569',
              }}>{c.store}</span>
              <span style={{ fontFamily: 'monospace', fontSize: 14, color: '#e2e8f0' }}>
                ბარკოდი: {c.barcode}
              </span>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>
                {c.variant_count} ჩანაწერი
              </span>
              {c.has_phantom && (
                <span style={{
                  marginLeft: 'auto', fontSize: 13, color: '#fee2e2', fontWeight: 600,
                }}>
                  ⚠ ცრუ მარაგი: {fmtNum(c.phantom_units)} ცალი = {fmtMoney(c.phantom_value_sell_ge)}
                </span>
              )}
            </div>
            <table style={{
              width: '100%', borderCollapse: 'collapse', fontSize: 13,
              color: '#e2e8f0',
            }}>
              <thead>
                <tr style={{ background: '#0b1220' }}>
                  <th style={th}>ტიპი</th>
                  <th style={th}>P_ID</th>
                  <th style={th}>სახელი</th>
                  <th style={{ ...th, textAlign: 'right' }}>მარაგი</th>
                  <th style={{ ...th, textAlign: 'right' }}>გაყიდვა</th>
                  <th style={th}>ბოლო გაყიდვა</th>
                </tr>
              </thead>
              <tbody>
                {c.variants.map((v) => (
                  <tr key={v.product_id} style={{
                    borderTop: '1px solid #1e293b',
                    background: v.kind === 'phantom' ? '#1f0e10' : 'transparent',
                  }}>
                    <td style={td}>
                      <span style={{
                        color: KIND_COLOR[v.kind],
                        fontWeight: 600, fontSize: 12,
                      }}>● {KIND_LABEL[v.kind] || v.kind}</span>
                    </td>
                    <td style={{ ...td, fontFamily: 'monospace', color: '#94a3b8' }}>{v.product_id}</td>
                    <td style={td}>{v.name || '—'}</td>
                    <td style={{
                      ...td, textAlign: 'right', fontVariantNumeric: 'tabular-nums',
                      color: v.stock < 0 ? '#f87171' : (v.stock > 0 && v.kind === 'phantom' ? '#fbbf24' : '#e2e8f0'),
                      fontWeight: v.kind === 'phantom' ? 600 : 400,
                    }}>
                      {fmtNum(v.stock)}
                    </td>
                    <td style={{ ...td, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {fmtMoney(v.lifetime_revenue_ge)}
                      <div style={{ fontSize: 11, color: '#64748b' }}>{fmtNum(v.sale_lines)} ჯერ</div>
                    </td>
                    <td style={{ ...td, fontSize: 12, color: '#94a3b8' }}>
                      {v.last_sale_at || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {filtered.length > 200 && (
        <div style={{
          padding: 12, fontSize: 13, color: '#94a3b8',
          background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
          marginTop: 12,
        }}>
          ნაჩვენებია პირველი 200. ფილტრით ან ძიებით შეამცირე სია.
        </div>
      )}
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
  padding: '8px 12px', fontWeight: 600, fontSize: 11,
  textTransform: 'uppercase', letterSpacing: '0.04em',
  color: '#94a3b8', textAlign: 'left',
};

const td = {
  padding: '8px 12px', verticalAlign: 'top',
};
