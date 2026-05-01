import { useMemo, useState } from 'react';

const NUM = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 0 });
const fmtNum = (v) => (Number.isFinite(Number(v)) ? NUM.format(Number(v)) : '—');

const PROBLEM_LABEL = {
  empty: 'ცარიელი კატეგორია',
  duplicate: 'დუბლიკატი ვარიანტი',
};

const PROBLEM_COLOR = {
  empty: '#ef4444',
  duplicate: '#f59e0b',
};

const STORE_COLOR = {
  დვაბზუ: '#a855f7',
  ოზურგეთი: '#3b82f6',
};


function SummaryCard({ label, value, accent }) {
  return (
    <div style={{
      padding: 14, background: '#1e293b', border: '1px solid #334155',
      borderRadius: 8, minWidth: 200, flex: '1 1 200px',
    }}>
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>{label}</div>
      <div style={{
        fontSize: 28, fontWeight: 700, color: accent || '#e2e8f0',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {fmtNum(value)}
      </div>
    </div>
  );
}


export default function CategoryAnomalies({ data }) {
  const ca = data?.category_anomalies;

  const [storeFilter, setStoreFilter] = useState('all');
  const [problemFilter, setProblemFilter] = useState('all');

  const rows = useMemo(() => {
    if (!ca) return [];
    const out = [];
    for (const bundle of (ca.stores || [])) {
      for (const p of (bundle.empty_category_products || [])) {
        out.push({
          store_id: bundle.store_id,
          store_name: bundle.store_name,
          product_id: p.product_id,
          product_name: p.product_name,
          barcode: p.barcode,
          code: p.code,
          problem: 'empty',
          current_category: '',
          target_category: '',
          supplier_name: p.supplier_name,
        });
      }
      for (const c of (bundle.duplicate_clusters || [])) {
        for (const p of (c.minority_products || [])) {
          out.push({
            store_id: bundle.store_id,
            store_name: bundle.store_name,
            product_id: p.product_id,
            product_name: p.product_name,
            barcode: p.barcode,
            code: p.code,
            problem: 'duplicate',
            current_category: p.current_category,
            target_category: c.majority_variant?.raw_category || '',
            supplier_name: p.supplier_name,
          });
        }
      }
    }
    return out;
  }, [ca]);

  const filteredRows = useMemo(() => {
    return rows
      .filter((r) => storeFilter === 'all' || r.store_id === storeFilter)
      .filter((r) => problemFilter === 'all' || r.problem === problemFilter)
      .sort((a, b) => {
        if (a.store_name !== b.store_name) return a.store_name.localeCompare(b.store_name, 'ka');
        if (a.problem !== b.problem) return a.problem === 'empty' ? -1 : 1;
        return (a.product_name || '').localeCompare(b.product_name || '', 'ka');
      });
  }, [rows, storeFilter, problemFilter]);

  if (!ca) {
    return (
      <div style={{ padding: 24, color: '#94a3b8' }}>
        <h1 style={{ color: '#e2e8f0', marginTop: 0 }}>კატეგორიების შემოწმება</h1>
        <p>მონაცემი ჯერ არ არის — pipeline-ის შემდეგი გაშვების მერე გამოჩნდება.</p>
      </div>
    );
  }

  const totals = ca.totals || {};
  const stores = ca.stores || [];

  return (
    <div style={{ padding: 20, color: '#e2e8f0' }}>
      <h1 style={{ marginTop: 0, marginBottom: 8 }}>კატეგორიების შემოწმება</h1>
      <p style={{ color: '#94a3b8', marginTop: 0, marginBottom: 20 }}>
        MegaPlus-ში არასწორად შევსებული კატეგორიები. გაასწორე MegaPlus-ში → pipeline ხელახლა გაუშვი → ცხრილი თვითონ დაიცლება.
      </p>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
        <SummaryCard label="ცარიელი კატეგორია" value={totals.empty_category_count} accent="#ef4444" />
        <SummaryCard label="დუბლიკატი ჯგუფი" value={totals.duplicate_cluster_count} accent="#f59e0b" />
        <SummaryCard label="დუბლიკატის პროდუქტები" value={totals.duplicate_minority_product_count} accent="#f59e0b" />
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
            {stores.map((s) => (
              <option key={s.store_id} value={s.store_id}>{s.store_name}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ fontSize: 12, color: '#94a3b8', marginRight: 8 }}>პრობლემის ტიპი:</label>
          <select
            value={problemFilter}
            onChange={(e) => setProblemFilter(e.target.value)}
            style={{ padding: '6px 10px', background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 4 }}
          >
            <option value="all">ყველა</option>
            <option value="empty">ცარიელი კატეგორია</option>
            <option value="duplicate">დუბლიკატი ვარიანტი</option>
          </select>
        </div>

        <div style={{ marginLeft: 'auto', fontSize: 13, color: '#94a3b8' }}>
          <strong style={{ color: '#e2e8f0' }}>{fmtNum(filteredRows.length)}</strong> ხაზი
        </div>
      </div>

      {/* Main table */}
      <div style={{ overflow: 'auto', maxHeight: '60vh', border: '1px solid #334155', borderRadius: 8 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead style={{ position: 'sticky', top: 0, background: '#0f172a', zIndex: 1 }}>
            <tr>
              <th style={thStyle}>მაღაზია</th>
              <th style={thStyle}>პროდუქტი</th>
              <th style={thStyle}>ბარკოდი (13-ნიშნა)</th>
              <th style={thStyle}>პრობლემა</th>
              <th style={thStyle}>მიმდინარე კატეგორია</th>
              <th style={thStyle}>სავარაუდო სწორი კატეგორია</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: 20, textAlign: 'center', color: '#94a3b8' }}>—</td></tr>
            ) : filteredRows.map((r, idx) => (
              <tr key={`${r.store_id}-${r.product_id}-${r.problem}-${idx}`} style={{ borderTop: '1px solid #1e293b' }}>
                <td style={{ ...tdStyle, color: STORE_COLOR[r.store_name] || '#e2e8f0', fontWeight: 600 }}>
                  {r.store_name}
                </td>
                <td style={tdStyle}>{r.product_name}</td>
                <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: 12, color: '#94a3b8' }}>{r.barcode || '—'}</td>
                <td style={tdStyle}>
                  <span style={{
                    padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                    background: `${PROBLEM_COLOR[r.problem]}22`, color: PROBLEM_COLOR[r.problem],
                  }}>
                    {PROBLEM_LABEL[r.problem]}
                  </span>
                </td>
                <td style={{ ...tdStyle, color: r.problem === 'empty' ? '#64748b' : '#e2e8f0', fontStyle: r.problem === 'empty' ? 'italic' : 'normal' }}>
                  {r.problem === 'empty' ? '(ცარიელი)' : r.current_category}
                </td>
                <td style={{ ...tdStyle, color: '#10b981' }}>
                  {r.target_category || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* PROTECTED supplier review */}
      <h2 style={{ marginTop: 32, marginBottom: 8, color: '#e2e8f0' }}>
        PROTECTED მომწოდებლები — მიმოხილვა
      </h2>
      <p style={{ color: '#94a3b8', marginTop: 0, marginBottom: 16, fontSize: 13 }}>
        სიგარეტის 3 იმპორტიორი — ELIZI / ჯიდიაი / ინტერნეიშნლ. მათი პროდუქტი თუ მოულოდნელ კატეგორიაში გამოჩნდა, აქ ნახავ.
      </p>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {stores.map((store) => (
          <div key={store.store_id} style={{
            flex: '1 1 400px', background: '#1e293b', border: '1px solid #334155',
            borderRadius: 8, padding: 14,
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: STORE_COLOR[store.store_name], marginBottom: 12 }}>
              {store.store_name}
            </div>
            {(store.protected_supplier_overview || []).map((sup) => (
              <div key={sup.supplier_tax_id} style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>
                  {sup.supplier_label}
                  <span style={{ fontSize: 11, color: '#64748b', fontWeight: 400, marginLeft: 8 }}>
                    {sup.supplier_tax_id}
                  </span>
                </div>
                <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                  <tbody>
                    {(sup.categories || []).map((cat) => (
                      <tr key={cat.raw_category}>
                        <td style={{ padding: '3px 0', color: '#cbd5e1' }}>{cat.raw_category}</td>
                        <td style={{ padding: '3px 0', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#94a3b8' }}>
                          {fmtNum(cat.product_count)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}


const thStyle = {
  textAlign: 'left',
  padding: '10px 12px',
  fontSize: 12,
  color: '#94a3b8',
  fontWeight: 600,
  borderBottom: '1px solid #334155',
  whiteSpace: 'nowrap',
};

const tdStyle = {
  padding: '8px 12px',
  verticalAlign: 'top',
};
