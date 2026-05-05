import { useState, useCallback, useMemo } from 'react';
import { extractTaxId, mergeSupplier } from './financeMerge.js';
import { fetchApiJson } from './lib/api.js';
import SupplierConcentrationWidget from './components/SupplierConcentrationWidget.jsx';
import CollapsibleSection from './components/CollapsibleSection.jsx';

const SUPPLIER_SORT_OPTIONS = [
  { value: 'debt_asc', label: 'ვალი ↑' },
  { value: 'debt_desc', label: 'ვალი ↓' },
];

const PAYMENT_SCOPE_LABEL_KA = {
  strict_bank_only: 'ბანკით დადასტურებული',
  manual_only: 'მხოლოდ ნაღდით / ჟურნალით',
  strict_and_manual: 'ბანკით + ჟურნალით',
  unpaid_or_unmatched: 'გადაუხდელი / დაუდგენელი',
};

function scopeLabel(scope) {
  return PAYMENT_SCOPE_LABEL_KA[scope] || scope || '—';
}

const NON_RS_NAME_RX = /არა.?\s*RS\s+ზედნადებ/i;

function isNonRsSyntheticRow(sup) {
  return NON_RS_NAME_RX.test(String(sup?.['ორგანიზაცია'] || ''));
}

async function loadXlsxModule() {
  const xlsxModule = await import('xlsx');
  return xlsxModule.default || xlsxModule;
}

const AVATAR_GRADIENTS = [
  'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
  'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
  'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
  'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
  'linear-gradient(135deg, #ec4899 0%, #a855f7 100%)',
  'linear-gradient(135deg, #14b8a6 0%, #10b981 100%)',
  'linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%)',
  'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
  'linear-gradient(135deg, #ef4444 0%, #f59e0b 100%)',
  'linear-gradient(135deg, #a855f7 0%, #6366f1 100%)',
];

function stripTaxIdPrefix(org) {
  return String(org || '').replace(/^\([^)]+\)\s*[-–—]?\s*/u, '').trim();
}

function orgInitial(org) {
  const clean = stripTaxIdPrefix(org);
  return (clean.charAt(0) || '?').toUpperCase();
}

function orgGradient(org) {
  const str = stripTaxIdPrefix(org) || String(org || '');
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) | 0;
  }
  return AVATAR_GRADIENTS[Math.abs(hash) % AVATAR_GRADIENTS.length];
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
  const [recordedFlash, setRecordedFlash] = useState(false);
  const [archiveOverrides, setArchiveOverrides] = useState({});
  const [pendingArchiveTid, setPendingArchiveTid] = useState(null);
  const [archiveError, setArchiveError] = useState(null);

  const isArchived = useCallback((sup) => {
    const tid = extractTaxId(sup['ორგანიზაცია']);
    if (tid && tid in archiveOverrides) return archiveOverrides[tid];
    return Boolean(sup.archived);
  }, [archiveOverrides]);

  const handleToggleArchive = useCallback(async (sup, becomeArchived) => {
    const tid = extractTaxId(sup['ორგანიზაცია']);
    if (!tid) {
      setArchiveError('ამ ფირმას საიდენტიფიკაციო ნომერი არ აქვს — არქივი ვერ ჩაიწერა.');
      return;
    }
    setPendingArchiveTid(tid);
    setArchiveError(null);
    try {
      await fetchApiJson('/api/suppliers/archive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tax_id: tid, archived: becomeArchived }),
      });
      setArchiveOverrides((prev) => ({ ...prev, [tid]: becomeArchived }));
    } catch (err) {
      setArchiveError(`ვერ შეინახა: ${err?.message || err}`);
    } finally {
      setPendingArchiveTid(null);
    }
  }, []);

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

  const { realSuppliers, archivedSuppliers, nonRsRows } = useMemo(() => {
    const real = [];
    const archived = [];
    const nonRs = [];
    for (const sup of filteredSuppliers) {
      if (isNonRsSyntheticRow(sup)) nonRs.push(sup);
      else if (isArchived(sup)) archived.push(sup);
      else real.push(sup);
    }
    return { realSuppliers: real, archivedSuppliers: archived, nonRsRows: nonRs };
  }, [filteredSuppliers, isArchived]);

  const nonRsTotalBank = useMemo(
    () => nonRsRows.reduce((sum, sup) => sum + (Number(getDisplay(sup).strictBankPaid) || 0), 0),
    [nonRsRows, getDisplay],
  );

  const payVal = parseMoney(payAmount);
  const showCashColumn = useMemo(
    () => realSuppliers.some((sup) => Number(getDisplay(sup).manualTotal) > 0),
    [realSuppliers, getDisplay],
  );
  const tableColumnCount = showCashColumn ? 8 : 7;
  const periodMeta = meta?.period && typeof meta.period === 'object' ? meta.period : {};
  const periodLabel = periodMeta.label_ka || (periodMeta.applied ? 'არჩეული პერიოდი' : 'ყველა პერიოდი');
  const periodCaveat = responseMeta?.period_caveat_ka || meta?.period_caveat_ka || '';
  const selectedOne = realSuppliers.length === 1 ? realSuppliers[0] : null;
  const selectedDisplay = selectedOne ? getDisplay(selectedOne) : null;
  const canRecord = Boolean(
    selectedOne && payVal > 0 && extractTaxId(selectedOne['ორგანიზაცია']),
  );

  const handleRecordPayment = () => {
    if (!canRecord) return;
    const tid = extractTaxId(selectedOne['ორგანიზაცია']);
    if (!tid) return;
    const next = { ...localPayments, [tid]: (Number(localPayments[tid]) || 0) + payVal };
    persistLocalPayments(next);
    setPayAmount('');
    setRecordedFlash(true);
    setTimeout(() => setRecordedFlash(false), 1400);
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
    const bom = '﻿';
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
      <div className="sup-toolbar">
        <div className="sup-toolbar-title">
          <span className="sup-toolbar-glyph" aria-hidden="true">🏢</span>
          <h2 className="sup-toolbar-h">მომწოდებლები</h2>
          <span className="sup-toolbar-count" title={`სულ ${realSuppliers.length} მომწოდებელი${nonRsRows.length ? ` (+ ${nonRsRows.length} RS-ის გარეშე)` : ''}`}>
            {realSuppliers.length}
          </span>
          <span className="sup-toolbar-period">{periodLabel}</span>
        </div>

        <div className="sup-toolbar-search">
          <svg className="sup-toolbar-search-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            type="text"
            className="sup-toolbar-search-input"
            placeholder="ძებნა — სახელი ან ნაწილი…"
            value={searchName}
            onChange={(e) => setSearchName(e.target.value)}
            autoComplete="off"
          />
          {searchName.trim() ? (
            <button
              type="button"
              className="sup-toolbar-search-clear"
              onClick={() => setSearchName('')}
              aria-label="ძებნის გასუფთავება"
            >
              ✕
            </button>
          ) : null}
        </div>

        <div className="sup-toolbar-sort">
          <select
            className="sup-toolbar-sort-select"
            value={supplierSortKey}
            onChange={(e) => setSupplierSortKey(e.target.value)}
            aria-label="დალაგება"
          >
            {SUPPLIER_SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="sup-toolbar-actions">
          <button
            type="button"
            className="sup-toolbar-action"
            disabled={filteredSuppliers.length === 0}
            onClick={handleDownloadSuppliersExcel}
            title="ცხრილის Excel-ად ჩამოტვირთვა (ძებნა თუ ცარიელია — ყველა)"
          >
            <DownloadIcon />
            <span>Excel</span>
          </button>
          <button
            type="button"
            className="sup-toolbar-action"
            disabled={!hasLocalPayments}
            onClick={handleDownloadCsv}
            title="ბრაუზერში ჩაწერილი გადახდების CSV-ად ჩამოტვირთვა — manual_payments.csv-ში ჩასასმელად"
          >
            <DownloadIcon />
            <span>CSV</span>
          </button>
        </div>
      </div>

      {periodCaveat ? (
        <div className="trust-banner-sub trust-banner-sub--warn">{periodCaveat}</div>
      ) : null}

      {selectedOne ? (
        <div className={`pay-card ${recordedFlash ? 'pay-card--flash' : ''}`} role="region" aria-label="გადახდის ჩაწერა">
          <div className="pay-card-glow" aria-hidden="true" />
          <div className="pay-card-head">
            <span className="pay-card-tag">
              <span className="pay-card-tag-dot" aria-hidden="true" />
              სელექტირებული მომწოდებელი
            </span>
            <span className="pay-card-name">{selectedOne['ორგანიზაცია']}</span>
          </div>

          <div className="pay-card-stats">
            <div className="pay-card-stat">
              <span className="pay-card-stat-label">ვალი</span>
              <span className={`pay-card-stat-value ${selectedDisplay.debt > 0 ? 'is-debt' : ''}`}>
                {formatNumber(selectedDisplay.debt)}
              </span>
            </div>
            <div className="pay-card-stat">
              <span className="pay-card-stat-label">სულ გადახდილი</span>
              <span className="pay-card-stat-value is-paid">{formatNumber(selectedDisplay.paid)}</span>
            </div>
            <div className="pay-card-stat">
              <span className="pay-card-stat-label">ზედნადები</span>
              <span className="pay-card-stat-value">{selectedOne.waybills_count ?? 0}</span>
            </div>
          </div>

          <div className="pay-card-form">
            <div className="pay-card-input-wrap">
              <input
                type="text"
                inputMode="decimal"
                className="pay-card-input"
                placeholder="0"
                value={payAmount}
                onChange={(e) => setPayAmount(e.target.value)}
                autoComplete="off"
                aria-label="გადახდის თანხა"
              />
              <span className="pay-card-currency" aria-hidden="true">₾</span>
              {payAmount.trim() ? (
                <button
                  type="button"
                  className="pay-card-input-clear"
                  onClick={() => setPayAmount('')}
                  aria-label="თანხის გასუფთავება"
                >
                  ✕
                </button>
              ) : null}
            </div>

            <button
              type="button"
              className="pay-card-record"
              disabled={!canRecord}
              onClick={handleRecordPayment}
            >
              <span className="pay-card-record-glyph" aria-hidden="true">✓</span>
              <span>ჩაწერა{payVal > 0 ? ` · ${formatNumber(payVal)}` : ''}</span>
            </button>

            {hasLocalPayments ? (
              <button
                type="button"
                className="pay-card-clear"
                onClick={handleClearLocal}
                title="ბრაუზერში ჩაწერილი ყველა გადახდის წაშლა"
              >
                ბრაუზერის გასუფთავება
              </button>
            ) : null}
          </div>

          <div className="pay-card-hints">
            <span className="pay-card-hint">
              <span className="pay-card-hint-bullet" />
              ჩაიწერება ბრაუზერში · ემატება „სულ გადახდილს" · იკლებს „ვალს"
            </span>
            <span className="pay-card-hint">
              <span className="pay-card-hint-bullet" />
              მუდმივად: <strong>CSV</strong> ჩამოტვირთვა და ჩაამატე{' '}
              <code>manual_payments.csv</code>-ში
            </span>
          </div>
        </div>
      ) : null}

      {payVal > 0 && realSuppliers.length > 1 && nameNeedle ? (
        <div className="sup-multi-warn" role="status">
          <span className="sup-multi-warn-icon" aria-hidden="true">!</span>
          <span>
            <strong>{realSuppliers.length} მომწოდებელი ჩანს ძებნაში.</strong>{' '}
            დააზუსტე სახელი, რომ ცხრილში ერთი ხაზი დარჩეს.
          </span>
        </div>
      ) : null}

      <div className="table-wrapper sup-table-wrapper">
        <table className="sup-table">
          <thead>
            <tr>
              <th className="sup-th sup-th-num">#</th>
              <th className="sup-th">ორგანიზაცია</th>
              <th className="sup-th sup-th-num">რაოდ.</th>
              <th className="sup-th sup-th-num" title="RS-ის რეალური ბრუნვა (ნომინალი მინუს დაბრუნებები)">ბრუნვა</th>
              <th className="sup-th sup-th-num" title="ბანკით დადასტურებული გადახდა">ბანკი</th>
              {showCashColumn && (
                <th className="sup-th sup-th-num" title="manual_payments.csv + ბრაუზერში ჩაწერილი">ნაღდი</th>
              )}
              <th className="sup-th sup-th-num">სულ გადახდ.</th>
              <th className="sup-th sup-th-num">ვალი</th>
            </tr>
          </thead>
          <tbody>
            {realSuppliers.map((sup, idx) => {
              const d = getDisplay(sup);
              const isSelected = selectedOne && sup === selectedOne;
              const hasDebt = d.debt > 0;
              const returned = Number(sup.total_returned) || 0;
              return (
                <tr
                  key={`${d.tid || 'x'}-${idx}`}
                  className={`sup-row ${isSelected ? 'is-selected' : ''} ${hasDebt ? 'has-debt' : ''}`}
                  onClick={() => onSupplierClick(sup)}
                  title="კლიკი — დეტალები"
                >
                  <td className="sup-td-num sup-td-idx">
                    <span
                      className={`sup-row-dot sup-row-dot--${d.paymentScope}`}
                      title={`${scopeLabel(d.paymentScope)}${d.paymentScopeNote ? ` · ${d.paymentScopeNote}` : ''}`}
                      aria-hidden="true"
                    />
                    {idx + 1}
                  </td>
                  <td className="sup-td-org">
                    <span
                      className="sup-org-avatar"
                      aria-hidden="true"
                      style={{ background: orgGradient(sup['ორგანიზაცია']) }}
                    >
                      {orgInitial(sup['ორგანიზაცია'])}
                    </span>
                    <span className="sup-org-name" title={sup['ორგანიზაცია']}>
                      {stripTaxIdPrefix(sup['ორგანიზაცია']) || sup['ორგანიზაცია']}
                    </span>
                    <button
                      type="button"
                      className="sup-archive-btn"
                      title="არქივში გადატანა"
                      disabled={pendingArchiveTid === d.tid}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleToggleArchive(sup, true);
                      }}
                    >
                      📥
                    </button>
                  </td>
                  <td className="sup-td-num">{sup.waybills_count}</td>
                  <td
                    className="sup-td-num sup-td-emph sup-td-turnover"
                    title={returned !== 0
                      ? `ნომინ. ${formatNumber(sup.total_nominal ?? 0)} · დაბრუნ. ${formatNumber(returned)}`
                      : undefined}
                  >
                    {formatNumber(sup.total_effective)}
                    {returned !== 0 ? (
                      <span className="sup-num-return-pill" aria-label="დაბრუნებული">
                        {formatNumber(returned)}
                      </span>
                    ) : null}
                  </td>
                  <td className="sup-td-num sup-num-bank">{formatNumber(d.strictBankPaid ?? 0)}</td>
                  {showCashColumn && (
                    <td className="sup-td-num sup-num-cash">{formatNumber(d.manualTotal ?? 0)}</td>
                  )}
                  <td className="sup-td-num sup-num-total">{formatNumber(d.paid)}</td>
                  <td className={`sup-td-num sup-td-debt ${hasDebt ? 'is-on' : ''}`}>
                    {formatNumber(d.debt)}
                  </td>
                </tr>
              );
            })}
            {realSuppliers.length === 0 ? (
              <tr>
                <td colSpan={tableColumnCount} className="sup-empty">
                  {periodMeta.applied ? 'არჩეულ პერიოდში მონაცემები არ მოიძებნა' : 'მონაცემები არ მოიძებნა'}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {archiveError ? (
        <div className="trust-banner-sub trust-banner-sub--warn" style={{ marginTop: 8 }}>
          {archiveError}
        </div>
      ) : null}

      {archivedSuppliers.length > 0 ? (
        <CollapsibleSection
          title={`📦 არქივი (${archivedSuppliers.length})`}
          subtitle="დაარქივებული ფირმები — მთავარ ცხრილში არ ჩანან, მაგრამ თანხები იჯამება ჩვეულებრივ. დაბრუნებისთვის — ↩"
          defaultOpen={false}
        >
          <div className="non-rs-list">
            {archivedSuppliers.map((sup, idx) => {
              const d = getDisplay(sup);
              const taxId = extractTaxId(sup['ორგანიზაცია']) || '—';
              return (
                <div key={`arch-${idx}`} className="non-rs-row">
                  <span className="non-rs-row-id">{taxId}</span>
                  <span className="non-rs-row-name">{stripTaxIdPrefix(sup['ორგანიზაცია']) || sup['ორგანიზაცია']}</span>
                  <span className="non-rs-row-amount">{formatNumber(d.debt)}</span>
                  <button
                    type="button"
                    className="sup-archive-btn"
                    title="არქივიდან დაბრუნება"
                    disabled={pendingArchiveTid === taxId}
                    onClick={() => handleToggleArchive(sup, false)}
                  >
                    ↩
                  </button>
                </div>
              );
            })}
          </div>
        </CollapsibleSection>
      ) : null}

      {nonRsRows.length > 0 ? (
        <CollapsibleSection
          title="📌 RS-ის გარეშე გადახდები"
          subtitle={`${nonRsRows.length} ჩანაწერი · ბანკით ${formatNumber(nonRsTotalBank)} — POS ტერმინალი ან merchant ID, რომელიც RS-ის ზედნადებებში არ იძებნება`}
          defaultOpen={false}
        >
          <div className="non-rs-list">
            {nonRsRows.map((sup, idx) => {
              const d = getDisplay(sup);
              const taxId = extractTaxId(sup['ორგანიზაცია']) || '—';
              return (
                <div key={`nonrs-${idx}`} className="non-rs-row">
                  <span className="non-rs-row-id">{taxId}</span>
                  <span className="non-rs-row-name">{stripTaxIdPrefix(sup['ორგანიზაცია']) || sup['ორგანიზაცია']}</span>
                  <span className="non-rs-row-amount sup-num-bank">{formatNumber(d.strictBankPaid ?? 0)}</span>
                </div>
              );
            })}
          </div>
        </CollapsibleSection>
      ) : null}

      <CollapsibleSection
        title="🎯 მომწოდებლების კონცენტრაცია"
        subtitle="HHI Index · Top-N წილი · მოლაპარაკების კანდიდატები"
        defaultOpen={false}
      >
        <SupplierConcentrationWidget payload={supplierConcentration} />
      </CollapsibleSection>
    </>
  );
}

function DownloadIcon() {
  return (
    <svg className="sup-toolbar-action-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}
