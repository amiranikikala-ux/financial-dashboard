import { useState, useEffect, useMemo } from 'react';
import { fetchApiJson } from './lib/api.js';
import CalendarRangePicker from './components/CalendarRangePicker.jsx';
import BankRefreshModal from './components/BankRefreshModal.jsx';

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

async function loadXlsxModule() {
  const xlsxModule = await import('xlsx');
  return xlsxModule.default || xlsxModule;
}

function buildCanonicalPeriodParams(fromDate, toDate, fromTime, toTime) {
  const resolvedFromDate = fromDate || toDate;
  const resolvedToDate = toDate || fromDate;
  if (!resolvedFromDate && !resolvedToDate) return null;
  return {
    from_date: resolvedFromDate,
    to_date: resolvedToDate,
    from_time: fromTime || '00:00',
    to_time: toTime || '23:59',
  };
}

export default function Cashflow({ data, reloadKey, formatNumber, fromDate, fromTime, toDate, toTime, onDataReload }) {
  const [showPosDailyTable, setShowPosDailyTable] = useState(false);
  const [showSalaryBreakdown, setShowSalaryBreakdown] = useState(false);
  const [showUnmatchedBankDetail, setShowUnmatchedBankDetail] = useState(false);
  const [showTbcExpenseDetailPanel, setShowTbcExpenseDetailPanel] = useState(false);
  const [posDateFrom, setPosDateFrom] = useState('');
  const [posDateTo, setPosDateTo] = useState('');
  const [showDownloads, setShowDownloads] = useState(false);
  const [showBankRefreshModal, setShowBankRefreshModal] = useState(false);
  const [bankRefreshAgeLabel, setBankRefreshAgeLabel] = useState('');
  const [bankRefreshTick, setBankRefreshTick] = useState(0);
  const [cashflowTbcExpensesDetail, setCashflowTbcExpensesDetail] = useState({
    key: '',
    detail: null,
    error: '',
    loading: false,
  });

  const canonicalPeriodParams = useMemo(
    () => buildCanonicalPeriodParams(fromDate, toDate, fromTime, toTime),
    [fromDate, fromTime, toDate, toTime],
  );
  const canonicalPeriodQueryString = useMemo(() => {
    if (!canonicalPeriodParams) return '';
    const params = new URLSearchParams();
    Object.entries(canonicalPeriodParams).forEach(([key, value]) => {
      params.set(key, value);
    });
    return params.toString();
  }, [canonicalPeriodParams]);
  const [cashflowBankUnmatchedDetail, setCashflowBankUnmatchedDetail] = useState({
    key: '',
    detail: null,
    error: '',
    loading: false,
  });

  const cashflowDetailKey = canonicalPeriodQueryString
    ? `cashflow:${reloadKey}:${canonicalPeriodQueryString}`
    : `cashflow:${reloadKey}`;

  useEffect(() => {
    if (!showTbcExpenseDetailPanel) return undefined;
    if (cashflowTbcExpensesDetail.key === cashflowDetailKey) return undefined;

    let active = true;
    const controller = new AbortController();

    const params = new URLSearchParams({ tab: 'cashflow_tbc_expenses_detail' });
    if (canonicalPeriodParams) {
      Object.entries(canonicalPeriodParams).forEach(([key, value]) => {
        params.set(key, value);
      });
    }

    fetchApiJson(`/api/data?${params.toString()}`, { signal: controller.signal })
      .then((json) => {
        if (!active) return;
        setCashflowTbcExpensesDetail({
          key: cashflowDetailKey,
          detail: json.tbc_expenses || {},
          error: '',
          loading: false,
        });
      })
      .catch((err) => {
        if (!active || err.name === 'AbortError') return;
        console.error('Failed to load cashflow TBC expense detail:', err);
        setCashflowTbcExpensesDetail({
          key: cashflowDetailKey,
          detail: null,
          error: err.message || 'უცნობი შეცდომა',
          loading: false,
        });
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [canonicalPeriodParams, cashflowDetailKey, cashflowTbcExpensesDetail.key, showTbcExpenseDetailPanel]);

  useEffect(() => {
    if (!showUnmatchedBankDetail) return undefined;
    if (cashflowBankUnmatchedDetail.key === cashflowDetailKey) return undefined;

    let active = true;
    const controller = new AbortController();

    const params = new URLSearchParams({ tab: 'cashflow_bank_unmatched_detail' });
    if (canonicalPeriodParams) {
      Object.entries(canonicalPeriodParams).forEach(([key, value]) => {
        params.set(key, value);
      });
    }

    fetchApiJson(`/api/data?${params.toString()}`, { signal: controller.signal })
      .then((json) => {
        if (!active) return;
        setCashflowBankUnmatchedDetail({
          key: cashflowDetailKey,
          detail: json.bank_unmatched_analysis || {},
          error: '',
          loading: false,
        });
      })
      .catch((err) => {
        if (!active || err.name === 'AbortError') return;
        console.error('Failed to load unmatched bank detail:', err);
        setCashflowBankUnmatchedDetail({
          key: cashflowDetailKey,
          detail: null,
          error: err.message || 'უცნობი შეცდომა',
          loading: false,
        });
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [canonicalPeriodParams, cashflowBankUnmatchedDetail.key, cashflowDetailKey, showUnmatchedBankDetail]);

  useEffect(() => {
    const raw = data.pos_terminal_income?.daily_summary;
    if (!Array.isArray(raw) || !raw.length) return;
    const days = raw.map((r) => r.day).filter(Boolean).sort();
    if (!days.length) return;
    setTimeout(() => {
      setPosDateFrom((f) => f || days[0]);
      setPosDateTo((t) => t || days[days.length - 1]);
    }, 0);
  }, [data.pos_terminal_income]);

  const posDailySorted = useMemo(() => {
    const raw = data.pos_terminal_income?.daily_summary;
    const rows = Array.isArray(raw) ? raw : [];
    return [...rows].sort((a, b) => String(a.day || '').localeCompare(String(b.day || '')));
  }, [data.pos_terminal_income]);

  const posDailyAvailableDays = useMemo(
    () => posDailySorted.map((r) => r.day).filter(Boolean),
    [posDailySorted],
  );

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

  const posTerminalIncome = data.pos_terminal_income || {};
  const tbcExpenses = data.tbc_expenses || { categories: [] };
  const tbcExpensesDetail =
    cashflowTbcExpensesDetail.key === cashflowDetailKey ? (cashflowTbcExpensesDetail.detail || null) : null;
  const tbcSamurneo = data.tbc_samurneo || {};
  const taxFlow = data.tax_flow || {};
  const tbcFoodmartCashback = data.tbc_foodmart_cashback || {};
  const unmatchedAnalysis = data.bank_unmatched_analysis || { categories: [] };
  const unmatchedAnalysisDetail =
    cashflowBankUnmatchedDetail.key === cashflowDetailKey
      ? (cashflowBankUnmatchedDetail.detail || null)
      : null;
  const expenseCategories = Array.isArray(tbcExpenses.categories) ? tbcExpenses.categories : [];
  const expenseDetailCategories = Array.isArray(tbcExpensesDetail?.categories)
    ? tbcExpensesDetail.categories
    : expenseCategories;
  const unmatchedCategories = Array.isArray(unmatchedAnalysis.categories) ? unmatchedAnalysis.categories : [];
  const unmatchedDetailCategories = Array.isArray(unmatchedAnalysisDetail?.categories)
    ? unmatchedAnalysisDetail.categories
    : unmatchedCategories;
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

  const bankTaxonomyCategories = (() => {
    const byId = Object.fromEntries(
      unmatchedDetailCategories.map((c) => [String(c?.id || ''), c]),
    );
    const ordered = BANK_TAXONOMY_ORDER.map((id) => byId[id]).filter(Boolean);
    const seen = new Set(ordered.map((c) => String(c.id)));
    const rest = unmatchedDetailCategories
      .filter((c) => c && !seen.has(String(c.id)))
      .sort((a, b) => String(a.id).localeCompare(String(b.id)));
    return [...ordered, ...rest];
  })();

  const tbcTaxonomyCategories = (() => {
    const byId = Object.fromEntries(
      expenseDetailCategories.map((c) => [String(c?.id || ''), c]),
    );
    const ordered = TBC_TAXONOMY_ORDER.map((id) => byId[id]).filter(Boolean);
    const seen = new Set(ordered.map((c) => String(c.id)));
    const rest = expenseDetailCategories
      .filter((c) => c && !seen.has(String(c.id)))
      .sort((a, b) => String(a.id).localeCompare(String(b.id)));
    return [...ordered, ...rest];
  })();

  const cashflowTbcDetailLoading =
    showTbcExpenseDetailPanel &&
    (cashflowTbcExpensesDetail.key !== cashflowDetailKey ||
      cashflowTbcExpensesDetail.loading);
  const cashflowTbcDetailError =
    cashflowTbcExpensesDetail.key === cashflowDetailKey ? cashflowTbcExpensesDetail.error : '';
  const cashflowBankDetailLoading =
    showUnmatchedBankDetail &&
    (cashflowBankUnmatchedDetail.key !== cashflowDetailKey ||
      cashflowBankUnmatchedDetail.loading);
  const cashflowBankDetailError =
    cashflowBankUnmatchedDetail.key === cashflowDetailKey ? cashflowBankUnmatchedDetail.error : '';

  const confidenceBadgeClass = (raw) => {
    const v = String(raw || 'low').toLowerCase();
    if (v === 'high') return 'badge conf-high';
    if (v === 'medium') return 'badge conf-medium';
    return 'badge conf-low';
  };

  const handleDownloadBankExpensesExcel = async () => {
    const rows = expenseCategories.map((c) => ({
      კატეგორია: c.label_ka || c.id,
      ბუღალტრული_როლი:
        c.accounting_role === 'state_treasury' ? 'სახელმწიფო ხაზინა' : 'საოპერაციო ხარჯი',
      ხაზები: c.line_count || 0,
      ჯამი: Number(c.total_ge) || 0,
    }));
    if (!rows.length) return;
    const XLSX = await loadXlsxModule();
    const ws = XLSX.utils.json_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'TBC ხარჯები');
    const stamp = new Date().toISOString().slice(0, 10);
    XLSX.writeFile(wb, `TBC_ხარჯები_შეჯამება_${stamp}.xlsx`);
  };

  useEffect(() => {
    let cancelled = false;
    fetch('/api/status')
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => {
        if (cancelled || !json) return;
        const completedAt = json?.bank_refresh?.completed_at;
        if (!completedAt) {
          setBankRefreshAgeLabel('');
          return;
        }
        const ageSec = Math.max(
          0,
          Math.round((Date.now() - new Date(completedAt).getTime()) / 1000),
        );
        let label;
        if (ageSec < 60) label = `${ageSec} წმ წინ`;
        else if (ageSec < 3600) label = `${Math.floor(ageSec / 60)} წთ წინ`;
        else if (ageSec < 86400)
          label = `${Math.floor(ageSec / 3600)} სთ წინ`;
        else label = `${Math.floor(ageSec / 86400)} დღის წინ`;
        setBankRefreshAgeLabel(label);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [bankRefreshTick, reloadKey]);

  const handleBankRefreshDataReload = () => {
    setBankRefreshTick((v) => v + 1);
    onDataReload?.();
  };

  return (
    <div className="cashflow-page">
      <div className="bank-refresh-launcher">
        <button
          type="button"
          className="bank-refresh-launcher__btn"
          onClick={() => setShowBankRefreshModal(true)}
        >
          ბანკიდან ახალი მონაცემის ჩამოტანა
        </button>
        {bankRefreshAgeLabel && (
          <span className="bank-refresh-launcher__age">
            ბოლო ჩამოტანა: {bankRefreshAgeLabel}
          </span>
        )}
      </div>
      <BankRefreshModal
        open={showBankRefreshModal}
        onClose={() => setShowBankRefreshModal(false)}
        onDataReload={handleBankRefreshDataReload}
      />
      <div className="tab-hero">
        <span className="tab-hero-title">💳 ბანკის ანალიზი</span>
        <span className="tab-hero-desc">POS შემოსავალი · TBC/BOG ხარჯი · არამიბმული ბანკი · სამეურნეო მოძრაობა</span>
      </div>
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
          style={{ cursor: 'pointer', borderBottom: '3px solid #22c55e' }}
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
          title={tbcExpenses.ledger_note_ka || 'დააჭირე — ცხრილი და დეტალური კატეგორიები'}
          style={{ cursor: 'pointer', borderBottom: '3px solid #ef4444' }}
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
        <div
          className="kpi-card"
          role="button"
          tabIndex={0}
          onClick={() => setShowSalaryBreakdown((v) => !v)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setShowSalaryBreakdown((v) => !v);
            }
          }}
          title="იგივე მონაცემია, რაც ქვემოთ იყო ცხრილად — TBC ხელფასის ხაზების დაყოფა ტექსტით"
          style={{ cursor: 'pointer' }}
        >
          <div className="kpi-label">ხელფასები</div>
          <div className="kpi-value amount-negative">{formatNumber(salaryTotal)}</div>
          <div className="kpi-sub">{salaryCategory?.line_count || 0} ხაზი</div>
          <div className="kpi-sub">
            {showSalaryBreakdown
              ? '▼ დახურვა'
              : '▶ ხელფასის ჯგუფი (ოზურგეთი / დვაბზუ / სხვა)'}
          </div>
          {showSalaryBreakdown && (
            <div
              className="salary-breakdown-embed"
              onClick={(e) => e.stopPropagation()}
              role="presentation"
            >
              <table className="salary-breakdown-table">
                <thead>
                  <tr>
                    <th>ჯგუფი</th>
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
                        breakdown ცარიელია
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="kpi-card" style={{ borderBottom: `3px solid ${netCashflow >= 0 ? '#22c55e' : '#ef4444'}` }}>
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
          role="button"
          tabIndex={0}
          onClick={() => setShowUnmatchedBankDetail((v) => !v)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setShowUnmatchedBankDetail((v) => !v);
            }
          }}
          title={unmatchedAnalysis.ledger_note_ka || ''}
          style={{ cursor: 'pointer' }}
        >
          <div className="kpi-label">არამიბმული ბანკი (სულ)</div>
          <div className="kpi-value amount-negative">{formatNumber(unmatchedTotal)}</div>
          <div className="kpi-sub">{unmatchedAnalysis.line_count || 0} ხაზი</div>
          <div className="kpi-sub">
            {showUnmatchedBankDetail
              ? '▼ დახურვა — დეტალური კატეგორიები'
              : '▶ დეტალური კატეგორიები (BOG/TBC, ნიმუშის ხაზები)'}
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">არამიბმული — „სხვა" (გასაწმენდი)</div>
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

      {showUnmatchedBankDetail && (
        <div className="unmatched-bank-detail-panel">
          <p className="taxonomy-lead unmatched-bank-detail-lead">
            RS მომწოდებელთან რომ არ მიებმება — ავტომატური წესები + ხელით override; ქვემოთ ნიმუშის ხაზები
            (BOG/TBC). ბუღალტრულად ბევრი ხარჯია, მაგრამ RS ID-ზე ვერ მიბმულია.
          </p>
          {cashflowBankDetailLoading ? (
            <p className="chart-desc">დეტალური ნიმუშები იტვირთება...</p>
          ) : null}
          {cashflowBankDetailError ? (
            <p className="chart-desc amount-negative">
              დეტალური ნიმუშები ვერ ჩაიტვირთა: {cashflowBankDetailError}
            </p>
          ) : null}
          <div className="taxonomy-grid">
            {bankTaxonomyCategories.map((cat) => {
              const prev = Array.isArray(cat.rows_preview) ? cat.rows_preview : [];
              const show = prev.slice(0, 10);
              return (
                <div className="taxonomy-card" key={`bank-tax-panel-${cat.id}`}>
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
                        <div className="taxonomy-preview-row" key={`bank-panel-${cat.id}-${idx}`}>
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
                  <tr key={`um-row-${cat.id}`}>
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
                  <th>TOP „სხვა" პატერნი</th>
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
        </div>
      )}

      {showPosDailyTable && (
        <div className="pos-daily-panel">
          <CalendarRangePicker
            availableDays={posDailyAvailableDays}
            from={posDateFrom}
            to={posDateTo}
            onFromChange={setPosDateFrom}
            onToChange={setPosDateTo}
            label="POS დღიური — აირჩიე პერიოდი"
          >
            <div className="pos-range-totals">
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
          </CalendarRangePicker>
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
                      ამ პერიოდში ხაზები არაა — შეცვალე „დან / მდე" ან დააჭირე „მთელი პერიოდი"
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
            {cashflowTbcDetailLoading ? (
              <p className="chart-desc">დეტალური ნიმუშები იტვირთება...</p>
            ) : null}
            {cashflowTbcDetailError ? (
              <p className="chart-desc amount-negative">
                დეტალური ნიმუშები ვერ ჩაიტვირთა: {cashflowTbcDetailError}
              </p>
            ) : null}
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
  );
}
