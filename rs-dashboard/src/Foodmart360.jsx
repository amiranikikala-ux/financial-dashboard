import { useMemo } from 'react';

const FOODMART_TAX_ID = '404460187';

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

export default function Foodmart360({ data }) {
  const buyerInvoices = data?.supplier_invoices?.[FOODMART_TAX_ID] || [];
  const buyerSummary = data?.supplier_invoices_summary?.[FOODMART_TAX_ID] || null;
  const allSellerInvoices = data?.our_seller_invoices || [];
  const sellerInvoices = useMemo(
    () => allSellerInvoices.filter((inv) => inv.customer_tax_id === FOODMART_TAX_ID),
    [allSellerInvoices],
  );
  const tbcCashback = data?.tbc_foodmart_cashback || null;
  const cashbackTotal = Number(tbcCashback?.total_amount_ge ?? tbcCashback?.summary?.total_amount_ge ?? 0);
  const cashbackCount = Number(tbcCashback?.line_count ?? (tbcCashback?.lines || []).length ?? 0);

  const supplier = (data?.suppliers || []).find(
    (s) => String(s.tax_id) === FOODMART_TAX_ID || String(s['ორგანიზაცია'] || '').includes(FOODMART_TAX_ID),
  );
  const agingTotal = Number(supplier?.total_effective || 0);
  const agingDebt = Number(supplier?.total_debt || 0);

  const buyerCount = buyerSummary?.invoice_count ?? buyerInvoices.length;
  const buyerAmount = Number(buyerSummary?.total_amount ?? 0);
  const buyerVat = Number(buyerSummary?.total_vat ?? 0);
  const sellerAmount = sellerInvoices.reduce((sum, inv) => sum + Number(inv.amount || 0), 0);
  const sellerCount = sellerInvoices.length;
  const gap = buyerAmount - agingTotal;

  const invoicesWithWaybills = buyerInvoices.filter((inv) => (inv.waybills?.length || 0) > 0).length;
  const invoicesWithoutWaybills = buyerCount - invoicesWithWaybills;

  const monthlyBuyer = useMemo(() => {
    const m = {};
    for (const inv of buyerInvoices) {
      const date = (inv.date_issued || '').slice(0, 7);
      if (!date) continue;
      if (!m[date]) m[date] = { count: 0, amount: 0, withWaybill: 0 };
      m[date].count += 1;
      m[date].amount += Number(inv.amount || 0);
      if ((inv.waybills?.length || 0) > 0) m[date].withWaybill += 1;
    }
    return Object.entries(m).sort(([a], [b]) => b.localeCompare(a));
  }, [buyerInvoices]);

  const sortedInvoices = useMemo(
    () => [...buyerInvoices].sort((a, b) => (b.date_issued || '').localeCompare(a.date_issued || '')),
    [buyerInvoices],
  );

  return (
    <div style={{ padding: 16, color: '#e2e8f0' }}>
      <h2 style={{ marginTop: 0, marginBottom: 8 }}>📊 ფუდმარტი 360°</h2>
      <p style={{ color: '#94a3b8', marginTop: 0, marginBottom: 20 }}>
        ფუდმარტთან ჩვენი ურთიერთობის სრული სურათი — ფაქტურა, ზედნადები, ბანკი, ვალი.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 24 }}>
        <Card
          title="ფუდმარტი → ჩვენ (ფაქტურა)"
          value={formatGel(buyerAmount)}
          hint={`${buyerCount} ფაქტურა, დღგ ${formatGelShort(buyerVat)}`}
          accent="#3b82f6"
        />
        <Card
          title="ჩვენ → ფუდმარტი (ფაქტურა)"
          value={formatGel(sellerAmount)}
          hint={`${sellerCount} ფაქტურა`}
          accent="#10b981"
        />
        <Card
          title="TBC cashback ფუდმარტიდან"
          value={formatGel(cashbackTotal)}
          hint={cashbackCount > 0 ? `${cashbackCount} გადარიცხვა` : 'მონაცემი არ არის'}
          accent="#fbbf24"
        />
        <Card
          title="აგინგ-ის ბრუნვა"
          value={formatGel(agingTotal)}
          hint={`ვალი ჩვენგან: ${formatGelShort(agingDebt)}`}
          accent="#a855f7"
        />
      </div>

      <div style={{
        background: '#0f172a', border: '1px solid #334155', borderRadius: 8,
        padding: 16, marginBottom: 24,
      }}>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 10 }}>
          🧮 ფაქტურა vs აგინგ — სხვაობა
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>ფაქტურით ჯამი</div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>{formatGel(buyerAmount)}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>აგინგ-ით ჯამი</div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>{formatGel(agingTotal)}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>სხვაობა</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: Math.abs(gap) > 100 ? '#fbbf24' : '#10b981' }}>
              {formatGel(gap)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>ზედნადებთან მიბმა</div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>
              {invoicesWithWaybills} / {buyerCount}
            </div>
            <div style={{ fontSize: 12, color: '#64748b' }}>
              ({invoicesWithoutWaybills} ფაქტურა ზედნადების გარეშე)
            </div>
          </div>
        </div>
        {Math.abs(gap) > 100 && (
          <div style={{
            marginTop: 12, padding: 10, background: '#451a03',
            border: '1px solid #f59e0b', borderRadius: 6, fontSize: 13,
          }}>
            ⚠️ სხვაობის შესაძლო მიზეზები: სერვისები ზედნადების გარეშე, გაუქმებული ზედნადები, თვის ბოლო ჩაჭრა, დაბრუნება.
            ეს არ არის შეცდომა — საჭიროა მფლობელის გადახედვა.
          </div>
        )}
      </div>

      <div style={{
        background: '#0f172a', border: '1px solid #334155', borderRadius: 8,
        padding: 16, marginBottom: 24,
      }}>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 10 }}>
          📅 ყოველთვიური დინამიკა
        </div>
        {monthlyBuyer.length === 0 ? (
          <div style={{ color: '#64748b', fontSize: 13 }}>მონაცემი არ არის.</div>
        ) : (
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>თვე</th>
                <th style={{ textAlign: 'right', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>ფაქტურა</th>
                <th style={{ textAlign: 'right', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>თანხა</th>
                <th style={{ textAlign: 'right', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>ზედნადებიანი</th>
              </tr>
            </thead>
            <tbody>
              {monthlyBuyer.map(([month, m]) => (
                <tr key={month} style={{ borderBottom: '1px solid #1e293b' }}>
                  <td style={{ padding: '6px', color: '#cbd5e1' }}>{month}</td>
                  <td style={{ padding: '6px', textAlign: 'right' }}>{m.count}</td>
                  <td style={{ padding: '6px', textAlign: 'right' }}>{formatGel(m.amount)}</td>
                  <td style={{ padding: '6px', textAlign: 'right', color: m.withWaybill === m.count ? '#10b981' : '#fbbf24' }}>
                    {m.withWaybill} / {m.count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div style={{
        background: '#0f172a', border: '1px solid #334155', borderRadius: 8,
        padding: 16,
      }}>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 10 }}>
          📋 ყველა ფაქტურა ({buyerCount})
        </div>
        <div style={{ maxHeight: 500, overflowY: 'auto' }}>
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead style={{ position: 'sticky', top: 0, background: '#0f172a' }}>
              <tr>
                <th style={{ textAlign: 'left', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>ID</th>
                <th style={{ textAlign: 'left', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>თარიღი</th>
                <th style={{ textAlign: 'right', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>თანხა</th>
                <th style={{ textAlign: 'right', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>დღგ</th>
                <th style={{ textAlign: 'left', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>სტატუსი</th>
                <th style={{ textAlign: 'center', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>ზედნადები</th>
              </tr>
            </thead>
            <tbody>
              {sortedInvoices.map((inv, idx) => (
                <tr key={inv.id || idx} style={{ borderBottom: '1px solid #1e293b' }}>
                  <td style={{ padding: '6px', color: '#cbd5e1', fontFamily: 'monospace', fontSize: 12 }}>{inv.id}</td>
                  <td style={{ padding: '6px', color: '#cbd5e1' }}>{(inv.date_issued || '').slice(0, 10)}</td>
                  <td style={{ padding: '6px', textAlign: 'right' }}>{formatGel(inv.amount)}</td>
                  <td style={{ padding: '6px', textAlign: 'right', color: '#94a3b8' }}>{formatGel(inv.vat)}</td>
                  <td style={{ padding: '6px', color: '#94a3b8' }}>{inv.status}</td>
                  <td style={{ padding: '6px', textAlign: 'center', color: (inv.waybills?.length || 0) > 0 ? '#10b981' : '#ef4444' }}>
                    {inv.waybills?.length || 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
