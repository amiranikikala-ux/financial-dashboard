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
    <div
      style={{
        padding: 16,
        background: '#1e293b',
        border: `1px solid ${color || '#334155'}`,
        borderRadius: 10,
        flex: '1 1 220px',
        minWidth: 220,
      }}
    >
      <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 6 }}>{label}</div>
      <div
        style={{
          fontSize: 22,
          fontWeight: 700,
          color: color || '#e2e8f0',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value}
      </div>
      {sub && (
        <div style={{ color: '#64748b', fontSize: 11, marginTop: 4 }}>{sub}</div>
      )}
    </div>
  );
}

function downloadCsv(rows, columns, filename) {
  if (!rows || !rows.length) return;
  const headers = columns.map((c) => c.label);
  const lines = [headers.join(',')];
  for (const row of rows) {
    const vals = columns.map((c) => {
      let v = c.value(row);
      if (v == null) v = '';
      v = String(v).replace(/"/g, '""');
      if (v.includes(',') || v.includes('"') || v.includes('\n')) {
        v = `"${v}"`;
      }
      return v;
    });
    lines.push(vals.join(','));
  }
  const blob = new Blob(['﻿' + lines.join('\n')], {
    type: 'text/csv;charset=utf-8;',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function DeadTable({ rows }) {
  if (!rows || !rows.length) {
    return (
      <div style={{ color: '#64748b', padding: 12 }}>
        (ცარიელია — გასასუფთავებელი არ არის)
      </div>
    );
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 13,
          background: '#0f172a',
        }}
      >
        <thead>
          <tr style={{ background: '#1e293b', color: '#94a3b8' }}>
            <th style={{ padding: 8, textAlign: 'left' }}>პროდუქტი</th>
            <th style={{ padding: 8, textAlign: 'left' }}>შტრიხკოდი</th>
            <th style={{ padding: 8, textAlign: 'left' }}>მომწოდებელი</th>
            <th style={{ padding: 8, textAlign: 'right' }}>ნაშთი</th>
            <th style={{ padding: 8, textAlign: 'right' }}>თვითღ.</th>
            <th style={{ padding: 8, textAlign: 'right' }}>ღირებულება</th>
            <th style={{ padding: 8, textAlign: 'left' }}>ბოლო გაყიდვა</th>
            <th style={{ padding: 8, textAlign: 'right' }}>დღე</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={`d-${r.product_id}`}
              style={{ borderTop: '1px solid #1e293b' }}
            >
              <td style={{ padding: 8 }}>{r.product_name}</td>
              <td style={{ padding: 8, color: '#94a3b8', fontFamily: 'monospace' }}>
                {r.barcode}
              </td>
              <td style={{ padding: 8, color: '#94a3b8' }}>{r.supplier_name}</td>
              <td
                style={{
                  padding: 8,
                  textAlign: 'right',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {fmtNum2(r.qty)}
              </td>
              <td
                style={{
                  padding: 8,
                  textAlign: 'right',
                  color: '#94a3b8',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {fmt2(r.cost_unit)}
              </td>
              <td
                style={{
                  padding: 8,
                  textAlign: 'right',
                  fontWeight: 600,
                  color: '#fbbf24',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {fmt(r.stock_value_cost)}
              </td>
              <td style={{ padding: 8, color: '#94a3b8' }}>
                {r.last_sale_date || '—'}
              </td>
              <td
                style={{
                  padding: 8,
                  textAlign: 'right',
                  color: '#ef4444',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {r.days_since_sale != null ? fmtNum(r.days_since_sale) : '∞'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NegativeTable({ rows }) {
  if (!rows || !rows.length) {
    return (
      <div style={{ color: '#64748b', padding: 12 }}>
        (ცარიელია — გასასუფთავებელი არ არის)
      </div>
    );
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 13,
          background: '#0f172a',
        }}
      >
        <thead>
          <tr style={{ background: '#1e293b', color: '#94a3b8' }}>
            <th style={{ padding: 8, textAlign: 'left' }}>პროდუქტი</th>
            <th style={{ padding: 8, textAlign: 'left' }}>შტრიხკოდი</th>
            <th style={{ padding: 8, textAlign: 'left' }}>მომწოდებელი</th>
            <th style={{ padding: 8, textAlign: 'right' }}>ნაშთი</th>
            <th style={{ padding: 8, textAlign: 'right' }}>თვითღ.</th>
            <th style={{ padding: 8, textAlign: 'right' }}>გავიდა 30 დღე</th>
            <th style={{ padding: 8, textAlign: 'left' }}>ბოლო გაყიდვა</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={`n-${r.product_id}`}
              style={{ borderTop: '1px solid #1e293b' }}
            >
              <td style={{ padding: 8 }}>{r.product_name}</td>
              <td style={{ padding: 8, color: '#94a3b8', fontFamily: 'monospace' }}>
                {r.barcode}
              </td>
              <td style={{ padding: 8, color: '#94a3b8' }}>{r.supplier_name}</td>
              <td
                style={{
                  padding: 8,
                  textAlign: 'right',
                  color: '#ef4444',
                  fontWeight: 600,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {fmtNum2(r.qty)}
              </td>
              <td
                style={{
                  padding: 8,
                  textAlign: 'right',
                  color: '#94a3b8',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {fmt2(r.cost_unit)}
              </td>
              <td
                style={{
                  padding: 8,
                  textAlign: 'right',
                  color: '#94a3b8',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {fmtNum2(r.qty_sold_30d)}
              </td>
              <td style={{ padding: 8, color: '#94a3b8' }}>
                {r.last_sale_date || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PhantomTable({ rows }) {
  if (!rows || !rows.length) {
    return (
      <div style={{ color: '#64748b', padding: 12 }}>
        (ცარიელია — გასასუფთავებელი არ არის)
      </div>
    );
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 13,
          background: '#0f172a',
        }}
      >
        <thead>
          <tr style={{ background: '#1e293b', color: '#94a3b8' }}>
            <th style={{ padding: 8, textAlign: 'left' }}>Phantom პროდუქტი</th>
            <th style={{ padding: 8, textAlign: 'left' }}>შტრიხკოდი</th>
            <th style={{ padding: 8, textAlign: 'left' }}>აქტიური (იგივე შტრიხკოდი)</th>
            <th style={{ padding: 8, textAlign: 'right' }}>ნაშთი</th>
            <th style={{ padding: 8, textAlign: 'right' }}>თვითღ.</th>
            <th style={{ padding: 8, textAlign: 'right' }}>ღირებულება</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={`p-${r.product_id}`}
              style={{ borderTop: '1px solid #1e293b' }}
            >
              <td style={{ padding: 8 }}>{r.phantom_name}</td>
              <td style={{ padding: 8, color: '#94a3b8', fontFamily: 'monospace' }}>
                {r.barcode}
              </td>
              <td style={{ padding: 8, color: '#94a3b8' }}>
                {r.active_name_on_same_barcode}
              </td>
              <td
                style={{
                  padding: 8,
                  textAlign: 'right',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {fmtNum2(r.qty)}
              </td>
              <td
                style={{
                  padding: 8,
                  textAlign: 'right',
                  color: '#94a3b8',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {fmt2(r.cost_unit)}
              </td>
              <td
                style={{
                  padding: 8,
                  textAlign: 'right',
                  fontWeight: 600,
                  color: '#a78bfa',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {fmt(r.stock_value_cost)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Cleanup({ inventoryCleanup }) {
  const bundle = inventoryCleanup || {};
  const stores = bundle.stores || {};
  const storeIds = Object.keys(stores);
  const totals = bundle.totals_combined || {};

  const [activeStore, setActiveStore] = useState('all');
  const [activeTab, setActiveTab] = useState('dead');
  const [search, setSearch] = useState('');
  const [maxRows, setMaxRows] = useState(100);

  // Combine rows across stores
  const combineRows = (key) => {
    const ids = activeStore === 'all' ? storeIds : [activeStore];
    const rows = [];
    for (const sid of ids) {
      const s = stores[sid] || {};
      const list = s[key] || [];
      const tag = s.store_name || sid;
      for (const r of list) {
        rows.push({ ...r, _store: tag });
      }
    }
    return rows;
  };

  const allDead = useMemo(() => combineRows('dead_365_plus'), [stores, activeStore]);
  const allNeg = useMemo(() => combineRows('negative_stock'), [stores, activeStore]);
  const allPhantom = useMemo(() => combineRows('phantom_duplicates'), [stores, activeStore]);

  const filterRows = (rows, keys) => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase().trim();
    return rows.filter((r) =>
      keys.some((k) => String(r[k] || '').toLowerCase().includes(q))
    );
  };

  const deadFiltered = useMemo(
    () => filterRows(allDead, ['product_name', 'barcode', 'supplier_name']),
    [allDead, search]
  );
  const negFiltered = useMemo(
    () => filterRows(allNeg, ['product_name', 'barcode', 'supplier_name']),
    [allNeg, search]
  );
  const phantomFiltered = useMemo(
    () =>
      filterRows(allPhantom, [
        'phantom_name',
        'active_name_on_same_barcode',
        'barcode',
      ]),
    [allPhantom, search]
  );

  if (!bundle.available) {
    return (
      <div style={{ padding: 24, color: '#94a3b8' }}>
        გასასუფთავებელი ნაშთის მონაცემი ცარიელია. გადატვირთეთ pipeline.
      </div>
    );
  }

  const storeButton = (id, label) => (
    <button
      key={id}
      onClick={() => setActiveStore(id)}
      style={{
        padding: '6px 14px',
        background: activeStore === id ? '#3b82f6' : '#1e293b',
        color: activeStore === id ? '#fff' : '#94a3b8',
        border: '1px solid #334155',
        borderRadius: 6,
        cursor: 'pointer',
        fontSize: 13,
      }}
    >
      {label}
    </button>
  );

  const tabButton = (id, label, count) => (
    <button
      key={id}
      onClick={() => setActiveTab(id)}
      style={{
        padding: '8px 16px',
        background: activeTab === id ? '#0ea5e9' : '#1e293b',
        color: activeTab === id ? '#fff' : '#94a3b8',
        border: '1px solid #334155',
        borderRadius: 6,
        cursor: 'pointer',
        fontSize: 14,
        fontWeight: activeTab === id ? 600 : 400,
      }}
    >
      {label} <span style={{ opacity: 0.7 }}>({fmtNum(count)})</span>
    </button>
  );

  const csvCols = {
    dead: [
      { label: 'მაღაზია', value: (r) => r._store },
      { label: 'პროდუქტი', value: (r) => r.product_name },
      { label: 'შტრიხკოდი', value: (r) => r.barcode },
      { label: 'მომწოდებელი', value: (r) => r.supplier_name },
      { label: 'ნაშთი', value: (r) => r.qty },
      { label: 'თვითღ.', value: (r) => r.cost_unit },
      { label: 'ღირებულება', value: (r) => r.stock_value_cost.toFixed(2) },
      { label: 'ბოლო გაყიდვა', value: (r) => r.last_sale_date || '' },
      { label: 'დღე გავიდა', value: (r) => r.days_since_sale ?? '' },
    ],
    neg: [
      { label: 'მაღაზია', value: (r) => r._store },
      { label: 'პროდუქტი', value: (r) => r.product_name },
      { label: 'შტრიხკოდი', value: (r) => r.barcode },
      { label: 'მომწოდებელი', value: (r) => r.supplier_name },
      { label: 'ნაშთი', value: (r) => r.qty },
      { label: 'თვითღ.', value: (r) => r.cost_unit },
      { label: 'გავიდა 30 დღე', value: (r) => r.qty_sold_30d },
      { label: 'ბოლო გაყიდვა', value: (r) => r.last_sale_date || '' },
    ],
    phantom: [
      { label: 'მაღაზია', value: (r) => r._store },
      { label: 'Phantom პროდუქტი', value: (r) => r.phantom_name },
      { label: 'შტრიხკოდი', value: (r) => r.barcode },
      { label: 'აქტიური', value: (r) => r.active_name_on_same_barcode },
      { label: 'ნაშთი', value: (r) => r.qty },
      { label: 'თვითღ.', value: (r) => r.cost_unit },
      { label: 'ღირებულება', value: (r) => r.stock_value_cost.toFixed(2) },
    ],
  };

  const currentRows =
    activeTab === 'dead'
      ? deadFiltered
      : activeTab === 'neg'
      ? negFiltered
      : phantomFiltered;
  const currentCsvCols = csvCols[activeTab];
  const csvName =
    activeTab === 'dead'
      ? 'gasaspuftavebeli_mkvdari.csv'
      : activeTab === 'neg'
      ? 'gasaspuftavebeli_uaryofiti.csv'
      : 'gasaspuftavebeli_phantom.csv';

  return (
    <div style={{ padding: 24, color: '#e2e8f0', maxWidth: 1400, margin: '0 auto' }}>
      <h2 style={{ fontSize: 24, marginBottom: 4 }}>🧹 ნაშთის გასუფთავება</h2>
      <p style={{ color: '#64748b', fontSize: 13, marginTop: 0, marginBottom: 20 }}>
        გასასწორებელი პროდუქცია MegaPlus-ში. გასწორების შემდეგ (ხელახლა გათვლა → F5)
        გასწორებული ჩამოვარდება სიიდან.{' '}
        {bundle.snapshot_date && <>· snapshot: <b>{bundle.snapshot_date}</b></>}
      </p>

      {/* KPI cards */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
        <KPI
          label="💀 მკვდარი (365+ დღე)"
          value={fmtNum(totals.dead_count || 0)}
          sub={`${fmt(totals.dead_value_cost || 0)} ღირებულება`}
          color="#fbbf24"
        />
        <KPI
          label="🔴 უარყოფითი ნაშთი"
          value={fmtNum(totals.negative_count || 0)}
          sub={`${fmt(totals.negative_value_cost || 0)} აბსოლუტური ღირებულება`}
          color="#ef4444"
        />
        <KPI
          label="👥 Phantom დუბლიკატი"
          value={fmtNum(totals.phantom_count || 0)}
          sub={`${fmt(totals.phantom_value_cost || 0)} თვითღ. / ${fmt(totals.phantom_value_retail || 0)} ფასი`}
          color="#a78bfa"
        />
      </div>

      {/* Store toggle */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
        <span style={{ color: '#94a3b8', fontSize: 12, marginRight: 6 }}>მაღაზია:</span>
        {storeButton('all', 'ყველა')}
        {storeIds.map((sid) =>
          storeButton(sid, (stores[sid] || {}).store_name || sid)
        )}
      </div>

      {/* Tab buttons */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {tabButton('dead', '💀 მკვდარი', deadFiltered.length)}
        {tabButton('neg', '🔴 უარყოფითი', negFiltered.length)}
        {tabButton('phantom', '👥 Phantom', phantomFiltered.length)}
      </div>

      {/* Search + CSV */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="🔎 ძებნა: სახელი / შტრიხკოდი / მომწოდებელი"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            flex: '1 1 300px',
            minWidth: 250,
            padding: '8px 12px',
            background: '#1e293b',
            color: '#e2e8f0',
            border: '1px solid #334155',
            borderRadius: 6,
            fontSize: 13,
          }}
        />
        <select
          value={maxRows}
          onChange={(e) => setMaxRows(Number(e.target.value))}
          style={{
            padding: '8px 12px',
            background: '#1e293b',
            color: '#e2e8f0',
            border: '1px solid #334155',
            borderRadius: 6,
            fontSize: 13,
          }}
        >
          <option value={100}>100 row</option>
          <option value={500}>500 row</option>
          <option value={2000}>2000 row</option>
          <option value={999999}>ყველა</option>
        </select>
        <button
          onClick={() => downloadCsv(currentRows, currentCsvCols, csvName)}
          disabled={!currentRows.length}
          style={{
            padding: '8px 14px',
            background: currentRows.length ? '#10b981' : '#334155',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            cursor: currentRows.length ? 'pointer' : 'not-allowed',
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          💾 CSV ({fmtNum(currentRows.length)})
        </button>
      </div>

      <div style={{ color: '#64748b', fontSize: 12, marginBottom: 8 }}>
        ნაჩვენებია: {fmtNum(Math.min(currentRows.length, maxRows))} /{' '}
        {fmtNum(currentRows.length)} row
      </div>

      {/* The selected table */}
      {activeTab === 'dead' && <DeadTable rows={deadFiltered.slice(0, maxRows)} />}
      {activeTab === 'neg' && <NegativeTable rows={negFiltered.slice(0, maxRows)} />}
      {activeTab === 'phantom' && (
        <PhantomTable rows={phantomFiltered.slice(0, maxRows)} />
      )}

      <div style={{ marginTop: 24, padding: 16, background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, fontSize: 13, color: '#94a3b8' }}>
        <div style={{ marginBottom: 8, fontWeight: 600, color: '#e2e8f0' }}>
          💡 როგორ ვმუშაობთ
        </div>
        <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 1.7 }}>
          <li>აქედან CSV ჩამოტვირთეთ ან პროდუქტი ერთად ნახეთ</li>
          <li>MegaPlus-ში ფიზიკურად შეამოწმეთ — არის თუ არ არის</li>
          <li>თუ არ არის → MegaPlus-ში ჩამოწერა / კორექცია</li>
          <li>გადატვირთვის ღილაკი ზევით (5-10 წთ) → F5</li>
          <li>გასწორებული ჩამოვარდება ამ სიიდან ავტომატურად</li>
        </ol>
      </div>
    </div>
  );
}
