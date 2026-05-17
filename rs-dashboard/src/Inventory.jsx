import { useMemo, useState } from 'react';

const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 0,
});
const GEL2 = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 2,
});
const NUM = new Intl.NumberFormat('ka-GE');
const NUM2 = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 2 });

const fmt = (v) => GEL.format(Number(v) || 0);
const fmt2 = (v) => GEL2.format(Number(v) || 0);
const fmtNum = (v) => NUM.format(Number(v) || 0);
const fmtNum2 = (v) => NUM2.format(Number(v) || 0);

function KPI({ label, value, sub, color }) {
  return (
    <div style={{
      padding: 16,
      background: '#1e293b',
      border: `1px solid ${color || '#334155'}`,
      borderRadius: 10,
      flex: '1 1 200px',
      minWidth: 200,
    }}>
      <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 6 }}>{label}</div>
      <div style={{
        fontSize: 22, fontWeight: 700, color: color || '#e2e8f0',
        fontVariantNumeric: 'tabular-nums',
      }}>{value}</div>
      {sub && <div style={{ color: '#64748b', fontSize: 11, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function dosColor(dos) {
  if (dos == null) return '#64748b';
  if (dos < 7) return '#ef4444';
  if (dos < 21) return '#eab308';
  return '#22c55e';
}

function DosBadge({ dos }) {
  if (dos == null) {
    return <span style={{ color: '#64748b' }}>—</span>;
  }
  return (
    <span style={{
      color: dosColor(dos),
      fontWeight: 600,
      fontVariantNumeric: 'tabular-nums',
    }}>
      {dos < 1 ? '< 1 დღე' : `${Math.round(dos)} დღე`}
    </span>
  );
}

function ItemsTable({ items, showDos = true }) {
  if (!items || !items.length) {
    return <div style={{ color: '#64748b', padding: 12 }}>(ცარიელია)</div>;
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: 13,
        background: '#0f172a',
      }}>
        <thead>
          <tr style={{ background: '#1e293b', color: '#94a3b8' }}>
            <th style={{ padding: 8, textAlign: 'left' }}>პროდუქტი</th>
            <th style={{ padding: 8, textAlign: 'left' }}>კატეგორია</th>
            <th style={{ padding: 8, textAlign: 'left' }}>მომწოდებელი</th>
            <th style={{ padding: 8, textAlign: 'right' }}>ნაშთი</th>
            <th style={{ padding: 8, textAlign: 'right' }}>ცხუმი</th>
            <th style={{ padding: 8, textAlign: 'right' }}>საცალო</th>
            <th style={{ padding: 8, textAlign: 'right' }}>30 დღე გაყიდვა</th>
            {showDos && <th style={{ padding: 8, textAlign: 'right' }}>კიდევ ეყოფა</th>}
            <th style={{ padding: 8, textAlign: 'left' }}>ბოლო გაყიდვა</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={`${it.product_id}-${it.barcode}`} style={{ borderBottom: '1px solid #1e293b' }}>
              <td style={{ padding: 8, color: '#e2e8f0' }}>
                <div>{it.product_name || '(უსახელო)'}</div>
                <div style={{ fontSize: 11, color: '#64748b' }}>
                  {it.product_code} {it.barcode && `· ${it.barcode}`}
                </div>
              </td>
              <td style={{ padding: 8, color: '#94a3b8', fontSize: 12 }}>{it.category}</td>
              <td style={{ padding: 8, color: '#94a3b8', fontSize: 12 }}>{it.supplier_name}</td>
              <td style={{ padding: 8, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                {fmtNum2(it.qty)}
              </td>
              <td style={{ padding: 8, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                {fmt(it.stock_value_cost)}
              </td>
              <td style={{ padding: 8, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                {fmt(it.stock_value_retail)}
              </td>
              <td style={{ padding: 8, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                {fmtNum2(it.qty_sold_30d)}
              </td>
              {showDos && (
                <td style={{ padding: 8, textAlign: 'right' }}>
                  <DosBadge dos={it.days_of_supply} />
                </td>
              )}
              <td style={{ padding: 8, color: '#94a3b8', fontSize: 12 }}>
                {it.last_sale_date ? it.last_sale_date.slice(0, 10) : 'არასოდეს'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TodaysSalesTable({ items }) {
  const sold = (items || []).filter((it) => it.qty_sold_today > 0);
  if (!sold.length) {
    return <div style={{ color: '#64748b', padding: 12 }}>დღევანდელ თარიღზე გაყიდვა არ ფიქსირდება.</div>;
  }
  const top = sold.sort((a, b) => b.revenue_today - a.revenue_today).slice(0, 30);
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{
        width: '100%', borderCollapse: 'collapse', fontSize: 13, background: '#0f172a',
      }}>
        <thead>
          <tr style={{ background: '#1e293b', color: '#94a3b8' }}>
            <th style={{ padding: 8, textAlign: 'left' }}>პროდუქტი</th>
            <th style={{ padding: 8, textAlign: 'right' }}>გაიყიდა ცალი</th>
            <th style={{ padding: 8, textAlign: 'right' }}>თანხა</th>
            <th style={{ padding: 8, textAlign: 'right' }}>დარჩა ნაშთი</th>
          </tr>
        </thead>
        <tbody>
          {top.map((it) => (
            <tr key={`t-${it.product_id}`} style={{ borderBottom: '1px solid #1e293b' }}>
              <td style={{ padding: 8, color: '#e2e8f0' }}>
                <div>{it.product_name || '(უსახელო)'}</div>
                <div style={{ fontSize: 11, color: '#64748b' }}>{it.supplier_name}</div>
              </td>
              <td style={{ padding: 8, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                {fmtNum2(it.qty_sold_today)}
              </td>
              <td style={{ padding: 8, textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#22c55e' }}>
                {fmt2(it.revenue_today)}
              </td>
              <td style={{ padding: 8, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                {fmtNum2(it.qty)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Inventory({ inventoryView }) {
  const data = inventoryView && typeof inventoryView === 'object' ? inventoryView : null;
  const empty = !data || data.available === false || !data.stores;

  const stores = useMemo(() => data?.stores || {}, [data]);
  const storeIds = useMemo(() => Object.keys(stores), [stores]);

  const [activeStore, setActiveStore] = useState(() => storeIds[0] || '');
  const [supplierFilter, setSupplierFilter] = useState('all');
  const [searchCompany, setSearchCompany] = useState('');
  const [searchName, setSearchName] = useState('');
  const [searchBarcode, setSearchBarcode] = useState('');
  const [view, setView] = useState('all'); // all | low | dead | stockout | negative

  const storeView = stores[activeStore] || null;

  // First pass: apply supplier + text search filters. Used by both the main
  // items table (with view filter on top) and Today's sales (without view).
  const searchedItems = useMemo(() => {
    const items = storeView?.items || [];
    const qCompany = searchCompany.trim().toLowerCase();
    const qName = searchName.trim().toLowerCase();
    const qBarcode = searchBarcode.trim().toLowerCase();
    return items.filter((it) => {
      if (supplierFilter !== 'all' && it.supplier_uuid !== supplierFilter) return false;
      if (qCompany) {
        const hay = `${it.supplier_name || ''} ${it.supplier_tax_id || ''}`.toLowerCase();
        if (!hay.includes(qCompany)) return false;
      }
      if (qName) {
        if (!(it.product_name || '').toLowerCase().includes(qName)) return false;
      }
      if (qBarcode) {
        const hay = `${it.barcode || ''} ${it.product_code || ''}`.toLowerCase();
        if (!hay.includes(qBarcode)) return false;
      }
      return true;
    });
  }, [storeView, supplierFilter, searchCompany, searchName, searchBarcode]);

  // Second pass: apply the view (all/low/dead/stockout/negative) on top.
  const filteredItems = useMemo(() => {
    return searchedItems.filter((it) => {
      if (view === 'low') {
        return it.qty > 0 && it.qty <= 5 && it.qty_sold_30d >= 1;
      }
      if (view === 'dead') {
        return it.qty > 0 && (it.days_since_sale == null || it.days_since_sale >= 365);
      }
      if (view === 'stockout') {
        return it.qty === 0 && it.days_since_sale != null && it.days_since_sale <= 14;
      }
      if (view === 'negative') {
        return it.qty < 0;
      }
      return it.qty > 0;
    });
  }, [searchedItems, view]);

  const sortedItems = useMemo(
    () => [...filteredItems].sort((a, b) => b.stock_value_cost - a.stock_value_cost),
    [filteredItems],
  );
  const limitedItems = sortedItems.slice(0, 200);

  const supplierSummary = useMemo(() => {
    if (!storeView) return null;
    if (supplierFilter === 'all') return null;
    return (storeView.suppliers || []).find((s) => s.supplier_uuid === supplierFilter) || null;
  }, [storeView, supplierFilter]);

  if (empty) {
    return (
      <div style={{ padding: 24, color: '#94a3b8' }}>
        <h2 style={{ color: '#e2e8f0', marginBottom: 12 }}>📦 ნაშთები</h2>
        <p>მონაცემი ჯერ არ არის ხელმისაწვდომი. გასახდელია „ხელახლა გათვლა" დააჭიროთ.</p>
      </div>
    );
  }

  const tc = data.totals_combined || {};

  return (
    <div style={{ padding: 16 }}>
      <div style={{ marginBottom: 12 }}>
        <h2 style={{ color: '#e2e8f0', marginBottom: 4 }}>📦 ნაშთები</h2>
        <div style={{ color: '#94a3b8', fontSize: 13 }}>
          მონაცემი: {data.snapshot_date || '—'} (Megaplus backup-ის ბოლო სრული დღე)
        </div>
      </div>

      {/* KPI cards — combined */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 18,
      }}>
        <KPI
          label="სრული ნაშთის ღირებულება (ცხუმით)"
          value={fmt(tc.stock_value_cost)}
          sub={`${fmtNum(tc.sku_total)} SKU · ${fmt(tc.stock_value_retail)} საცალო ფასით`}
          color="#22c55e"
        />
        <KPI
          label={'„გაუყიდავის" წილი (365+ დღე)'}
          value={`${(tc.dead_pct || 0).toFixed(1)}%`}
          sub={`${fmt(tc.dead_value_cost)} ფული „ჩარჩენილია" · ${fmtNum(tc.dead_365_plus_count)} პროდუქცია`}
          color={tc.dead_pct > 30 ? '#ef4444' : tc.dead_pct > 15 ? '#eab308' : '#22c55e'}
        />
        <KPI
          label="დღევანდელი გაყიდვა"
          value={fmt2(tc.revenue_today)}
          sub={`${fmtNum2(tc.qty_sold_today)} ცალი`}
          color="#3b82f6"
        />
        <KPI
          label="სიგნალები"
          value={fmtNum(
            (tc.negative_stock_count || 0)
            + (tc.stockout_recent_count || 0)
            + (tc.low_stock_count || 0),
          )}
          sub={`🔴 ${tc.negative_stock_count} უარყოფითი · 🟠 ${tc.stockout_recent_count} stockout · 🟡 ${tc.low_stock_count} ცოტა დარჩა`}
          color="#eab308"
        />
      </div>

      {/* Store tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {storeIds.map((sid) => {
          const s = stores[sid];
          const active = activeStore === sid;
          return (
            <button
              key={sid}
              type="button"
              onClick={() => { setActiveStore(sid); setSupplierFilter('all'); setView('all'); }}
              style={{
                padding: '8px 14px',
                background: active ? '#3b82f6' : '#1e293b',
                color: active ? '#fff' : '#94a3b8',
                border: '1px solid ' + (active ? '#3b82f6' : '#334155'),
                borderRadius: 6,
                cursor: 'pointer',
                fontWeight: active ? 600 : 400,
              }}
            >
              {s.store_name} ({fmtNum(s.totals?.sku_total)} SKU · {fmt(s.totals?.stock_value_cost)})
            </button>
          );
        })}
      </div>

      {storeView && (
        <>
          {/* Controls — placed directly under store tabs for fast access */}
          <section style={{
            marginBottom: 12, background: '#0f172a', padding: 12, borderRadius: 8,
            display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end',
          }}>
            <div style={{ flex: '1 1 200px' }}>
              <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 4 }}>
                კომპანია (მომწოდებელი)
              </label>
              <input
                type="text"
                value={searchCompany}
                onChange={(e) => setSearchCompany(e.target.value)}
                placeholder="მაგ: ჯიდიაი, კოკა-კოლა..."
                style={{
                  width: '100%', padding: 8, background: '#1e293b', color: '#e2e8f0',
                  border: '1px solid #334155', borderRadius: 6, fontSize: 13,
                }}
              />
            </div>
            <div style={{ flex: '1 1 200px' }}>
              <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 4 }}>
                პროდუქტის სახელი
              </label>
              <input
                type="text"
                value={searchName}
                onChange={(e) => setSearchName(e.target.value)}
                placeholder="მაგ: კოკა-კოლა 1.5ლ"
                style={{
                  width: '100%', padding: 8, background: '#1e293b', color: '#e2e8f0',
                  border: '1px solid #334155', borderRadius: 6, fontSize: 13,
                }}
              />
            </div>
            <div style={{ flex: '1 1 180px' }}>
              <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 4 }}>
                შტრიხკოდი / კოდი
              </label>
              <input
                type="text"
                value={searchBarcode}
                onChange={(e) => setSearchBarcode(e.target.value)}
                placeholder="მაგ: 5060337..."
                style={{
                  width: '100%', padding: 8, background: '#1e293b', color: '#e2e8f0',
                  border: '1px solid #334155', borderRadius: 6, fontSize: 13,
                }}
              />
            </div>
            <div style={{ flex: '1 1 240px' }}>
              <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 4 }}>
                მომწოდებელი
              </label>
              <select
                value={supplierFilter}
                onChange={(e) => setSupplierFilter(e.target.value)}
                style={{
                  width: '100%', padding: 8, background: '#1e293b', color: '#e2e8f0',
                  border: '1px solid #334155', borderRadius: 6, fontSize: 13,
                }}
              >
                <option value="all">ყველა მომწოდებელი</option>
                {(storeView.suppliers || [])
                  .filter((s) => s.sku_count > 0)
                  .map((s) => (
                    <option key={s.supplier_uuid || '_unknown'} value={s.supplier_uuid || '_unknown'}>
                      {s.supplier_name} ({s.sku_count} SKU · {fmt(s.stock_value_cost)})
                    </option>
                  ))}
              </select>
            </div>
            <div style={{ flex: '1 1 240px' }}>
              <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 4 }}>
                ნახე
              </label>
              <select
                value={view}
                onChange={(e) => setView(e.target.value)}
                style={{
                  width: '100%', padding: 8, background: '#1e293b', color: '#e2e8f0',
                  border: '1px solid #334155', borderRadius: 6, fontSize: 13,
                }}
              >
                <option value="all">ყველა აქტიური ნაშთი</option>
                <option value="low">🟡 ცოტა დარჩა (≤ 5 ცალი, კვირაში 1+ გაყიდვა)</option>
                <option value="stockout">🟠 ცარიელი, ბოლო 2 კვირაში გაიყიდა</option>
                <option value="dead">⚪ 365+ დღე უმოძრაო</option>
                <option value="negative">🔴 უარყოფითი (შეცდომა)</option>
              </select>
            </div>
          </section>

          {/* Today's sales for the active store — respects search filters */}
          <section style={{ marginBottom: 18 }}>
            <h3 style={{ color: '#e2e8f0', fontSize: 16, marginBottom: 8 }}>
              📅 {storeView.last_complete_day}-ის გაყიდვა — {storeView.store_name}
            </h3>
            <TodaysSalesTable items={searchedItems} />
          </section>

          {/* Supplier summary card */}
          {supplierSummary && (
            <div style={{
              marginBottom: 12, padding: 12, background: '#0f172a',
              border: '1px solid #334155', borderRadius: 8,
              display: 'flex', flexWrap: 'wrap', gap: 16,
            }}>
              <div style={{ flex: '1 1 200px' }}>
                <div style={{ color: '#94a3b8', fontSize: 12 }}>მომწოდებელი</div>
                <div style={{ color: '#e2e8f0', fontWeight: 600 }}>{supplierSummary.supplier_name}</div>
                {supplierSummary.supplier_tax_id && (
                  <div style={{ color: '#64748b', fontSize: 11 }}>ს/კ {supplierSummary.supplier_tax_id}</div>
                )}
              </div>
              <div>
                <div style={{ color: '#94a3b8', fontSize: 12 }}>SKU</div>
                <div style={{ color: '#e2e8f0', fontWeight: 600 }}>{fmtNum(supplierSummary.sku_count)}</div>
              </div>
              <div>
                <div style={{ color: '#94a3b8', fontSize: 12 }}>ნაშთი ცხუმით</div>
                <div style={{ color: '#22c55e', fontWeight: 600 }}>{fmt(supplierSummary.stock_value_cost)}</div>
              </div>
              <div>
                <div style={{ color: '#94a3b8', fontSize: 12 }}>30 დღე გაყიდვა</div>
                <div style={{ color: '#3b82f6', fontWeight: 600 }}>
                  {fmt2(supplierSummary.revenue_30d)} ({fmtNum2(supplierSummary.qty_sold_30d)} ცალი)
                </div>
              </div>
            </div>
          )}

          {/* Main items table */}
          <section style={{ marginBottom: 18 }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              alignItems: 'baseline', marginBottom: 8,
            }}>
              <h3 style={{ color: '#e2e8f0', fontSize: 16, margin: 0 }}>
                პროდუქცია · {fmtNum(filteredItems.length)} ცალი
                {filteredItems.length > 200 && (
                  <span style={{ color: '#94a3b8', fontSize: 12, marginLeft: 8 }}>
                    (ნაჩვენებია პირველი 200, ღირებულების მიხედვით)
                  </span>
                )}
              </h3>
              <div style={{ color: '#94a3b8', fontSize: 12 }}>
                ჯამური ცხუმი: {fmt(filteredItems.reduce((s, it) => s + it.stock_value_cost, 0))}
              </div>
            </div>
            <ItemsTable items={limitedItems} />
          </section>
        </>
      )}
    </div>
  );
}
