import { Fragment, useEffect, useMemo, useState } from 'react';
import { fetchApiJson } from './lib/api.js';

const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 0,
});
const fmt = (v) =>
  v === null || v === undefined || !Number.isFinite(Number(v))
    ? '—'
    : GEL.format(Number(v));

const VAT_RATE = 0.18;

const STATUS_META = {
  green: { label: '🟢 OK', color: '#22c55e', bg: '#064e3b' },
  yellow: { label: '🟡 ყურადღება', color: '#eab308', bg: '#422006' },
  red: { label: '🔴 ხარვეზი', color: '#ef4444', bg: '#450a0a' },
  no_declared_data: { label: '⚪ declared არ მაქვს', color: '#94a3b8', bg: '#1e293b' },
  insufficient_data: { label: '⚫ MAX data აკლია', color: '#cbd5e1', bg: '#0f172a' },
};

const CATEGORY_OPTIONS = [
  { value: 'salary_cash', label_ka: 'ხელფასი ხელზე', vat_default: true },
  { value: 'personal_withdrawal', label_ka: 'პერსონალური ამოღება', vat_default: true },
  { value: 'supplier_undocumented', label_ka: 'მომწოდებელი ხელზე', vat_default: false },
  { value: 'business_expense', label_ka: 'ბიზნეს ხარჯი (ქვითრით)', vat_default: false },
  { value: 'advance_to_employee', label_ka: 'ავანსი თანამშრომელს', vat_default: false },
  { value: 'return_to_customer', label_ka: 'დაბრუნება მყიდველს', vat_default: false },
  { value: 'unknown', label_ka: 'ვერ ვიხსენებ', vat_default: true },
];

function StatusChip({ status }) {
  const meta = STATUS_META[status] || STATUS_META.no_declared_data;
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 6,
        fontSize: 12,
        fontWeight: 600,
        color: meta.color,
        background: meta.bg,
        whiteSpace: 'nowrap',
      }}
    >
      {meta.label}
    </span>
  );
}

function SummaryCard({ label, value, hint, color }) {
  return (
    <div
      style={{
        padding: 14,
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: 8,
        minWidth: 180,
        flex: '1 1 180px',
      }}
    >
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>{label}</div>
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
      {hint ? (
        <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>{hint}</div>
      ) : null}
    </div>
  );
}

function DrillDown({ row }) {
  const entries = [
    ['MAX retail (total register)', row.max_pos_ge],
    ['TBC POS', row.tbc_pos_ge],
    ['BOG POS', row.bog_pos_ge],
    ['bank_card (TBC+BOG)', row.bank_card_ge],
    ['cashreg_in (MAX − bank)', row.cashreg_in_ge],
    ['invoices ა/ფ (bruto)', row.invoices_ge],
    ['📦 total_real_ge', row.total_real_ge],
    ['—', null],
    ['cash_supplier (manual_payments)', row.cash_supplier_ge],
    ['cash_classified (journal)', row.cash_classified_ge],
    ['🟡 cash_unaccounted', row.cash_unaccounted_ge],
    ['—', null],
    ['declared (ბუღალტერი)', row.declared_ge],
    ['gap_vs_declared', row.gap_vs_declared_ge],
    ['VAT on unaccounted (18%)', row.vat_on_unaccounted_ge],
  ];
  return (
    <div
      style={{
        padding: 12,
        background: '#0f172a',
        border: '1px solid #1e293b',
        borderRadius: 8,
        marginTop: 6,
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr auto',
          rowGap: 4,
          columnGap: 14,
        }}
      >
        {entries.map(([label, val], i) =>
          label === '—' ? (
            <div
              key={`sep-${i}`}
              style={{ gridColumn: '1 / -1', borderTop: '1px dashed #1e293b', marginTop: 4 }}
            />
          ) : (
            <Fragment key={`row-${i}`}>
              <div style={{ color: '#cbd5e1', fontSize: 13 }}>{label}</div>
              <div
                style={{
                  color: '#e2e8f0',
                  fontSize: 13,
                  fontVariantNumeric: 'tabular-nums',
                  fontWeight: 600,
                }}
              >
                {fmt(val)}
              </div>
            </Fragment>
          )
        )}
      </div>
      {row.cash_classified_by_category &&
      Object.keys(row.cash_classified_by_category).length > 0 ? (
        <div style={{ marginTop: 10, fontSize: 12, color: '#94a3b8' }}>
          კლასიფიცირებული cash-ოუთფლოუ:
          <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
            {Object.entries(row.cash_classified_by_category).map(([cat, sub]) => {
              const catMeta = CATEGORY_OPTIONS.find((c) => c.value === cat);
              return (
                <li key={cat} style={{ color: '#cbd5e1' }}>
                  {catMeta?.label_ka || cat}: {fmt(sub?.total_ge || 0)}
                  {sub?.entries_count ? ` (${sub.entries_count} ჩანაწერი)` : ''}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function CashOutflowForm({ period, defaultUnaccounted, onRecorded }) {
  const [amount, setAmount] = useState('');
  const [purpose, setPurpose] = useState('');
  const [category, setCategory] = useState('salary_cash');
  const [vatApplies, setVatApplies] = useState(true);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const categoryMeta = CATEGORY_OPTIONS.find((c) => c.value === category);

  const handleCategoryChange = (value) => {
    setCategory(value);
    const meta = CATEGORY_OPTIONS.find((c) => c.value === value);
    if (meta) setVatApplies(meta.vat_default);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    const amt = Number(amount);
    if (!Number.isFinite(amt) || amt <= 0) {
      setError('თანხა უნდა იყოს დადებითი რიცხვი.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetchApiJson('/api/vat-reconciliation/cash-outflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          period,
          amount_ge: amt,
          purpose_ka: purpose.trim(),
          category,
          vat_applies: vatApplies,
          notes: notes.trim(),
        }),
      });
      setSuccess(
        `✅ ჩაიწერა: ${fmt(amt)} · ${categoryMeta?.label_ka || category}. დარჩა: ${fmt(
          res.remaining_unaccounted_preview_ge
        )} (VAT preview ${fmt(res.preview_vat_liability_ge)})`
      );
      setAmount('');
      setPurpose('');
      setNotes('');
      onRecorded?.(res);
    } catch (err) {
      setError(err.message || 'ჩაწერა ვერ მოხერხდა.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        padding: 12,
        background: '#0f172a',
        border: '1px solid #334155',
        borderRadius: 8,
        marginTop: 8,
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: 10,
        alignItems: 'end',
      }}
    >
      <div style={{ gridColumn: '1 / -1', fontSize: 12, color: '#94a3b8' }}>
        Cash კლასიფიკაცია · {period} · დარჩა <b>{fmt(defaultUnaccounted)}</b>
      </div>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span style={{ fontSize: 11, color: '#94a3b8' }}>თანხა ₾</span>
        <input
          type="number"
          min="0"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
          style={inputStyle}
        />
      </label>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span style={{ fontSize: 11, color: '#94a3b8' }}>კატეგორია</span>
        <select
          value={category}
          onChange={(e) => handleCategoryChange(e.target.value)}
          style={inputStyle}
        >
          {CATEGORY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label_ka}
            </option>
          ))}
        </select>
      </label>
      <label
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 12,
          color: '#cbd5e1',
        }}
      >
        <input
          type="checkbox"
          checked={vatApplies}
          onChange={(e) => setVatApplies(e.target.checked)}
        />
        დღგ 18%
      </label>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, gridColumn: 'span 2' }}>
        <span style={{ fontSize: 11, color: '#94a3b8' }}>მიზანი (ვიზე, რისთვის)</span>
        <input
          type="text"
          value={purpose}
          onChange={(e) => setPurpose(e.target.value)}
          placeholder="მაგ: გიორგის ხელფასი ივლისისთვის"
          style={inputStyle}
        />
      </label>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, gridColumn: 'span 2' }}>
        <span style={{ fontSize: 11, color: '#94a3b8' }}>შენიშვნა (არასავალდებულო)</span>
        <input
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          style={inputStyle}
        />
      </label>
      <button
        type="submit"
        disabled={submitting}
        style={{
          padding: '8px 14px',
          background: submitting ? '#334155' : '#2563eb',
          color: '#f1f5f9',
          border: 'none',
          borderRadius: 6,
          fontWeight: 600,
          cursor: submitting ? 'wait' : 'pointer',
        }}
      >
        {submitting ? 'ინახება...' : 'ჩაწერა'}
      </button>
      {error ? (
        <div style={{ gridColumn: '1 / -1', color: '#f87171', fontSize: 12 }}>{error}</div>
      ) : null}
      {success ? (
        <div style={{ gridColumn: '1 / -1', color: '#4ade80', fontSize: 12 }}>{success}</div>
      ) : null}
      <div style={{ gridColumn: '1 / -1', fontSize: 11, color: '#64748b' }}>
        ⚠️ ჩანაწერი მოდის `Financial_Analysis/cash_outflow_journal.csv`-ში. მთლიანი ციფრები
        განახლდება pipeline regen-ის შემდეგ (`python generate_dashboard_data.py`).
      </div>
    </form>
  );
}

const inputStyle = {
  padding: '6px 8px',
  background: '#1e293b',
  border: '1px solid #334155',
  borderRadius: 4,
  color: '#e2e8f0',
  fontSize: 13,
};

export default function VATAudit({ reloadKey }) {
  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [yearFilter, setYearFilter] = useState('all');
  const [localRefresh, setLocalRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fetchApiJson('/api/vat-reconciliation')
      .then((json) => {
        if (!active) return;
        setBundle(json);
        setLoading(false);
      })
      .catch((err) => {
        if (!active || err.name === 'AbortError') return;
        setError(err.message);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reloadKey, localRefresh]);

  const rows = bundle?.by_month || [];

  const years = useMemo(() => {
    const set = new Set();
    rows.forEach((r) => set.add((r.period || '').slice(0, 4)));
    return ['all', ...Array.from(set).sort()];
  }, [rows]);

  const filteredRows = useMemo(() => {
    if (yearFilter === 'all') return rows;
    return rows.filter((r) => (r.period || '').startsWith(yearFilter));
  }, [rows, yearFilter]);

  const totals = useMemo(() => {
    const t = {
      declared: 0,
      real: 0,
      gap: 0,
      unaccounted: 0,
      bank_card: 0,
      cashreg: 0,
      invoices: 0,
      months_with_declared: 0,
      red: 0,
      yellow: 0,
      green: 0,
    };
    filteredRows.forEach((r) => {
      t.real += Number(r.total_real_ge) || 0;
      t.bank_card += Number(r.bank_card_ge) || 0;
      t.cashreg += Number(r.cashreg_in_ge) || 0;
      t.invoices += Number(r.invoices_ge) || 0;
      t.unaccounted += Number(r.cash_unaccounted_ge) || 0;
      if (r.declared_ge != null) {
        t.declared += Number(r.declared_ge) || 0;
        t.gap += Number(r.gap_vs_declared_ge) || 0;
        t.months_with_declared += 1;
      }
      if (r.status === 'red') t.red += 1;
      else if (r.status === 'yellow') t.yellow += 1;
      else if (r.status === 'green') t.green += 1;
    });
    t.vat_exposure = t.unaccounted * VAT_RATE;
    return t;
  }, [filteredRows]);

  if (loading) {
    return (
      <div style={{ padding: 24, color: '#94a3b8' }}>VAT reconciliation იტვირთება…</div>
    );
  }
  if (error) {
    return <div style={{ padding: 24, color: '#f87171' }}>შეცდომა: {error}</div>;
  }
  if (!rows.length) {
    return (
      <div style={{ padding: 24, color: '#94a3b8' }}>
        VAT reconciliation მონაცემები არ მოიძებნა. pipeline regen საჭიროა.
      </div>
    );
  }

  return (
    <div style={{ padding: 16 }}>
      <div
        style={{
          marginBottom: 16,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <h2 style={{ margin: '0 0 4px 0', color: '#f1f5f9' }}>🧾 VAT &amp; აუდიტი</h2>
          <div style={{ fontSize: 13, color: '#94a3b8' }}>
            Declared (ბუღალტერი) vs რეალური pipeline ბრუნვა · month-by-month ×{' '}
            {filteredRows.length} თვე · status: 🟢 {totals.green} · 🟡 {totals.yellow} · 🔴{' '}
            {totals.red}
          </div>
        </div>
        <a
          href="/api/vat-reconciliation/export"
          download
          style={{
            padding: '8px 14px',
            background: '#16a34a',
            color: '#f1f5f9',
            border: 'none',
            borderRadius: 6,
            fontWeight: 600,
            fontSize: 13,
            textDecoration: 'none',
            whiteSpace: 'nowrap',
          }}
          title="ექსელ ექსპორტი აუდიტორის/ბუღალტერის გადასაცემად"
        >
          📥 Excel ექსპორტი
        </a>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 18 }}>
        <SummaryCard
          label="Declared (ბუღალტერი)"
          value={fmt(totals.declared)}
          hint={`${totals.months_with_declared} თვე declared`}
        />
        <SummaryCard
          label="🟢 რეალური pipeline (total_real)"
          value={fmt(totals.real)}
          hint="MAX − bank-overlap + bank_card + invoices"
        />
        <SummaryCard
          label="🔴 Gap vs declared"
          value={fmt(totals.gap)}
          color={totals.gap > 0 ? '#f87171' : '#4ade80'}
          hint={
            totals.declared > 0
              ? `${((totals.gap / totals.declared) * 100).toFixed(1)}% undeclared`
              : '—'
          }
        />
        <SummaryCard
          label="cash_unaccounted"
          value={fmt(totals.unaccounted)}
          color="#fbbf24"
          hint="კლასიფიკაციას ელოდება"
        />
        <SummaryCard
          label="VAT exposure (18%)"
          value={fmt(totals.vat_exposure)}
          color="#fb923c"
          hint="worst-case თუ არავინ კლასიფიცირდება"
        />
      </div>

      <div
        style={{
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          marginBottom: 10,
          flexWrap: 'wrap',
        }}
      >
        <span style={{ fontSize: 12, color: '#94a3b8' }}>წელი:</span>
        {years.map((y) => (
          <button
            key={y}
            onClick={() => setYearFilter(y)}
            style={{
              padding: '4px 10px',
              background: yearFilter === y ? '#2563eb' : '#1e293b',
              color: '#f1f5f9',
              border: '1px solid #334155',
              borderRadius: 6,
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            {y === 'all' ? 'ყველა' : y}
          </button>
        ))}
        <div style={{ marginLeft: 'auto', fontSize: 11, color: '#64748b' }}>
          generated: {bundle?.generated_at || '—'}
        </div>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: 13,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          <thead>
            <tr style={{ background: '#0f172a', color: '#94a3b8' }}>
              <th style={thStyle}>თვე</th>
              <th style={thStyleRight}>declared</th>
              <th style={thStyleRight}>bank_card</th>
              <th style={thStyleRight}>cashreg_in</th>
              <th style={thStyleRight}>invoices</th>
              <th style={thStyleRight}>total_real</th>
              <th style={thStyleRight}>gap</th>
              <th style={thStyleRight}>unaccounted</th>
              <th style={thStyle}>status</th>
              <th style={thStyle}>action</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((r) => {
              const isOpen = expanded === r.period;
              const gap = r.gap_vs_declared_ge;
              return (
                <Fragment key={r.period}>
                  <tr
                    style={{
                      background: isOpen ? '#1e293b' : 'transparent',
                      borderBottom: '1px solid #1e293b',
                      cursor: 'pointer',
                    }}
                    onClick={() => setExpanded(isOpen ? null : r.period)}
                  >
                    <td style={tdStyle}>
                      <b>{r.period}</b>
                      {r.needs_user_input ? (
                        <span
                          style={{ marginLeft: 6, fontSize: 11, color: '#fbbf24' }}
                        >
                          ⚠️
                        </span>
                      ) : null}
                    </td>
                    <td style={tdRight}>{fmt(r.declared_ge)}</td>
                    <td style={tdRight}>{fmt(r.bank_card_ge)}</td>
                    <td style={tdRight}>{fmt(r.cashreg_in_ge)}</td>
                    <td style={tdRight}>{fmt(r.invoices_ge)}</td>
                    <td style={{ ...tdRight, fontWeight: 700 }}>{fmt(r.total_real_ge)}</td>
                    <td
                      style={{
                        ...tdRight,
                        color:
                          gap == null
                            ? '#94a3b8'
                            : gap > 0
                            ? '#f87171'
                            : '#4ade80',
                        fontWeight: 600,
                      }}
                    >
                      {gap == null ? '—' : (gap > 0 ? '+' : '') + fmt(gap).replace('₾', '').trim() + ' ₾'}
                    </td>
                    <td style={{ ...tdRight, color: '#fbbf24' }}>
                      {fmt(r.cash_unaccounted_ge)}
                    </td>
                    <td style={tdStyle}>
                      <StatusChip status={r.status} />
                    </td>
                    <td style={tdStyle}>
                      <span style={{ color: '#60a5fa', fontSize: 12 }}>
                        {isOpen ? '▾ დახურე' : '▸ ნახე'}
                      </span>
                    </td>
                  </tr>
                  {isOpen ? (
                    <tr style={{ background: '#0f172a' }}>
                      <td colSpan={10} style={{ padding: '8px 12px' }}>
                        <DrillDown row={r} />
                        {r.cash_unaccounted_ge > 0 ? (
                          <CashOutflowForm
                            period={r.period}
                            defaultUnaccounted={r.cash_unaccounted_ge}
                            onRecorded={() => setLocalRefresh((k) => k + 1)}
                          />
                        ) : (
                          <div
                            style={{
                              marginTop: 8,
                              padding: 10,
                              background: '#064e3b',
                              border: '1px solid #065f46',
                              borderRadius: 6,
                              color: '#a7f3d0',
                              fontSize: 12,
                            }}
                          >
                            ✅ ამ თვეში cash_unaccounted = 0 · classification საჭირო არ არის
                          </div>
                        )}
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
          <tfoot>
            <tr style={{ background: '#0f172a', color: '#e2e8f0', fontWeight: 700 }}>
              <td style={tdStyle}>ჯამი</td>
              <td style={tdRight}>{fmt(totals.declared)}</td>
              <td style={tdRight}>{fmt(totals.bank_card)}</td>
              <td style={tdRight}>{fmt(totals.cashreg)}</td>
              <td style={tdRight}>{fmt(totals.invoices)}</td>
              <td style={tdRight}>{fmt(totals.real)}</td>
              <td
                style={{
                  ...tdRight,
                  color: totals.gap > 0 ? '#f87171' : '#4ade80',
                }}
              >
                {(totals.gap > 0 ? '+' : '') + fmt(totals.gap).replace('₾', '').trim() + ' ₾'}
              </td>
              <td style={{ ...tdRight, color: '#fbbf24' }}>{fmt(totals.unaccounted)}</td>
              <td colSpan={2}></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div
        style={{
          marginTop: 16,
          fontSize: 12,
          color: '#64748b',
          lineHeight: 1.5,
        }}
      >
        💡 <b>Identity</b>: total_real = bank_card + cashreg_in + invoices ·{' '}
        cashreg_in = max(0, MAX − bank_card) · gap = total_real − declared ·{' '}
        VAT exposure = cash_unaccounted × 18%.
        <br />
        💡 <b>cash_unaccounted</b> კლასიფიკაცია <code>cash_outflow_journal.csv</code>-ში
        (salary_cash / supplier_undocumented / business_expense / …) ამცირებს VAT exposure-ს.
        თანხა რჩება იმ ნაწილზე, რისთვისაც დღგ ფორმალურად გადაცხდება.
      </div>
    </div>
  );
}

const thStyle = {
  padding: '8px 10px',
  textAlign: 'left',
  borderBottom: '2px solid #1e293b',
  fontSize: 12,
  fontWeight: 600,
};
const thStyleRight = { ...thStyle, textAlign: 'right' };
const tdStyle = {
  padding: '8px 10px',
  color: '#e2e8f0',
  textAlign: 'left',
};
const tdRight = { ...tdStyle, textAlign: 'right' };
