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
  const cashbackTotal = Number(
    tbcCashback?.total_ge
      ?? tbcCashback?.total_amount_ge
      ?? tbcCashback?.summary?.total_amount_ge
      ?? 0,
  );
  const cashbackCount = Number(tbcCashback?.line_count ?? (tbcCashback?.rows_preview || []).length ?? 0);

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

  // Monthly netting reconciliation:
  // (our seller invoice) − (their buyer invoice) = expected; received in TBC next month-start
  const monthlyReconciliation = useMemo(() => {
    const months = {};
    const ensure = (ym) => {
      if (!months[ym]) months[ym] = { our: 0, their: 0, received: 0 };
      return months[ym];
    };
    for (const inv of sellerInvoices) {
      const ym = (inv.date_issued || '').slice(0, 7);
      if (ym.length !== 7) continue;
      ensure(ym).our += Number(inv.amount || 0);
    }
    for (const inv of buyerInvoices) {
      const ym = (inv.date_issued || '').slice(0, 7);
      if (ym.length !== 7) continue;
      ensure(ym).their += Number(inv.amount || 0);
    }
    const cashRows = tbcCashback?.rows_preview || [];
    for (const row of cashRows) {
      const dateStr = String(row['თარიღი'] || '').slice(0, 10);
      const m = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})/);
      if (!m) continue;
      const year = parseInt(m[1], 10);
      const month = parseInt(m[2], 10);
      const day = parseInt(m[3], 10);
      let billYear, billMonth;
      if (day <= 15) {
        if (month === 1) { billYear = year - 1; billMonth = 12; }
        else { billYear = year; billMonth = month - 1; }
      } else {
        billYear = year; billMonth = month;
      }
      const billingYM = `${billYear}-${String(billMonth).padStart(2, '0')}`;
      ensure(billingYM).received += Number(row['თანხა'] || 0);
    }
    const list = Object.entries(months).map(([ym, m]) => ({
      ym,
      our: m.our,
      their: m.their,
      expected: m.our - m.their,
      received: m.received,
      gap: (m.our - m.their) - m.received,
    }));
    return list.sort((a, b) => b.ym.localeCompare(a.ym));
  }, [sellerInvoices, buyerInvoices, tbcCashback]);

  const totalOutstanding = useMemo(
    () => monthlyReconciliation.reduce((sum, m) => sum + m.gap, 0),
    [monthlyReconciliation],
  );

  const serviceInvoiceCount = invoicesWithoutWaybills;
  const serviceInvoiceAmount = useMemo(
    () => buyerInvoices
      .filter((inv) => (inv.waybills?.length || 0) === 0)
      .reduce((sum, inv) => sum + Number(inv.amount || 0), 0),
    [buyerInvoices],
  );

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

      {/* MAIN: net profit + outstanding receivable (two most important numbers) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, marginBottom: 20 }}>
        {/* Net profit (income − service expense) */}
        <div style={{
          background: '#0f172a', border: '2px solid #10b981',
          borderRadius: 8, padding: 20,
        }}>
          <div style={{ fontSize: 14, color: '#94a3b8', marginBottom: 8 }}>
            💵 წმინდა მოგება ფუდმარტიდან (PnL)
          </div>
          <div style={{ fontSize: 32, fontWeight: 700, color: '#10b981' }}>
            {formatGel(sellerAmount - serviceInvoiceAmount)}
          </div>
          <div style={{ fontSize: 13, color: '#cbd5e1', marginTop: 10, lineHeight: 1.6 }}>
            შემოსავალი (ჩვენი მომსახურება) <b>{formatGel(sellerAmount)}</b>
            {' − '}ხარჯი (ფუდმარტის მომსახურება — ქირა, რეკლამა) <b>{formatGel(serviceInvoiceAmount)}</b>
            {' = '}<b>{formatGel(sellerAmount - serviceInvoiceAmount)}</b>
          </div>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 6 }}>
            საქონელი ({formatGelShort(agingTotal)}) მარაგშია — გაყიდვისას COGS-ად აისახება, ხარჯად აქ არ ითვლება.
          </div>
        </div>

        {/* Net outstanding receivable (cash flow status) */}
        <div style={{
          background: '#0f172a',
          border: `2px solid ${totalOutstanding > 100 ? '#fbbf24' : (totalOutstanding < -100 ? '#ef4444' : '#10b981')}`,
          borderRadius: 8, padding: 20,
        }}>
          <div style={{ fontSize: 14, color: '#94a3b8', marginBottom: 8 }}>
            💰 ფუდმარტის მისაცემი ჩვენთვის
          </div>
          <div style={{
            fontSize: 32, fontWeight: 700,
            color: totalOutstanding > 100 ? '#fbbf24' : (totalOutstanding < -100 ? '#ef4444' : '#10b981'),
          }}>
            {formatGel(totalOutstanding)}
          </div>
          <div style={{ fontSize: 13, color: '#cbd5e1', marginTop: 10, lineHeight: 1.6 }}>
            ჩვენი ფაქტურა <b>{formatGel(sellerAmount)}</b>
            {' − '}ფუდმარტის ფაქტურა <b>{formatGel(buyerAmount)}</b>
            {' − '}TBC-ში მიღებული <b>{formatGel(cashbackTotal)}</b>
            {' = '}<b>{formatGel(totalOutstanding)}</b>
          </div>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 6 }}>
            {totalOutstanding > 100
              ? 'დადებითი — ფუდმარტს გვმართებს კიდევ ეს თანხა'
              : (totalOutstanding < -100
                ? 'უარყოფითი — ჩვენ გვაქვს ზედმეტად მიღებული'
                : 'სრულიად დახურული — ფაქტიურად გასწორებულია')}
          </div>
        </div>
      </div>

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
      </div>

      <div style={{
        background: '#0f172a', border: '1px solid #334155', borderRadius: 8,
        padding: 16, marginBottom: 24,
      }}>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 10 }}>
          🧮 ფუდმარტის ფაქტურა — საქონელი vs მომსახურება
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>საქონელი (ზედნადებიანი)</div>
            <div style={{ fontSize: 18, fontWeight: 600, color: '#10b981' }}>{formatGel(agingTotal)}</div>
            <div style={{ fontSize: 12, color: '#64748b' }}>{invoicesWithWaybills} ფაქტურა — რეალურად მიღებული საქონელი</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>მომსახურება (ზედნადების გარეშე)</div>
            <div style={{ fontSize: 18, fontWeight: 600, color: '#3b82f6' }}>{formatGel(serviceInvoiceAmount)}</div>
            <div style={{ fontSize: 12, color: '#64748b' }}>{serviceInvoiceCount} ფაქტურა — საკომისიო, თარო, რეკლამა</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>ჯამი (ფაქტურით)</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{formatGel(buyerAmount)}</div>
            <div style={{ fontSize: 12, color: '#64748b' }}>{buyerCount} ფაქტურა</div>
          </div>
        </div>
        <div style={{
          marginTop: 12, padding: 10, background: '#0c2030',
          border: '1px solid #334155', borderRadius: 6, fontSize: 13, color: '#cbd5e1',
        }}>
          ℹ️ ფუდმარტის ფაქტურის უმეტესი ნაწილი მომსახურებაა (თაროზე განთავსების საფასური, რეკლამა). ზედნადები მათ არ სჭირდება — ეს ნორმალურია.
        </div>
      </div>

      <div style={{
        background: '#0f172a', border: '1px solid #334155', borderRadius: 8,
        padding: 16, marginBottom: 24,
      }}>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 10 }}>
          🔄 ყოველთვიური ანგარიშსწორება — ფორმულის ცხრილი
        </div>
        <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 10 }}>
          ფორმულა: ჩვენი ფაქტურა − ფუდმარტის ფაქტურა = უნდა მიგვეღო. სხვაობა &gt; 0 ნიშნავს გაუხდელი ვალია იმ თვისთვის.
        </div>
        {monthlyReconciliation.length === 0 ? (
          <div style={{ color: '#64748b', fontSize: 13 }}>მონაცემი არ არის.</div>
        ) : (
          <div style={{ maxHeight: 420, overflowY: 'auto' }}>
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead style={{ position: 'sticky', top: 0, background: '#0f172a', zIndex: 1 }}>
                <tr>
                  <th style={{ textAlign: 'left', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>თვე</th>
                  <th style={{ textAlign: 'right', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>ჩვენი ფაქტურა</th>
                  <th style={{ textAlign: 'right', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>ფუდმარტის ფაქტურა</th>
                  <th style={{ textAlign: 'right', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>უნდა მიგვეღო</th>
                  <th style={{ textAlign: 'right', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>მივიღეთ</th>
                  <th style={{ textAlign: 'right', padding: '6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>სხვაობა</th>
                </tr>
              </thead>
              <tbody>
                {monthlyReconciliation.map((m) => {
                  const isOpen = Math.abs(m.gap) > 1;
                  const gapColor = m.gap > 1 ? '#fbbf24' : (m.gap < -1 ? '#60a5fa' : '#10b981');
                  return (
                    <tr key={m.ym} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '6px', color: '#cbd5e1' }}>{m.ym}</td>
                      <td style={{ padding: '6px', textAlign: 'right', color: '#10b981' }}>{formatGel(m.our)}</td>
                      <td style={{ padding: '6px', textAlign: 'right', color: '#3b82f6' }}>{formatGel(m.their)}</td>
                      <td style={{ padding: '6px', textAlign: 'right' }}>{formatGel(m.expected)}</td>
                      <td style={{ padding: '6px', textAlign: 'right' }}>{formatGel(m.received)}</td>
                      <td style={{ padding: '6px', textAlign: 'right', fontWeight: isOpen ? 700 : 400, color: gapColor }}>
                        {formatGel(m.gap)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot style={{ position: 'sticky', bottom: 0, background: '#0f172a' }}>
                <tr style={{ borderTop: '2px solid #334155' }}>
                  <td style={{ padding: '8px 6px', fontWeight: 700, color: '#e2e8f0' }}>ჯამი</td>
                  <td style={{ padding: '8px 6px', textAlign: 'right', fontWeight: 700, color: '#10b981' }}>{formatGel(sellerAmount)}</td>
                  <td style={{ padding: '8px 6px', textAlign: 'right', fontWeight: 700, color: '#3b82f6' }}>{formatGel(buyerAmount)}</td>
                  <td style={{ padding: '8px 6px', textAlign: 'right', fontWeight: 700 }}>{formatGel(sellerAmount - buyerAmount)}</td>
                  <td style={{ padding: '8px 6px', textAlign: 'right', fontWeight: 700 }}>{formatGel(cashbackTotal)}</td>
                  <td style={{ padding: '8px 6px', textAlign: 'right', fontWeight: 700, color: totalOutstanding > 100 ? '#fbbf24' : '#10b981' }}>{formatGel(totalOutstanding)}</td>
                </tr>
              </tfoot>
            </table>
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
