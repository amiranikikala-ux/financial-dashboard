import { useState, useEffect, useCallback, useMemo } from 'react';
import * as XLSX from 'xlsx';
import './index.css';
import Analytics from './Analytics.jsx';
import { STORAGE_KEY, extractTaxId, mergeSupplier } from './financeMerge.js';

/** TBC ხარჯები — tbc_expense_categories.json რიგით */
const TBC_TAXONOMY_ORDER = [
  'bank_fees_software_service',
  'transfer_commission_fee',
  'transit_ucc_communal',
  'utility_telecom_bank_commission',
  'transit_magti_mobile',
  'pos_terminal_service_fee',
  'incoming_packages_fee',
  'incasso_cash_handling',
  'treasury_budget_commission',
  'bank_account_package_fee',
  'card_retail_own_chain',
  'card_mcc_groceries_5411',
  'card_mcc_misc_retail_5943',
  'card_mcc_building_supplies_5039',
  'salary_payments',
];

/** არამიბმული: იგივე id-ები რაც TBC ბლოკში + მხოლოდ არამიბმულის დამატებითი (generate_dashboard_data) */
const BANK_UNMATCHED_EXTRA_ORDER = [
  'bank_fees_software_service',
  'cashback_foodmart',
  'rent_related',
  'tax_and_budget',
  'loan_and_finance',
  'utilities_related',
  'rs_budget_payments',
  'cash_withdrawal',
  'card_purchase_expense',
  'card_network_settlement',
  'bank_fees',
  'other_unclassified',
];

/** ძველი data.json / ხელით approve — იგივე რანჟირი ახალ id-ებთან */
const BANK_TAXONOMY_LEGACY_IDS = [
  'utility_transit_ucc',
  'utility_transit_magti',
  'pos_and_acquiring_fee',
  'salary_related',
];

const BANK_TAXONOMY_ORDER = [
  ...TBC_TAXONOMY_ORDER,
  ...BANK_UNMATCHED_EXTRA_ORDER,
  ...BANK_TAXONOMY_LEGACY_IDS,
];

function previewSnippet(text, maxLen = 96) {
  const t = String(text || '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!t) return '—';
  return t.length > maxLen ? `${t.slice(0, maxLen)}…` : t;
}

function App() {
  const [data, setData] = useState({ suppliers: [], waybills: [], meta: {} });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('suppliers'); // suppliers | waybills | analytics | cashflow
  const [showPosDailyTable, setShowPosDailyTable] = useState(false);
  const [showTbcExpenseDetailPanel, setShowTbcExpenseDetailPanel] = useState(true);
  const [posDateFrom, setPosDateFrom] = useState('');
  const [posDateTo, setPosDateTo] = useState('');
  const [showDownloads, setShowDownloads] = useState(false);
  const [searchName, setSearchName] = useState('');
  const [payAmount, setPayAmount] = useState('');
  const [localPayments, setLocalPayments] = useState({});

  useEffect(() => {
    fetch(`/data.json?v=${Date.now()}`, { cache: 'no-store' })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`data.json: HTTP ${res.status} — გაუშვი პროექტის ფოლდერში: python generate_dashboard_data.py`);
        }
        return res.json();
      })
      .then((json) => {
        setData({
          suppliers: [],
          waybills: [],
          meta: null,
          ...json,
        });
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load data:', err);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') setLocalPayments(parsed);
      }
    } catch (_) {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (loading) return;
    const raw = data.pos_terminal_income?.daily_summary;
    if (!Array.isArray(raw) || !raw.length) return;
    const days = raw.map((r) => r.day).filter(Boolean).sort();
    if (!days.length) return;
    setPosDateFrom((f) => f || days[0]);
    setPosDateTo((t) => t || days[days.length - 1]);
  }, [loading, data.pos_terminal_income]);

  const posDailySorted = useMemo(() => {
    const raw = data.pos_terminal_income?.daily_summary;
    const rows = Array.isArray(raw) ? raw : [];
    return [...rows].sort((a, b) => String(a.day || '').localeCompare(String(b.day || '')));
  }, [data.pos_terminal_income]);

  const posDailyFiltered = useMemo(() => {
    if (!posDailySorted.length) return [];
    const d0 = posDailySorted[0]?.day;
    const d1 = posDailySorted[posDailySorted.length - 1]?.day;
    const from = posDateFrom || d0;
    const to = posDateTo || d1;
    if (!from || !to) return posDailySorted;
    const lo = from <= to ? from : to;
    const hi = from <= to ? to : from;
    return posDailySorted.filter((r) => {
      const d = r.day;
      return d && d >= lo && d <= hi;
    });
  }, [posDailySorted, posDateFrom, posDateTo]);

  const posRangeTotals = useMemo(() => {
    let tbc = 0;
    let bog = 0;
    let tot = 0;
    for (const r of posDailyFiltered) {
      tbc += Number(r.tbc_total_ge) || 0;
      bog += Number(r.bog_total_ge) || 0;
      tot += Number(r.total_ge) || 0;
    }
    return { tbc, bog, total: tot, days: posDailyFiltered.length };
  }, [posDailyFiltered]);

  const persistLocalPayments = useCallback((next) => {
    setLocalPayments(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch (_) {
      /* ignore */
    }
  }, []);

  const formatNumber = (num) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'GEL' }).format(
      num || 0
    );
  };

  const parseMoney = (raw) => {
    const n = parseFloat(String(raw || '').replace(/\s/g, '').replace(',', '.'));
    return Number.isNaN(n) ? 0 : Math.max(0, n);
  };

  const getDisplay = (sup) => {
    const m = mergeSupplier(sup, localPayments);
    return {
      tid: extractTaxId(sup['ორგანიზაცია']),
      extra: m.extra,
      paid: m.paid,
      debt: m.debt,
      tp0: m.paidBase,
      manualTotal: m.manualTotal,
    };
  };

  const nameNeedle = searchName.trim().toLowerCase();
  const filteredSuppliers = (data.suppliers || []).filter((s) => {
    const org = String(s['ორგანიზაცია'] || '');
    if (nameNeedle && !org.toLowerCase().includes(nameNeedle)) return false;
    return true;
  });

  const payVal = parseMoney(payAmount);
  const canRecord =
    activeTab === 'suppliers' &&
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

  const handleDownloadSuppliersExcel = () => {
    if (!filteredSuppliers.length) return;
    const rows = filteredSuppliers.map((sup) => {
      const d = getDisplay(sup);
      return {
        ორგანიზაცია: sup['ორგანიზაცია'],
        რაოდენობა: sup.waybills_count,
        ნომინალური: Number(sup.total_nominal) || 0,
        'რეალური ჯამი': Number(sup.total_effective) || 0,
        'ნაღდით გადახდა': d.manualTotal ?? 0,
        'სულ გადახდილი': d.paid,
        დავალიანება: d.debt,
      };
    });
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

  const handleDownloadBankExpensesExcel = () => {
    const rows = expenseCategories.map((c) => ({
      კატეგორია: c.label_ka || c.id,
      ბუღალტრული_როლი:
        c.accounting_role === 'state_treasury' ? 'სახელმწიფო ხაზინა' : 'საოპერაციო ხარჯი',
      ხაზები: c.line_count || 0,
      ჯამი: Number(c.total_ge) || 0,
    }));
    if (!rows.length) return;
    const ws = XLSX.utils.json_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'TBC ხარჯები');
    const stamp = new Date().toISOString().slice(0, 10);
    XLSX.writeFile(wb, `TBC_ხარჯები_შეჯამება_${stamp}.xlsx`);
  };

  const filteredWaybills = (data.waybills || []).filter((w) => {
    if (!nameNeedle) return true;
    return (
      w.supplier?.toLowerCase().includes(nameNeedle) ||
      String(w.waybill_number || '')
        .toLowerCase()
        .includes(nameNeedle)
    );
  });

  const tbcCardIncome = data.tbc_card_income || {};
  const posTerminalIncome = data.pos_terminal_income || {};
  const tbcExpenses = data.tbc_expenses || { categories: [] };
  const tbcSamurneo = data.tbc_samurneo || {};
  const taxFlow = data.tax_flow || {};
  const tbcFoodmartCashback = data.tbc_foodmart_cashback || {};
  const unmatchedAnalysis = data.bank_unmatched_analysis || { categories: [] };
  const expenseCategories = Array.isArray(tbcExpenses.categories) ? tbcExpenses.categories : [];
  const unmatchedCategories = Array.isArray(unmatchedAnalysis.categories) ? unmatchedAnalysis.categories : [];
  const salaryCategory = expenseCategories.find((c) => c?.id === 'salary_payments') || null;
  const salaryTotal = Number(salaryCategory?.total_ge) || 0;
  const posTotal = Number(posTerminalIncome.total_ge) || 0;
  const posTbc = Number(posTerminalIncome.tbc_total_ge) || 0;
  const posBog = Number(posTerminalIncome.bog_total_ge) || 0;
  const downloadableFiles = Array.isArray(data.download_files) ? data.download_files : [];
  const downloadableZip = String(data.download_zip_file || '');
  const grandTbcExpenseAll = Number(tbcExpenses.grand_total_ge) || 0;
  const treasuryTbcExpenseCat = Number(tbcExpenses.grand_total_state_treasury_ge) || 0;
  const operatingExplicit = tbcExpenses.grand_total_operating_expense_ge;
  const totalExpenses =
    operatingExplicit !== undefined && operatingExplicit !== null
      ? Number(operatingExplicit) || 0
      : Math.max(0, grandTbcExpenseAll - treasuryTbcExpenseCat);
  const netCashflow = posTotal - totalExpenses;
  const incomeMonthly =
    Array.isArray(posTerminalIncome.monthly_summary) && posTerminalIncome.monthly_summary.length > 0
      ? posTerminalIncome.monthly_summary
      : Array.isArray(tbcCardIncome.monthly_summary)
        ? tbcCardIncome.monthly_summary
        : [];
  const expenseMonthly = Array.isArray(tbcExpenses.monthly_summary) ? tbcExpenses.monthly_summary : [];
  const salaryBreakdown = Array.isArray(tbcExpenses.salary_breakdown) ? tbcExpenses.salary_breakdown : [];
  const unmatchedTotal = Number(unmatchedAnalysis.total_ge) || 0;
  const unmatchedUncategorized = Number(unmatchedAnalysis.uncategorized_total_ge) || 0;
  const unmatchedDynamic = Number(unmatchedAnalysis.dynamic_promoted_total_ge) || 0;
  const unmatchedTop = Array.isArray(unmatchedAnalysis.top_unclassified_signatures)
    ? unmatchedAnalysis.top_unclassified_signatures
    : [];
  const confidenceTotals = unmatchedAnalysis.confidence_totals || {};
  const confHigh = Number(confidenceTotals.high) || 0;
  const confMedium = Number(confidenceTotals.medium) || 0;
  const confLow = Number(confidenceTotals.low) || 0;
  const manualApproved = Number(unmatchedAnalysis.manual_override_approved_lines) || 0;
  const manualRejected = Number(unmatchedAnalysis.manual_override_rejected_lines) || 0;
  const samExpense = Number(tbcSamurneo.expense_total_ge) || 0;
  const samReturn = Number(tbcSamurneo.return_total_ge) || 0;
  const samNet = Number(tbcSamurneo.net_ge) || 0;
  const taxOut = Number(taxFlow.out_total_ge) || 0;
  const taxIn = Number(taxFlow.in_total_ge) || 0;
  const taxNet = Number(taxFlow.net_ge) || 0;
  const foodmartCashbackTotal = Number(tbcFoodmartCashback.total_ge) || 0;
  const foodmartCashbackLines = Number(tbcFoodmartCashback.line_count) || 0;
  const unmatchedManualSplitIds = [
    'transit_ucc_communal',
    'transit_magti_mobile',
    'utility_transit_ucc',
    'utility_transit_magti',
    'bank_fees_software_service',
  ];
  const unmatchedManualSplit = unmatchedCategories.filter((c) => unmatchedManualSplitIds.includes(String(c?.id || '')));
  const unmatchedManualSplitTotal = unmatchedManualSplit.reduce((acc, c) => acc + (Number(c?.total_ge) || 0), 0);

  const bankTaxonomyCategories = useMemo(() => {
    const byId = Object.fromEntries(
      unmatchedCategories.map((c) => [String(c?.id || ''), c]),
    );
    const ordered = BANK_TAXONOMY_ORDER.map((id) => byId[id]).filter(Boolean);
    const seen = new Set(ordered.map((c) => String(c.id)));
    const rest = unmatchedCategories
      .filter((c) => c && !seen.has(String(c.id)))
      .sort((a, b) => String(a.id).localeCompare(String(b.id)));
    return [...ordered, ...rest];
  }, [unmatchedCategories]);

  const tbcTaxonomyCategories = useMemo(() => {
    const byId = Object.fromEntries(
      expenseCategories.map((c) => [String(c?.id || ''), c]),
    );
    const ordered = TBC_TAXONOMY_ORDER.map((id) => byId[id]).filter(Boolean);
    const seen = new Set(ordered.map((c) => String(c.id)));
    const rest = expenseCategories
      .filter((c) => c && !seen.has(String(c.id)))
      .sort((a, b) => String(a.id).localeCompare(String(b.id)));
    return [...ordered, ...rest];
  }, [expenseCategories]);
  const confidenceBadgeClass = (raw) => {
    const v = String(raw || 'low').toLowerCase();
    if (v === 'high') return 'badge conf-high';
    if (v === 'medium') return 'badge conf-medium';
    return 'badge conf-low';
  };

  return (
    <div className="dashboard-container">
      {loading ? (
        <div className="loading">იტვირთება მონაცემები...</div>
      ) : (
        <>
      <header>
        <div>
          <h1>RS Dashboard</h1>
          <div className="subtitle">ფინანსური ანალიზი და ზედნადებების კონტროლი</div>
          {data.meta != null && (
            <div className="subtitle meta-hint">
              ნაღდით გადახდა (manual_payments.csv):{' '}
              {formatNumber(data.meta.manual_payments_total)}{' '}
              — {data.meta.manual_payments_rows_with_amount || 0} კომპანიაზე თანხით &gt; 0
              {Number(data.meta.suppliers_only_journal_or_bank) > 0 && (
                <>
                  {' '}
                  | RS-ის გარეშე სიაში: {data.meta.suppliers_only_journal_or_bank}
                </>
              )}
            </div>
          )}
        </div>
        <div className="tabs">
          <button
            type="button"
            className={`tab-btn ${activeTab === 'suppliers' ? 'active' : ''}`}
            onClick={() => setActiveTab('suppliers')}
          >
            🏢 მომწოდებლები
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'waybills' ? 'active' : ''}`}
            onClick={() => setActiveTab('waybills')}
          >
            📄 ზედნადებები
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'analytics' ? 'active' : ''}`}
            onClick={() => setActiveTab('analytics')}
          >
            📊 ანალიტიკა
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'cashflow' ? 'active' : ''}`}
            onClick={() => setActiveTab('cashflow')}
          >
            💳 ბანკის ანალიზი
          </button>
        </div>
      </header>

      <div className="panel">
        {activeTab !== 'analytics' && activeTab !== 'cashflow' && (
        <div className="controls controls-filters">
          <label className="filter-field">
            <span className="filter-label">
              {activeTab === 'suppliers' ? 'კომპანია' : 'ძებნა'}
            </span>
            <input
              type="text"
              className="search-input search-input-compact"
              placeholder={
                activeTab === 'suppliers'
                  ? 'სახელი, ნაწილობრივი ტექსტი…'
                  : 'კომპანია ან ზედნადები…'
              }
              value={searchName}
              onChange={(e) => setSearchName(e.target.value)}
              autoComplete="off"
            />
          </label>
          {activeTab === 'suppliers' && (
            <>
              <label className="filter-field">
                <span className="filter-label">თანხა (₾)</span>
                <span className="filter-hint">
                  იმატებს „სულ გადახდილს“, იკლებს „დავალიანებას“
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
            </>
          )}
        </div>
        )}

        {activeTab === 'analytics' ? (
          <Analytics suppliers={data.suppliers} localPayments={localPayments} />
        ) : activeTab === 'cashflow' ? (
          <div className="cashflow-page">
            <div className="kpi-grid">
              <div
                className="kpi-card kpi-card--accent"
                role="button"
                tabIndex={0}
                onClick={() => setShowPosDailyTable((v) => !v)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setShowPosDailyTable((v) => !v);
                  }
                }}
                title="დააჭირე POS დღიური — თარიღის დიაპაზონით"
                style={{ cursor: 'pointer' }}
              >
                <div className="kpi-label">POS ტერმინალი (TBC + BOG)</div>
                <div className="kpi-value amount-positive">{formatNumber(posTotal)}</div>
                <div className="kpi-sub">TBC: <span className="amount-positive">{formatNumber(posTbc)}</span></div>
                <div className="kpi-sub">BOG: <span className="amount-positive">{formatNumber(posBog)}</span></div>
                <div className="kpi-sub">
                  {showPosDailyTable ? '▼ დახურვა' : '▶ POS დღიური (თარიღი: დან — მდე)'}
                </div>
              </div>
              <div
                className="kpi-card kpi-card--warn"
                role="button"
                tabIndex={0}
                onClick={() => setShowTbcExpenseDetailPanel((v) => !v)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setShowTbcExpenseDetailPanel((v) => !v);
                  }
                }}
                title={
                  tbcExpenses.ledger_note_ka ||
                  'დააჭირე — ცხრილი და დეტალური კატეგორიები'
                }
                style={{ cursor: 'pointer' }}
              >
                <div className="kpi-label">TBC — საოპერაციო ხარჯი (კატეგორიები)</div>
                <div className="kpi-value amount-negative">{formatNumber(totalExpenses)}</div>
                <div className="kpi-sub">{data.meta?.tbc_expenses_total_lines || 0} ხაზი</div>
                <div className="kpi-sub">
                  ხაზინა/საბიუჯეტო (TBC კატეგორიები):{' '}
                  <span className="amount-neutral">{formatNumber(treasuryTbcExpenseCat)}</span>
                </div>
                <div className="kpi-sub">
                  {showTbcExpenseDetailPanel
                    ? '▼ დახურვა'
                    : '▶ TBC ხარჯები — ცხრილი და დეტალური კატეგორიები'}
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">ხელფასები</div>
                <div className="kpi-value amount-negative">{formatNumber(salaryTotal)}</div>
                <div className="kpi-sub">{salaryCategory?.line_count || 0} ხაზი</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">სუფთა სხვაობა (შემოსავალი - ხარჯი)</div>
                <div className={`kpi-value ${netCashflow >= 0 ? 'amount-positive' : 'amount-negative'}`}>
                  {formatNumber(netCashflow)}
                </div>
                <div className="kpi-sub">
                  POS ტერმინალი (TBC+BOG) − საოპერაციო ხარჯი (ხაზინის TBC კატეგორია ცალკეა)
                </div>
              </div>
              <div
                className="kpi-card"
                title={unmatchedAnalysis.ledger_note_ka || ''}
              >
                <div className="kpi-label">არამიბმული ბანკი (სულ)</div>
                <div className="kpi-value amount-negative">{formatNumber(unmatchedTotal)}</div>
                <div className="kpi-sub">{unmatchedAnalysis.line_count || 0} ხაზი</div>
                <div className="kpi-sub">
                  ბუღალტრულად ბევრი აქ — ხარჯებია, მაგრამ RS მომწოდებელთან ვერ მიბმულია (ვრცლად — tooltip)
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">არამიბმული — „სხვა“ (გასაწმენდი)</div>
                <div className="kpi-value amount-negative">{formatNumber(unmatchedUncategorized)}</div>
                <div className="kpi-sub">რაც ნაკლებია, მით უკეთესი</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">არამიბმული — ავტო ჯგუფებით დაჭერილი</div>
                <div className="kpi-value amount-neutral">{formatNumber(unmatchedDynamic)}</div>
                <div className="kpi-sub">განმეორებადი IBAN/კონტრაგენტები</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">სანდოობა HIGH</div>
                <div className="kpi-value amount-positive">{formatNumber(confHigh)}</div>
                <div className="kpi-sub">ძლიერი ტექსტური/IBAN დამთხვევა</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">სანდოობა MEDIUM</div>
                <div className="kpi-value amount-neutral">{formatNumber(confMedium)}</div>
                <div className="kpi-sub">ნაწილობრივ სპეციფიკური</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">სანდოობა LOW</div>
                <div className="kpi-value amount-negative">{formatNumber(confLow)}</div>
                <div className="kpi-sub">საჭიროებს ხელით გადამოწმებას</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">ხელით override</div>
                <div className="kpi-value amount-neutral">{manualApproved + manualRejected}</div>
                <div className="kpi-sub">approve: {manualApproved} | reject: {manualRejected}</div>
              </div>
              <div className="kpi-card" title={tbcSamurneo.accounting_note_ka || ''}>
                <div className="kpi-label">
                  {tbcSamurneo.label_ka || 'საქმიანობისთვის აუცილებელი ხარჯი (სამეურნეო)'}
                </div>
                <div className="kpi-sub">ბუღალტრულად: კომპანიის საქმიანობისთვის აუცილებელი ხარჯის მოძრაობა (ბანკის ფილტრი)</div>
                <div className="kpi-sub">შემოტანა: <span className="amount-positive">{formatNumber(samReturn)}</span></div>
                <div className="kpi-sub">გატანა: <span className="amount-negative">{formatNumber(samExpense)}</span></div>
                <div className="kpi-sub">
                  მეტობა: <span className={samNet >= 0 ? 'amount-positive' : 'amount-negative'}>{formatNumber(samNet)}</span>
                </div>
              </div>
              <div className="kpi-card" title={taxFlow.ledger_note_ka || ''}>
                <div className="kpi-label">
                  {taxFlow.label_ka || 'საგადასახადო / ბიუჯეტი / ხაზინა'}
                </div>
                <div className="kpi-sub">
                  RS / ბიუჯეტი / სახელმწიფო ხაზინა — ერთი ჯგუფის მოძრაობა (ვრცლად tooltip)
                </div>
                <div className="kpi-sub">ჩარიცხული: <span className="amount-positive">{formatNumber(taxIn)}</span></div>
                <div className="kpi-sub">გადარიცხული: <span className="amount-negative">{formatNumber(taxOut)}</span></div>
                <div className="kpi-sub">
                  მეტობა: <span className={taxNet >= 0 ? 'amount-positive' : 'amount-negative'}>{formatNumber(taxNet)}</span>
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">ფუდმარტი ქეშბექი</div>
                <div className="kpi-value kpi-value--foodmart amount-positive">{formatNumber(foodmartCashbackTotal)}</div>
                <div className="kpi-sub">{foodmartCashbackLines} ხაზი</div>
              </div>
            </div>

            {showPosDailyTable && (
              <div className="pos-daily-panel">
                <div className="pos-date-range">
                  <span className="pos-date-range-label">POS დღიური — აირჩიე პერიოდი</span>
                  <label className="pos-date-field">
                    <span>დან</span>
                    <input
                      type="date"
                      value={posDateFrom}
                      onChange={(e) => setPosDateFrom(e.target.value)}
                      min={posDailySorted[0]?.day}
                      max={posDailySorted[posDailySorted.length - 1]?.day}
                    />
                  </label>
                  <label className="pos-date-field">
                    <span>მდე</span>
                    <input
                      type="date"
                      value={posDateTo}
                      onChange={(e) => setPosDateTo(e.target.value)}
                      min={posDailySorted[0]?.day}
                      max={posDailySorted[posDailySorted.length - 1]?.day}
                    />
                  </label>
                  <button
                    type="button"
                    className="btn-pos-range-full"
                    onClick={() => {
                      if (!posDailySorted.length) return;
                      const days = posDailySorted.map((r) => r.day).filter(Boolean);
                      if (!days.length) return;
                      setPosDateFrom(days[0]);
                      setPosDateTo(days[days.length - 1]);
                    }}
                  >
                    მთელი პერიოდი
                  </button>
                </div>
                <div className="pos-range-totals">
                  <span>
                    არჩეულ პერიოდში: <strong>{posRangeTotals.days}</strong> დღე
                  </span>
                  <span>
                    TBC: <span className="amount-positive">{formatNumber(posRangeTotals.tbc)}</span>
                  </span>
                  <span>
                    BOG: <span className="amount-positive">{formatNumber(posRangeTotals.bog)}</span>
                  </span>
                  <span>
                    ჯამი: <span className="amount-positive">{formatNumber(posRangeTotals.total)}</span>
                  </span>
                </div>
                <div className="table-wrapper cashflow-table">
                  <table>
                    <thead>
                      <tr>
                        <th>დღე</th>
                        <th>TBC POS</th>
                        <th>BOG POS</th>
                        <th>ჯამი POS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {posDailyFiltered.map((r) => (
                        <tr key={`pos-filtered-${r.day}`}>
                          <td>{r.day}</td>
                          <td className="amount-positive">{formatNumber(r.tbc_total_ge)}</td>
                          <td className="amount-positive">{formatNumber(r.bog_total_ge)}</td>
                          <td className="amount-positive">{formatNumber(r.total_ge)}</td>
                        </tr>
                      ))}
                      {posDailyFiltered.length === 0 && (
                        <tr>
                          <td colSpan="4" style={{ textAlign: 'center' }}>
                            ამ პერიოდში ხაზები არაა — შეცვალე „დან / მდე“ ან დააჭირე „მთელი პერიოდი“
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {showTbcExpenseDetailPanel && (
              <div className="pos-daily-panel tbc-expense-detail-panel">
                <div className="table-wrapper cashflow-table">
                  <table>
                    <thead>
                      <tr>
                        <th>კატეგორია</th>
                        <th>ხაზების რაოდენობა</th>
                        <th>ჯამი</th>
                        <th>წილი (ჯამი ყველა კატეგორია)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {expenseCategories.map((cat) => {
                        const catTotal = Number(cat.total_ge) || 0;
                        const share =
                          grandTbcExpenseAll > 0 ? (catTotal / grandTbcExpenseAll) * 100 : 0;
                        return (
                          <tr key={cat.id}>
                            <td>{cat.label_ka || cat.id}</td>
                            <td>{cat.line_count || 0}</td>
                            <td className="amount-negative">{formatNumber(catTotal)}</td>
                            <td>{share.toFixed(2)}%</td>
                          </tr>
                        );
                      })}
                      {expenseCategories.length === 0 && (
                        <tr>
                          <td colSpan="4" style={{ textAlign: 'center' }}>
                            TBC ხარჯების კატეგორიები ჯერ არ არის ჩატვირთული
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="taxonomy-section taxonomy-section--in-panel">
                  <h3 className="taxonomy-heading">TBC ხარჯები — დეტალური კატეგორიები (ეკრანზე)</h3>
                  <p className="taxonomy-lead">
                    იგივე წესები, რაც <code>tbc_expense_categories.json</code>-შია — ჯამი და ნიმუშის ხაზები.
                  </p>
                  <div className="taxonomy-grid">
                    {tbcTaxonomyCategories.map((cat) => {
                      const prev = Array.isArray(cat.rows_preview) ? cat.rows_preview : [];
                      const show = prev.slice(0, 10);
                      return (
                        <div className="taxonomy-card" key={`tbc-tax-${cat.id}`}>
                          <div className="taxonomy-card-head">
                            <span className="taxonomy-card-title">{cat.label_ka || cat.id}</span>
                            <code className="taxonomy-card-id">{cat.id}</code>
                          </div>
                          <div className="taxonomy-card-stats">
                            <span className="amount-negative">{formatNumber(cat.total_ge)}</span>
                            <span className="taxonomy-meta">{cat.line_count || 0} ხაზი</span>
                          </div>
                          <details className="taxonomy-details">
                            <summary>
                              ნიმუშის ხაზები ({show.length}
                              {prev.length > 10 ? ` / ${prev.length}` : ''})
                            </summary>
                            <div className="taxonomy-preview-list">
                              {show.length === 0 && (
                                <div className="taxonomy-preview-empty">პრევიუ არ არის data.json-ში</div>
                              )}
                              {show.map((r, idx) => (
                                <div className="taxonomy-preview-row" key={`tbc-${cat.id}-${idx}`}>
                                  <div className="taxonomy-preview-top">
                                    <span className="taxonomy-preview-date">{r.თარიღი || '—'}</span>
                                    <span className="taxonomy-preview-amt amount-negative">
                                      {formatNumber(r.თანხა)}
                                    </span>
                                  </div>
                                  <span className="taxonomy-preview-desc">
                                    {previewSnippet(r.ტექსტი_მოკლე, 120)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </details>
                        </div>
                      );
                    })}
                  </div>
                  {tbcTaxonomyCategories.length === 0 && (
                    <p className="taxonomy-empty">კატეგორიები ცარიელია ან data.json განახლებული არაა.</p>
                  )}
                </div>
              </div>
            )}

            <div className="cashflow-grid-2">
              <div className="table-wrapper cashflow-table">
                <p className="taxonomy-lead" style={{ marginBottom: '0.5rem' }}>
                  ყოველთვიური შემოსავალი = <strong>POS ტერმინალი (TBC + BOG)</strong> — იგივე ლოგიკა, რაც ზემოთ KPI და დღიური ცხრილი.
                </p>
                <table>
                  <thead>
                    <tr>
                      <th>თვე</th>
                      <th>შემოსავალი (POS TBC+BOG)</th>
                      <th>ხარჯი (TBC კატეგორიები)</th>
                      <th>სხვაობა</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incomeMonthly.map((im) => {
                      const em = expenseMonthly.find((x) => x.month === im.month);
                      const inAmt = Number(im.total_ge) || 0;
                      const exAmt = Number(em?.total_ge) || 0;
                      const delta = inAmt - exAmt;
                      return (
                        <tr key={im.month}>
                          <td>{im.month}</td>
                          <td className="amount-positive">{formatNumber(inAmt)}</td>
                          <td className="amount-negative">{formatNumber(exAmt)}</td>
                          <td className={delta >= 0 ? 'amount-positive' : 'amount-negative'}>
                            {formatNumber(delta)}
                          </td>
                        </tr>
                      );
                    })}
                    {incomeMonthly.length === 0 && (
                      <tr>
                        <td colSpan="4" style={{ textAlign: 'center' }}>
                          თვეების ჭრილი ჯერ არ არის
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="table-wrapper cashflow-table">
                <table>
                  <thead>
                    <tr>
                      <th>ხელფასის ჯგუფი</th>
                      <th>ჯამი</th>
                    </tr>
                  </thead>
                  <tbody>
                    {salaryBreakdown.map((r) => (
                      <tr key={r.name}>
                        <td>{r.name}</td>
                        <td className="amount-negative">{formatNumber(r.total_ge)}</td>
                      </tr>
                    ))}
                    {salaryBreakdown.length === 0 && (
                      <tr>
                        <td colSpan="2" style={{ textAlign: 'center' }}>
                          ხელფასის breakdown ჯერ არ არის
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="cashflow-focus-grid">
              <div className="kpi-card kpi-card--accent">
                <div className="kpi-label">ახალი დაყოფა — ფოკუსი</div>
                <div className="kpi-value amount-neutral">{formatNumber(unmatchedManualSplitTotal)}</div>
                <div className="kpi-sub">{unmatchedManualSplit.length} ქვეკატეგორია</div>
              </div>
              {unmatchedManualSplit.map((cat) => (
                <div className="kpi-card" key={`split-${cat.id}`}>
                  <div className="kpi-label">{cat.label_ka || cat.id}</div>
                  <div className="kpi-sub">
                    <span className={confidenceBadgeClass(cat.confidence)}>
                      {String(cat.confidence || 'low').toUpperCase()}
                    </span>
                  </div>
                  <div className="kpi-sub">ხაზები: {cat.line_count || 0}</div>
                  <div className="kpi-sub">
                    ჯამი:{' '}
                    <span className="amount-neutral">{formatNumber(cat.total_ge)}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="taxonomy-section">
              <h3 className="taxonomy-heading">არამიბმული ბანკი — დეტალური კატეგორიები (ეკრანზე)</h3>
              <p className="taxonomy-lead">
                RS მომწოდებელთან რომ არ მიებმება — ავტომატური წესები + ხელით override; ქვემოთ ნიმუშის ხაზები
                (BOG/TBC).
              </p>
              <div className="taxonomy-grid">
                {bankTaxonomyCategories.map((cat) => {
                  const prev = Array.isArray(cat.rows_preview) ? cat.rows_preview : [];
                  const show = prev.slice(0, 10);
                  return (
                    <div className="taxonomy-card" key={`bank-tax-${cat.id}`}>
                      <div className="taxonomy-card-head">
                        <span className="taxonomy-card-title">{cat.label_ka || cat.id}</span>
                        <code className="taxonomy-card-id">{cat.id}</code>
                      </div>
                      <div className="taxonomy-card-stats">
                        <span
                          className={
                            cat.id === 'other_unclassified' ? 'amount-negative' : 'amount-neutral'
                          }
                        >
                          {formatNumber(cat.total_ge)}
                        </span>
                        <span className="taxonomy-meta">{cat.line_count || 0} ხაზი</span>
                        <span className={confidenceBadgeClass(cat.confidence)}>
                          {String(cat.confidence || 'low').toUpperCase()}
                        </span>
                      </div>
                      <details className="taxonomy-details">
                        <summary>
                          ნიმუშის ხაზები ({show.length}
                          {prev.length > 10 ? ` / ${prev.length}` : ''})
                        </summary>
                        <div className="taxonomy-preview-list">
                          {show.length === 0 && (
                            <div className="taxonomy-preview-empty">პრევიუ არ არის</div>
                          )}
                          {show.map((r, idx) => (
                            <div className="taxonomy-preview-row" key={`bank-${cat.id}-${idx}`}>
                              <div className="taxonomy-preview-top">
                                <span className="taxonomy-preview-date">{r.თარიღი || '—'}</span>
                                {r.ბანკი ? (
                                  <span className="taxonomy-preview-bank">{r.ბანკი}</span>
                                ) : null}
                                <span className="taxonomy-preview-amt amount-negative">
                                  {formatNumber(r.თანხა)}
                                </span>
                              </div>
                              <span className="taxonomy-preview-desc">
                                {previewSnippet(
                                  r.ოპერაციის_შინაარსი || r.მიმღები_სახელი || r.მიზეზი,
                                  120,
                                )}
                              </span>
                            </div>
                          ))}
                        </div>
                      </details>
                    </div>
                  );
                })}
              </div>
              {bankTaxonomyCategories.length === 0 && (
                <p className="taxonomy-empty">არამიბმული კატეგორიები ცარიელია.</p>
              )}
            </div>

            <div className="table-wrapper cashflow-table">
              <table>
                <thead>
                  <tr>
                    <th>არამიბმული კატეგორია (ავტომატური)</th>
                    <th>სანდოობა</th>
                    <th>ხაზები</th>
                    <th>ჯამი</th>
                  </tr>
                </thead>
                <tbody>
                  {unmatchedCategories.map((cat) => (
                    <tr key={cat.id}>
                      <td>{cat.label_ka || cat.id}</td>
                      <td>
                        <span className={confidenceBadgeClass(cat.confidence)}>
                          {String(cat.confidence || 'low').toUpperCase()}
                        </span>
                      </td>
                      <td>{cat.line_count || 0}</td>
                      <td className={cat.id === 'other_unclassified' ? 'amount-negative' : 'amount-neutral'}>
                        {formatNumber(cat.total_ge)}
                      </td>
                    </tr>
                  ))}
                  {unmatchedCategories.length === 0 && (
                    <tr>
                      <td colSpan="4" style={{ textAlign: 'center' }}>
                        არამიბმული ავტომატური კატეგორიები ჯერ არ არის
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="table-wrapper cashflow-table">
              <table>
                <thead>
                  <tr>
                    <th>TOP „სხვა“ პატერნი</th>
                    <th>ხაზები</th>
                    <th>ჯამი</th>
                  </tr>
                </thead>
                <tbody>
                  {unmatchedTop.map((r, idx) => (
                    <tr key={`${r.signature}-${idx}`}>
                      <td>{r.signature}</td>
                      <td>{r.line_count || 0}</td>
                      <td className="amount-negative">{formatNumber(r.total_ge)}</td>
                    </tr>
                  ))}
                  {unmatchedTop.length === 0 && (
                    <tr>
                      <td colSpan="3" style={{ textAlign: 'center' }}>
                        TOP პატერნები ჯერ არ არის
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="cashflow-note">
              <button
                type="button"
                className="btn-download-toggle"
                onClick={() => setShowDownloads((v) => !v)}
                aria-expanded={showDownloads}
              >
                <span>ფაილების ჩამოტვირთვა</span>
                <span className="arrow">{showDownloads ? '▾' : '▸'}</span>
              </button>

              {showDownloads && (
                <div className="download-list">
                  <button type="button" className="btn-download-xlsx" onClick={handleDownloadBankExpensesExcel}>
                    TBC ხარჯები (შეჯამება)
                  </button>
                  {downloadableZip ? (
                    <a
                      className="btn-download-xlsx"
                      href={`/download/${encodeURIComponent(downloadableZip)}`}
                      download={downloadableZip}
                      style={{ textDecoration: 'none' }}
                      title={downloadableZip}
                    >
                      ყველა ერთად (ZIP)
                    </a>
                  ) : null}
                  {downloadableFiles.map((f) => (
                    <a
                      key={f}
                      className="btn-download-xlsx"
                      href={`/download/${encodeURIComponent(f)}`}
                      download={f}
                      style={{ textDecoration: 'none' }}
                      title={f}
                    >
                      {f}
                    </a>
                  ))}
                </div>
              )}
              <div className="cashflow-note-hint">
                დააჭირე, ჩამონათვალი რომ გაიშალოს
              </div>
            </div>
          </div>
        ) : (
          <>
            {activeTab === 'suppliers' ? (
              <div className="local-pay-banner local-pay-banner--short" role="status">
                ერთი კომპანია ძებნაში → თანხა → <strong>გადახდის ჩაწერა</strong>. სამუდამოდ:{' '}
                <strong>CSV ჩამოტვირთვა</strong> და ჩაამატე ფაილში, შემდეგ გენერაცია.
              </div>
            ) : null}

            {activeTab === 'suppliers' && payVal > 0 && filteredSuppliers.length > 1 && nameNeedle ? (
              <div className="filter-warning" role="status">
                <strong>რამდენიმე მომწოდებელი ჩანს.</strong> სანამ ჩაწერო, დააზუსტე სახელი, რომ ცხრილში{' '}
                <strong>ერთი</strong> ხაზი დარჩეს.
              </div>
            ) : null}

            <div className="table-wrapper">
              {activeTab === 'suppliers' ? (
                <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>ორგანიზაცია</th>
                  <th>რაოდენობა</th>
                  <th title="ყველა ხაზის „თანხის“ პირდაპირი ჯამი — გაუქმებულიც თუ ჩაწერილია თანხით. ეს არ არის ვალის ჯამი.">
                    ნომინალური
                  </th>
                  <th title="უკან დაბრუნების ხაზების თანხების ჯამი (დადებითიც ჩანს, თუ RS ასე აქვს)">
                    დაბრუნებული
                  </th>
                  <th title="ფაქტობრივი ვალდებულება RS-ის მიხედვით: გაუქმებული = 0, უკან დაბრუნება = უარყოფითი. ამიტომ ხშირად ნაკლებია ნომინალზე — ეს ნორმაა.">
                    რეალური ჯამი
                  </th>
                  <th title="manual_payments.csv + ამ ბრაუზერში ჩაწერილი გადახდები">ნაღდით გადახდა</th>
                  <th>სულ გადახდილი</th>
                  <th>დავალიანება</th>
                </tr>
              </thead>
              <tbody>
                {filteredSuppliers.map((sup, idx) => {
                  const d = getDisplay(sup);
                  return (
                    <tr key={`${d.tid || 'x'}-${idx}`}>
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
                      <td className="amount-neutral">{formatNumber(d.manualTotal ?? 0)}</td>
                      <td className="amount-positive">{formatNumber(d.paid)}</td>
                      <td className="amount-negative">{formatNumber(d.debt)}</td>
                    </tr>
                  );
                })}
                {filteredSuppliers.length === 0 && (
                  <tr>
                    <td colSpan="9" style={{ textAlign: 'center' }}>
                      მონაცემები არ მოიძებნა
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>თარიღი</th>
                  <th>ორგანიზაცია</th>
                  <th>ზედნადები</th>
                  <th>თანხა</th>
                  <th>სტატუსი</th>
                </tr>
              </thead>
              <tbody>
                {filteredWaybills.slice(0, 1000).map((wb, idx) => {
                  let badgeClass = 'badge active';
                  let badgeText = 'აქტიური';

                  if (wb.status?.includes('გაუქმებული')) {
                    badgeClass = 'badge canceled';
                    badgeText = 'გაუქმებული';
                  } else if (wb.type?.includes('დაბრუნება')) {
                    badgeClass = 'badge return';
                    badgeText = 'დაბრუნება';
                  }

                  return (
                    <tr key={idx}>
                      <td>{wb.date}</td>
                      <td>{wb.supplier}</td>
                      <td>{wb.waybill_number}</td>
                      <td
                        className={
                          wb.effective_amount < 0
                            ? 'amount-negative'
                            : wb.effective_amount === 0
                              ? 'amount-neutral'
                              : 'amount-positive'
                        }
                      >
                        {formatNumber(wb.effective_amount || wb.nominal_amount)}
                      </td>
                      <td>
                        <span className={badgeClass}>{badgeText}</span>
                      </td>
                    </tr>
                  );
                })}
                {filteredWaybills.length > 1000 && (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', color: 'var(--warning)' }}>
                      ჩაიტვირთა მხოლოდ პირველი 1000 ჩანაწერი
                    </td>
                  </tr>
                )}
                {filteredWaybills.length === 0 && (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center' }}>
                      მონაცემები არ მოიძებნა
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
              )}
            </div>
          </>
        )}
      </div>
        </>
      )}
    </div>
  );
}

export default App;
