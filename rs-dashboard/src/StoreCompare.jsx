import { useMemo, useState } from 'react';

const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency', currency: 'GEL', maximumFractionDigits: 0,
});
const NUM = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 0 });
const fmt = (v) =>
  v === null || v === undefined || !Number.isFinite(Number(v)) ? '—' : GEL.format(Number(v));
const fmtNum = (v) => (Number.isFinite(Number(v)) ? NUM.format(Number(v)) : '—');
const fmtPct = (v) =>
  v === null || v === undefined || !Number.isFinite(Number(v)) ? '—' : `${Number(v).toFixed(1)}%`;

const STORES = ['ოზურგეთი', 'დვაბზუ'];
const STORE_COLORS = {
  ოზურგეთი: '#3b82f6',
  დვაბზუ: '#a855f7',
};

function KPICard({ label, a, b, format, higherIsBetter = true, hint }) {
  const va = Number(a) || 0;
  const vb = Number(b) || 0;
  const winner = va === vb ? null : higherIsBetter ? (va > vb ? 'ოზურგეთი' : 'დვაბზუ') : (va < vb ? 'ოზურგეთი' : 'დვაბზუ');
  const delta = va - vb;
  const deltaPct = vb !== 0 ? (delta / Math.abs(vb)) * 100 : 0;
  return (
    <div style={{
      padding: 14, background: '#1e293b', border: '1px solid #334155',
      borderRadius: 8, minWidth: 240, flex: '1 1 240px',
    }}>
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 8 }}>{label}</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {STORES.map((s) => {
          const isWinner = winner === s;
          return (
            <div key={s} style={{
              padding: '6px 8px',
              background: isWinner ? `${STORE_COLORS[s]}22` : 'transparent',
              borderLeft: `3px solid ${isWinner ? STORE_COLORS[s] : '#334155'}`,
              borderRadius: 4,
            }}>
              <div style={{ fontSize: 11, color: STORE_COLORS[s], fontWeight: 600 }}>
                {s} {isWinner ? '🏆' : ''}
              </div>
              <div style={{
                fontSize: 18, fontWeight: 700, color: '#e2e8f0',
                fontVariantNumeric: 'tabular-nums', marginTop: 2,
              }}>
                {format(s === 'ოზურგეთი' ? a : b)}
              </div>
            </div>
          );
        })}
      </div>
      {winner && Math.abs(delta) > 0 ? (
        <div style={{ marginTop: 6, fontSize: 11, color: '#64748b' }}>
          {winner === 'ოზურგეთი' ? 'ოზურგეთი ' : 'დვაბზუ '}
          წინ {higherIsBetter ? '+' : ''}{fmtPct(Math.abs(deltaPct))}
        </div>
      ) : null}
      {hint ? <div style={{ marginTop: 4, fontSize: 11, color: '#64748b' }}>{hint}</div> : null}
    </div>
  );
}

function CategoryComparisonTable({ categories, sortBy, onSort, topN }) {
  const rows = useMemo(() => {
    const prepared = categories.map((c) => {
      const ob = Object.fromEntries(
        (c.object_breakdown || []).map((o) => [o.object, o])
      );
      const oz = ob['ოზურგეთი'] || {};
      const dv = ob['დვაბზუ'] || {};
      return {
        category: c.category,
        total: Number(c.revenue_ge) || 0,
        oz_rev: Number(oz.revenue_ge) || 0,
        oz_margin: Number(oz.gross_margin_pct) || 0,
        dv_rev: Number(dv.revenue_ge) || 0,
        dv_margin: Number(dv.gross_margin_pct) || 0,
      };
    });
    const sorted = [...prepared].sort((a, b) => {
      if (sortBy === 'oz_rev') return b.oz_rev - a.oz_rev;
      if (sortBy === 'dv_rev') return b.dv_rev - a.dv_rev;
      if (sortBy === 'delta') return Math.abs(b.oz_rev - b.dv_rev) - Math.abs(a.oz_rev - a.dv_rev);
      return b.total - a.total;
    });
    return sorted.slice(0, topN);
  }, [categories, sortBy, topN]);

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{
        width: '100%', borderCollapse: 'collapse', fontSize: 13,
        fontVariantNumeric: 'tabular-nums',
      }}>
        <thead>
          <tr style={{ background: '#0f172a', color: '#94a3b8' }}>
            <th style={th}>კატეგორია</th>
            <th style={thR} onClick={() => onSort('total')}>
              ჯამი {sortBy === 'total' ? '▾' : ''}
            </th>
            <th style={{ ...thR, color: STORE_COLORS['ოზურგეთი'] }} onClick={() => onSort('oz_rev')}>
              ოზურგეთი {sortBy === 'oz_rev' ? '▾' : ''}
            </th>
            <th style={thR}>margin</th>
            <th style={{ ...thR, color: STORE_COLORS['დვაბზუ'] }} onClick={() => onSort('dv_rev')}>
              დვაბზუ {sortBy === 'dv_rev' ? '▾' : ''}
            </th>
            <th style={thR}>margin</th>
            <th style={thR} onClick={() => onSort('delta')}>
              |Δ| {sortBy === 'delta' ? '▾' : ''}
            </th>
            <th style={th}>დომინანტი</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const ozDominant = r.oz_rev > r.dv_rev * 3;
            const dvDominant = r.dv_rev > r.oz_rev * 3;
            const dominant = ozDominant ? 'ოზურგეთი' : dvDominant ? 'დვაბზუ' : null;
            return (
              <tr key={r.category} style={{ borderBottom: '1px solid #1e293b' }}>
                <td style={td}>{r.category}</td>
                <td style={tdR}>{fmt(r.total)}</td>
                <td style={{ ...tdR, color: r.oz_rev > 0 ? STORE_COLORS['ოზურგეთი'] : '#64748b' }}>
                  {fmt(r.oz_rev)}
                </td>
                <td style={tdR}>{r.oz_rev > 0 ? fmtPct(r.oz_margin) : '—'}</td>
                <td style={{ ...tdR, color: r.dv_rev > 0 ? STORE_COLORS['დვაბზუ'] : '#64748b' }}>
                  {fmt(r.dv_rev)}
                </td>
                <td style={tdR}>{r.dv_rev > 0 ? fmtPct(r.dv_margin) : '—'}</td>
                <td style={{ ...tdR, color: '#fbbf24' }}>{fmt(Math.abs(r.oz_rev - r.dv_rev))}</td>
                <td style={td}>
                  {dominant ? (
                    <span style={{
                      padding: '2px 8px', background: `${STORE_COLORS[dominant]}33`,
                      color: STORE_COLORS[dominant], borderRadius: 4, fontSize: 11, fontWeight: 600,
                    }}>{dominant} only</span>
                  ) : (
                    <span style={{ fontSize: 11, color: '#64748b' }}>shared</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function StoreCompare({ retailSales }) {
  const [sortBy, setSortBy] = useState('total');
  const [topN, setTopN] = useState(15);

  const byObject = useMemo(() => {
    const map = {};
    for (const r of retailSales?.by_object || []) {
      map[r.object] = r;
    }
    return map;
  }, [retailSales]);

  const categories = useMemo(() => retailSales?.by_category || [], [retailSales]);

  const oz = byObject['ოზურგეთი'] || {};
  const dv = byObject['დვაბზუ'] || {};

  if (!retailSales) return <div style={{ padding: 24, color: '#94a3b8' }}>Store comparison იტვირთება…</div>;
  if (!oz.object && !dv.object) {
    return <div style={{ padding: 24, color: '#94a3b8' }}>retail_sales.by_object მონაცემი არ მოიძებნა.</div>;
  }

  return (
    <div style={{ padding: 16 }}>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ margin: '0 0 4px 0', color: '#f1f5f9' }}>🏬 მაღაზიების შედარება</h2>
        <div style={{ fontSize: 13, color: '#94a3b8' }}>
          ოზურგეთი vs დვაბზუ · retail_sales.by_object + by_category breakdown ·
          ვადები: <span style={{ color: STORE_COLORS['ოზურგეთი'] }}>{oz?.date_range?.min || '—'} → {oz?.date_range?.max || '—'}</span>
          {' · '}
          <span style={{ color: STORE_COLORS['დვაბზუ'] }}>{dv?.date_range?.min || '—'} → {dv?.date_range?.max || '—'}</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 18 }}>
        <KPICard
          label="💰 ბრუნვა"
          a={oz.revenue_ge} b={dv.revenue_ge}
          format={fmt}
          hint="ფასდაკლების ჩათვლით ყიდულის ფული"
        />
        <KPICard
          label="💎 მოგება"
          a={oz.profit_ge} b={dv.profit_ge}
          format={fmt}
        />
        <KPICard
          label="📊 მარჟა %"
          a={oz.gross_margin_pct} b={dv.gross_margin_pct}
          format={(v) => fmtPct(v)}
          hint="profit / revenue"
        />
        <KPICard
          label="🧾 ტრანზაქციები"
          a={oz.row_count} b={dv.row_count}
          format={fmtNum}
          hint="რამდენი ხაზი MAX-ში"
        />
        <KPICard
          label="📦 SKU ვერიეტი"
          a={oz.distinct_product_count} b={dv.distinct_product_count}
          format={fmtNum}
          hint="რამდენი განსხვ. პროდუქტი"
        />
        <KPICard
          label="🗂️ აქტიური კატეგორიები"
          a={oz.distinct_category_count} b={dv.distinct_category_count}
          format={fmtNum}
        />
      </div>

      <div style={{
        padding: 12, background: '#1e293b', borderRadius: 8, marginBottom: 12,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8,
      }}>
        <div style={{ fontSize: 14, color: '#f1f5f9', fontWeight: 600 }}>
          კატეგორიების შედარება (top {topN})
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#94a3b8' }}>რაოდ.:</span>
          {[10, 15, 25, 50].map((n) => (
            <button key={n} onClick={() => setTopN(n)} style={{
              padding: '3px 8px', fontSize: 12,
              background: topN === n ? '#2563eb' : '#0f172a',
              color: '#f1f5f9', border: '1px solid #334155', borderRadius: 4, cursor: 'pointer',
            }}>{n}</button>
          ))}
          <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 8 }}>დალაგება:</span>
          {[
            { v: 'total', l: 'ჯამი' },
            { v: 'oz_rev', l: 'ოზ' },
            { v: 'dv_rev', l: 'დვ' },
            { v: 'delta', l: '|Δ|' },
          ].map((o) => (
            <button key={o.v} onClick={() => setSortBy(o.v)} style={{
              padding: '3px 8px', fontSize: 12,
              background: sortBy === o.v ? '#2563eb' : '#0f172a',
              color: '#f1f5f9', border: '1px solid #334155', borderRadius: 4, cursor: 'pointer',
            }}>{o.l}</button>
          ))}
        </div>
      </div>

      <CategoryComparisonTable
        categories={categories}
        sortBy={sortBy}
        onSort={setSortBy}
        topN={topN}
      />

      <div style={{ marginTop: 16, fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
        💡 <b>"დომინანტი" chip</b> მონიშნავს კატეგორიას, სადაც ერთი მაღაზია 3×-ზე მეტად წინაა — ე.ი.
        სხვა მაღაზიაში ეს ან არ იყიდება ან მცირე მოცულობით. ნიშანია რომ შეიძლება პორტფოლიოს
        რებალანსი გააზრდის შემოსავალს იქაც.
        <br />
        💡 <b>margin-ი</b> per-store კატეგორიის ფარგლებში ცალ-ცალკე დათვლილია. თუ ერთ მაღაზიაში
        აშკარად მაღალია, გადაამოწმე ფასდაკლება / შესყიდვის პირობები მეორეში.
      </div>
    </div>
  );
}

const th = {
  padding: '8px 10px', textAlign: 'left', borderBottom: '2px solid #1e293b',
  fontSize: 12, fontWeight: 600, cursor: 'pointer', userSelect: 'none',
};
const thR = { ...th, textAlign: 'right' };
const td = { padding: '8px 10px', color: '#e2e8f0' };
const tdR = { ...td, textAlign: 'right' };
