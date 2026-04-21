import { useState, useCallback, useMemo } from 'react';
import { STORAGE_KEY, extractTaxId, mergeSupplier } from './financeMerge.js';
import SupplierConcentrationWidget from './components/SupplierConcentrationWidget.jsx';

const SUPPLIER_SORT_OPTIONS = [
  { value: 'debt_asc', label: 'დავალიანება ზრდადობით' },
  { value: 'debt_desc', label: 'დავალიანება კლებადობით' },
];

async function loadXlsxModule() {
  const xlsxModule = await import('xlsx');
  return xlsxModule.default || xlsxModule;
}

export default function Suppliers({
  suppliers,
  localPayments,
  meta,
  persistLocalPayments,
  formatNumber,
  onSupplierClick,
  responseMeta,
  supplierConcentration,
}) {
  const [searchName, setSearchName] = useState('');
  const [supplierSortKey, setSupplierSortKey] = useState('debt_asc');
  const [payAmount, setPayAmount] = useState('');

  const parseMoney = (raw) => {
    const n = parseFloat(String(raw || '').replace(/\s/g, '').replace(',', '.'));
    return Number.isNaN(n) ? 0 : Math.max(0, n);
  };

  const getDisplay = useCallback((sup) => {
    const m = mergeSupplier(sup, localPayments);
    return {
      tid: extractTaxId(sup['ორგანიზაცია']),
      extra: m.extra,
      paid: m.paid,
      debt: m.debt,
      tp0: m.paidBase,
      strictBankPaid: m.bank,
      manualTotal: m.manualTotal,
      paymentScope: sup.payment_scope || 'unpaid_or_unmatched',
      paymentScopeNote: sup.payment_scope_note || '',
    };
  }, [localPayments]);

  const nameNeedle = searchName.trim().toLowerCase();
  const filteredSuppliers = useMemo(() => {
    const filtered = (suppliers || []).filter((s) => {
      const org = String(s['ორგანიზაცია'] || '');
      if (nameNeedle && !org.toLowerCase().includes(nameNeedle)) return false;
      return true;
    });
    const sorted = [...filtered];
    sorted.sort((a, b) => {
      const debtA = Number(getDisplay(a).debt) || 0;
      const debtB = Number(getDisplay(b).debt) || 0;
      if (supplierSortKey === 'debt_asc' && debtA !== debtB) return debtA - debtB;
      if (supplierSortKey === 'debt_desc' && debtA !== debtB) return debtB - debtA;
      return String(a['ორგანიზაცია'] || '').localeCompare(String(b['ორგანიზაცია'] || ''));
    });
    return sorted;
  }, [suppliers, nameNeedle, supplierSortKey, getDisplay]);

  const payVal = parseMoney(payAmount);
  const periodMeta = meta?.period && typeof meta.period === 'object' ? meta.period : {};
  const periodLabel = periodMeta.label_ka || (periodMeta.applied ? 'არჩეული პერიოდი' : 'ყველა პერიოდი');
  const periodCaveat = responseMeta?.period_caveat_ka || meta?.period_caveat_ka || '';
  const canRecord =
    filteredSuppliers.length === 1 &&
    payVal > 0 &&
    extractTaxId(filteredSuppliers[0]['ორგანიზაცია']);

  const handleRecordPayment = () => {
    if (!canRecord) return;
    const tid = extractTaxId(filteredSuppliers[0]['ორგანიზაცია']);
    if (!tid) return;
    const next = { ...localPayments, [tid]: (Number(localPayments[tid]) || 0) + payVal };
    persistLocalPayments(next);
    setPayAmount('');
  };

  const handleClearLocal = () => {
    if (!window.confirm('წავშალოთ ბრაუზერში ჩაწერილი ყველა დამატებითი გადახდა?')) return;
    persistLocalPayments({});
  };

  const hasLocalPayments = Object.values(localPayments).some((v) => Number(v) > 0);

  const handleDownloadSuppliersExcel = async () => {
    if (!filteredSuppliers.length) return;
    const rows = filteredSuppliers.map((sup) => {
      const d = getDisplay(sup);
      return {
        ორგანიზაცია: sup['ორგანიზაცია'],
        რაოდენობა: sup.waybills_count,
        ნომინალური: Number(sup.total_nominal) || 0,
        'რეალური ჯამი': Number(sup.total_effective) || 0,
        'strict ბანკით გადახდა': d.strictBankPaid ?? 0,
        'ნაღდით გადახდა': d.manualTotal ?? 0,
        'სულ გადახდილი': d.paid,
        დავალიანება: d.debt,
        'გადახდის scope': d.paymentScope,
      };
    });
    const XLSX = await loadXlsxModule();
    const ws = XLSX.utils.json_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'მომწოდებლები');
    const stamp = new Date().toISOString().slice(0, 10);
    XLSX.writeFile(wb, `მომწოდებლები_${stamp}.xlsx`);
  };

  const handleDownloadCsv = () => {
    const rows = [['tax_id', 'company', 'amount', 'comment']];
    for (const [tid, amt] of Object.entries(localPayments)) {
      if (Number(amt) > 0) rows.push([tid, '', String(amt), 'ბრაუზერიდან — ჩაამატე manual_payments.csv']);
    }
    if (rows.length < 2) return;
    const bom = '\uFEFF';
    const body = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([bom + body], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'manual_payments_დამატება.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <>
      <SupplierConcentrationWidget payload={supplierConcentration} />
      <div className="controls controls-filters">
        <label className="filter-field">
          <span className="filter-label">კომპანია</span>
          <input
            type="text"
            className="search-input search-input-compact"
            placeholder="სახელი, ნაწილობრივი ტექსტი…"
            value={searchName}
            onChange={(e) => setSearchName(e.target.value)}
            autoComplete="off"
          />
        </label>
        <label className="filter-field">
          <span className="filter-label">სორტი</span>
          <select
            className="pnl-month-select"
            value={supplierSortKey}
            onChange={(e) => setSupplierSortKey(e.target.value)}
          >
            {SUPPLIER_SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="filter-field">
          <span className="filter-label">თანხა (₾)</span>
          <span className="filter-hint">
            იმატებს „სულ გადახდილს", იკლებს „დავალიანებას"
          </span>
          <div className="filter-amount-row">
            <input
              type="text"
              inputMode="decimal"
              className="search-input search-input-compact search-input-amount"
              placeholder="მაგ. 5000"
              value={payAmount}
              onChange={(e) => setPayAmount(e.target.value)}
              autoComplete="off"
            />
            {payAmount.trim() ? (
              <button
                type="button"
                className="btn-clear-filter"
                onClick={() => setPayAmount('')}
                title="გასუფთავება"
              >
                ✕
              </button>
            ) : null}
          </div>
        </label>
        <div className="filter-field filter-field--actions">
          <span className="filter-label">მოქმედება</span>
          <div className="filter-amount-row">
            <button
              type="button"
              className="btn-record-pay"
              disabled={!canRecord}
              onClick={handleRecordPayment}
              title={
                canRecord
                  ? 'ჩაიწერება ბრაუზერში და ემატება სულ გადახდილს'
                  : 'კომპანია უნდა იყოს ზუსტად ერთი ხაზი ძებნაში და თანხა > 0'
              }
            >
              გადახდის ჩაწერა
            </button>
            <button
              type="button"
              className="btn-clear-local"
              onClick={handleClearLocal}
              title="ყველა ლოკალური გადახდის წაშლა"
            >
              გასუფთავება
            </button>
            <button
              type="button"
              className="btn-download-csv"
              disabled={!hasLocalPayments}
              onClick={handleDownloadCsv}
              title="ჩამოტვირთე ხაზები manual_payments.csv-ში ჩასასმელად"
            >
              CSV ჩამოტვირთვა
            </button>
            <button
              type="button"
              className="btn-download-xlsx"
              disabled={filteredSuppliers.length === 0}
              onClick={handleDownloadSuppliersExcel}
              title="ცხრილის მიხედვით (ძებნა თუ ცარიელია — ყველა). ნაღდი + გადახდილი + ვალი = იგივე რაც ეკრანზე"
            >
              Excel ჩამოტვირთვა
            </button>
          </div>
        </div>
      </div>

      {/* Tab Hero */}
      <div className="tab-hero">
        <span className="tab-hero-title">🏢 მომწოდებლები</span>
        <span className="tab-hero-desc">RS ზედნადებების აგრეგაცია, ვალი და გადახდა · {periodLabel}</span>
      </div>

      <div className="controls controls-filters" style={{ marginTop: 12, marginBottom: 12 }}>
        <span className="badge muted">პერიოდი: {periodLabel}</span>
        <span className="badge muted">მომწოდებელი: {filteredSuppliers.length}</span>
      </div>

      <div className="local-pay-banner local-pay-banner--short" role="status">
        ერთი კომპანია ძებნაში → თანხა → <strong>გადახდის ჩაწერა</strong>. strict ბანკი და manual/off-bank
        journal ახლა ცალ-ცალკეა ნაჩვენები. სამუდამოდ: <strong>CSV ჩამოტვირთვა</strong> და ჩაამატე
        ფაილში, შემდეგ გენერაცია.
      </div>

      {periodCaveat ? (
        <div className="trust-banner-sub trust-banner-sub--warn">
          {periodCaveat}
        </div>
      ) : null}

      {payVal > 0 && filteredSuppliers.length > 1 && nameNeedle ? (
        <div className="filter-warning" role="status">
          <strong>რამდენიმე მომწოდებელი ჩანს.</strong> სანამ ჩაწერო, დააზუსტე სახელი, რომ ცხრილში{' '}
          <strong>ერთი</strong> ხაზი დარჩეს.
        </div>
      ) : null}

      <div className="table-wrapper table-premium">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>ორგანიზაცია</th>
              <th>რაოდენობა</th>
              <th title={"ყველა ხაზის \u201Eთანხის\u201C პირდაპირი ჯამი \u2014 გაუქმებულიც თუ ჩაწერილია თანხით. ეს არ არის ვალის ჯამი."}>
                ნომინალური
              </th>
              <th title="უკან დაბრუნების ხაზების თანხების ჯამი (დადებითიც ჩანს, თუ RS ასე აქვს)">
                დაბრუნებული
              </th>
              <th title="ფაქტობრივი ვალდებულება RS-ის მიხედვით: გაუქმებული = 0, უკან დაბრუნება = უარყოფითი. ამიტომ ხშირად ნაკლებია ნომინალზე — ეს ნორმაა.">
                რეალური ჯამი
              </th>
              <th title="მხოლოდ strict bank reconciliation-ით დამტკიცებული supplier payment">
                strict ბანკით გადახდა
              </th>
              <th title="manual_payments.csv + ამ ბრაუზერში ჩაწერილი გადახდები">ნაღდით გადახდა</th>
              <th>სულ გადახდილი</th>
              <th>დავალიანება</th>
              <th>scope</th>
            </tr>
          </thead>
          <tbody>
            {filteredSuppliers.map((sup, idx) => {
              const d = getDisplay(sup);
              return (
                <tr
                  key={`${d.tid || 'x'}-${idx}`}
                  onClick={() => onSupplierClick(sup)}
                  style={{ cursor: 'pointer' }}
                  title="კლიკი — დეტალები"
                >
                  <td>{idx + 1}</td>
                  <td>{sup['ორგანიზაცია']}</td>
                  <td>{sup.waybills_count}</td>
                  <td className="amount-neutral">{formatNumber(sup.total_nominal ?? 0)}</td>
                  <td
                    className={
                      Number(sup.total_returned) === 0
                        ? 'amount-neutral'
                        : Number(sup.total_returned) < 0
                          ? 'amount-negative'
                          : 'amount-neutral'
                    }
                  >
                    {Number(sup.total_returned) !== 0 ? formatNumber(sup.total_returned) : '—'}
                  </td>
                  <td className="amount-positive">{formatNumber(sup.total_effective)}</td>
                  <td className="amount-positive">{formatNumber(d.strictBankPaid ?? 0)}</td>
                  <td className="amount-neutral">{formatNumber(d.manualTotal ?? 0)}</td>
                  <td className="amount-positive">{formatNumber(d.paid)}</td>
                  <td
                    className="amount-negative"
                    style={d.debt > 0 ? { background: 'rgba(239,68,68,0.06)', fontWeight: 700 } : undefined}
                  >
                    {formatNumber(d.debt)}
                  </td>
                  <td>
                    <span className="badge muted" title={d.paymentScopeNote}>
                      {d.paymentScope}
                    </span>
                  </td>
                </tr>
              );
            })}
            {filteredSuppliers.length === 0 && (
              <tr>
                <td colSpan="11" style={{ textAlign: 'center' }}>
                  {periodMeta.applied ? 'არჩეულ პერიოდში მონაცემები არ მოიძებნა' : 'მონაცემები არ მოიძებნა'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
