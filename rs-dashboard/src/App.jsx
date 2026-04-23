import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import './index.css';
import { STORAGE_KEY } from './financeMerge.js';
import DashboardTabs from './components/DashboardTabs.jsx';
import TrustBanner from './components/TrustBanner.jsx';
import useHashTab from './hooks/useHashTab.js';
import { fetchApiJson } from './lib/api.js';
import LiveClock from './components/LiveClock.jsx';
import RefreshButton from './components/RefreshButton.jsx';
import MobileNav from './components/MobileNav.jsx';
import useDataStatus from './hooks/useDataStatus.js';
import DateTimeCalendarPicker from './components/DateTimeCalendarPicker.jsx';
// ChatAssistant is eager-loaded on purpose: it is a global FAB that must be
// present on every tab and every route. Lazy-loading it previously caused
// the FAB to occasionally disappear on tab switches (notably #suppliers)
// when the Vite dev server re-evaluated the chunk and the Suspense boundary
// rendered its `null` fallback. Keeping it in the main bundle guarantees
// the button is always mounted from the first paint.
import ChatAssistant from './components/ChatAssistant.jsx';

const Analytics = lazy(() => import('./Analytics.jsx'));
const DeadStock = lazy(() => import('./DeadStock.jsx'));
const DebtPlan = lazy(() => import('./DebtPlan.jsx'));
const PnL = lazy(() => import('./PnL.jsx'));
const WorkingCapital = lazy(() => import('./WorkingCapital.jsx'));
const Ratios = lazy(() => import('./Ratios.jsx'));
const Forecast = lazy(() => import('./Forecast.jsx'));
const Budget = lazy(() => import('./Budget.jsx'));
const Valuation = lazy(() => import('./Valuation.jsx'));
const Executive = lazy(() => import('./Executive.jsx'));
const ImportedProducts = lazy(() => import('./ImportedProducts.jsx'));
const RetailSales = lazy(() => import('./RetailSales.jsx'));
const Cashflow = lazy(() => import('./Cashflow.jsx'));
const SupplierModal = lazy(() => import('./SupplierModal.jsx'));
const Suppliers = lazy(() => import('./Suppliers.jsx'));
const Waybills = lazy(() => import('./Waybills.jsx'));
const Insights = lazy(() => import('./Insights.jsx'));
const VATAudit = lazy(() => import('./VATAudit.jsx'));

const SAFE_PERIOD_REQUEST_TABS = new Set([
  'suppliers',
  'retail_sales',
  'imported_products',
  'working_capital',
  'forecast',
  'budget',
  'valuation',
  'executive',
  'pnl_summary',
]);

const PERIOD_PICKER_TABS = new Set([
  'suppliers',
  'waybills',
  'retail_sales',
  'imported_products',
  'working_capital',
  'forecast',
  'budget',
  'valuation',
  'executive',
  'insights',
  'pnl',
  'analytics',
]);

function App() {
  const [data, setData] = useState({ suppliers: [], waybills: [], waybills_summary: null, meta: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [activeTab, setActiveTab] = useHashTab('suppliers');
  const [selectedSupplier, setSelectedSupplier] = useState(null);
  const [localPayments, setLocalPayments] = useState({});
  const [importedProductsResponse, setImportedProductsResponse] = useState(null);
  const [importedProductsLoading, setImportedProductsLoading] = useState(false);
  const [importedProductsError, setImportedProductsError] = useState(null);
  const [importedProductsLoadedKey, setImportedProductsLoadedKey] = useState(-1);
  const { status: dataStatus, refreshing, triggerRefresh } = useDataStatus();
  const [globalFromDate, setGlobalFromDate] = useState('');
  const [globalToDate, setGlobalToDate] = useState('');
  const [globalFromTime, setGlobalFromTime] = useState('00:00');
  const [globalToTime, setGlobalToTime] = useState('23:59');

  const buildCanonicalPeriodParams = useCallback((tabKey) => {
    if (!SAFE_PERIOD_REQUEST_TABS.has(tabKey)) return null;
    const fromDate = globalFromDate || globalToDate;
    const toDate = globalToDate || globalFromDate;
    if (!fromDate && !toDate) return null;
    return {
      from_date: fromDate,
      to_date: toDate,
      from_time: globalFromTime || '00:00',
      to_time: globalToTime || '23:59',
    };
  }, [globalFromDate, globalFromTime, globalToDate, globalToTime]);

  const appendCanonicalPeriodParams = useCallback((params, tabKey) => {
    const periodParams = buildCanonicalPeriodParams(tabKey);
    if (!periodParams) return params;
    Object.entries(periodParams).forEach(([key, value]) => {
      params.set(key, value);
    });
    return params;
  }, [buildCanonicalPeriodParams]);

  const importedProductsParams = new URLSearchParams({ tab: 'imported_products' });
  appendCanonicalPeriodParams(importedProductsParams, 'imported_products');
  const importedProductsQueryString = importedProductsParams.toString();
  const importedProductsRequestKey = `${reloadKey}:${importedProductsQueryString}`;

  useEffect(() => {
    const POLLING_INTERVAL = 5 * 60 * 1000;
    let lastFetchTime = Date.now();

    const triggerReload = () => {
      lastFetchTime = Date.now();
      setReloadKey((k) => k + 1);
    };

    const intervalId = setInterval(() => {
      if (document.visibilityState === 'visible') {
        triggerReload();
      }
    }, POLLING_INTERVAL);

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        const now = Date.now();
        if (now - lastFetchTime >= POLLING_INTERVAL) {
          triggerReload();
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  useEffect(() => {
    if (activeTab === 'imported_products' || activeTab === 'waybills' || activeTab === 'cashflow' || activeTab === 'insights' || activeTab === 'debt_plan' || activeTab === 'vat_audit') return undefined;
    let active = true;
    const requestTab = activeTab === 'pnl' ? 'pnl_summary' : activeTab === 'analytics' ? 'suppliers' : activeTab;
    const params = new URLSearchParams({ tab: requestTab });
    appendCanonicalPeriodParams(params, requestTab);
    setTimeout(() => {
      if (active) {
        setLoading(true);
        setError(null);
      }
    }, 0);
    fetchApiJson(`/api/data?${params.toString()}`)
      .then((json) => {
        if (!active) return;
        setData({
          suppliers: [],
          waybills: [],
          waybills_summary: null,
          meta: null,
          ...json,
        });
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        console.error('Failed to load data:', err);
        setError(err.message);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [activeTab, appendCanonicalPeriodParams, reloadKey]);

  useEffect(() => {
    if (activeTab !== 'cashflow') return undefined;

    let active = true;
    const controller = new AbortController();
    const params = new URLSearchParams({ tab: 'cashflow_summary' });
    appendCanonicalPeriodParams(params, 'cashflow_summary');
    setTimeout(() => {
      if (active) {
        setLoading(true);
        setError(null);
      }
    }, 0);

    fetchApiJson(`/api/data?${params.toString()}`, { signal: controller.signal })
      .then((json) => {
        if (!active) return;
        setData({
          suppliers: [],
          waybills: [],
          waybills_summary: null,
          meta: null,
          ...json,
        });
        setLoading(false);
      })
      .catch((err) => {
        if (!active || err.name === 'AbortError') return;
        console.error('Failed to load cashflow summary:', err);
        setError(err.message);
        setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [activeTab, appendCanonicalPeriodParams, reloadKey]);

  useEffect(() => {
    if (activeTab !== 'imported_products') return undefined;
    if (importedProductsLoadedKey === importedProductsRequestKey && importedProductsResponse) return undefined;

    let active = true;
    const controller = new AbortController();
    setTimeout(() => {
      if (!active) return;
      setImportedProductsLoading(true);
      setImportedProductsError(null);
    }, 0);

    fetchApiJson(`/api/data?${importedProductsQueryString}`, { signal: controller.signal })
      .then((json) => {
        if (!active) return;
        setImportedProductsResponse(json);
        setImportedProductsLoadedKey(importedProductsRequestKey);
        setImportedProductsLoading(false);
      })
      .catch((err) => {
        if (!active || err.name === 'AbortError') return;
        console.error('Failed to load imported products:', err);
        setImportedProductsError(err.message);
        setImportedProductsLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [activeTab, importedProductsLoadedKey, importedProductsQueryString, importedProductsRequestKey, importedProductsResponse]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') {
          setTimeout(() => setLocalPayments(parsed), 0);
        }
      }
    } catch {
      /* ignore */
    }
  }, []);

  const persistLocalPayments = useCallback((next) => {
    setLocalPayments(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }, []);

  const formatNumber = (num) => {
    return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL', maximumFractionDigits: 0 }).format(
      num || 0
    );
  };

  const expectedTab = activeTab === 'pnl' ? 'pnl_summary' : activeTab === 'cashflow' ? 'cashflow_summary' : activeTab === 'analytics' ? 'suppliers' : activeTab;
  const currentResponseMeta = activeTab === 'imported_products'
    ? importedProductsResponse?.response_meta ?? null
    : data.response_meta?.tab === expectedTab
      ? data.response_meta
      : null;
  const currentMeta = activeTab === 'imported_products'
    ? importedProductsResponse?.meta ?? null
    : data.response_meta?.tab === expectedTab
      ? data.meta ?? null
      : null;
  const showPeriodPicker = PERIOD_PICKER_TABS.has(activeTab);
  const pickerLabel = currentMeta?.data_period_label || ((globalFromDate || globalToDate) ? 'არჩეული პერიოდი' : 'პერიოდი');
  const showHeaderPaymentStats = Boolean(
    currentMeta
    && (
      currentMeta.strict_bank_only_total != null
      || currentMeta.combined_supplier_paid_total != null
      || currentMeta.suppliers_only_journal_or_bank != null
    )
  );
  const monthlyPnl = Array.isArray(data.monthly_pnl) ? data.monthly_pnl : [];
  const supplierAging = Array.isArray(data.supplier_aging) ? data.supplier_aging : [];
  const agingSummary = data.aging_summary || {};
  const apMonthlyTrend = Array.isArray(data.ap_monthly_trend) ? data.ap_monthly_trend : [];
  const financialRatios = data.financial_ratios || null;
  const forecastBlock = data.forecast || null;
  const budgetBlock = data.budget || null;
  const companyValuation = data.company_valuation || null;
  const executiveSummary = data.executive_summary || null;
  const paymentScopeSummary = currentMeta?.payment_scope_summary || {};
  const truthBoundarySummary = currentMeta?.truth_boundary_summary || {};
  const suppliersOnlyJournalOrBank = Number(currentMeta?.suppliers_only_journal_or_bank) || 0;
  const showGlobalError = Boolean(error) && activeTab !== 'imported_products' && activeTab !== 'waybills' && activeTab !== 'insights';
  const showGlobalLoading = loading && activeTab !== 'imported_products' && activeTab !== 'waybills' && activeTab !== 'insights' && activeTab !== 'debt_plan';
  const tabSuspenseFallback = <div className="loading">იტვირთება გვერდი...</div>;

  return (
    <div className="dashboard-container">
      {showGlobalError && (
        <div className="local-pay-banner" style={{ background: '#ef4444', color: '#fff' }} role="alert">
          <strong>შეცდომა:</strong> {error}
          <button type="button" onClick={() => setReloadKey((v) => v + 1)} style={{ marginLeft: 16, padding: '4px 8px', background: '#fff', color: '#ef4444', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
            თავიდან ცდა
          </button>
        </div>
      )}
      {showGlobalLoading ? (
        <div className="loading">იტვირთება მონაცემები...</div>
      ) : (
        <>
      <header>
        <div className="header-top-row">
          <div className="header-brand-block">
            <h1>RS Dashboard</h1>
            <div className="subtitle">ფინანსური ანალიზი და ზედნადებების კონტროლი</div>
          </div>
          <div className="header-center">
            {showPeriodPicker && (
              <DateTimeCalendarPicker
                fromDate={globalFromDate}
                fromTime={globalFromTime}
                toDate={globalToDate}
                toTime={globalToTime}
                onFromDateChange={setGlobalFromDate}
                onFromTimeChange={setGlobalFromTime}
                onToDateChange={setGlobalToDate}
                onToTimeChange={setGlobalToTime}
                label={pickerLabel}
              />
            )}
            {showHeaderPaymentStats && (
                <span className="header-stats-compact">
                  ბანკი: <span className="stat-val">{formatNumber(currentMeta.strict_bank_only_total)}</span>
                  &nbsp;·&nbsp;გადახდილი: <span className="stat-val">{formatNumber(currentMeta.combined_supplier_paid_total)}</span>
                  {Number(currentMeta.suppliers_only_journal_or_bank) > 0 && (
                    <>&nbsp;·&nbsp;RS-ის გარეშე: <span className="stat-val">{currentMeta.suppliers_only_journal_or_bank}</span></>
                  )}
                </span>
            )}
          </div>
          <div className="header-right-controls">
            <RefreshButton status={dataStatus} refreshing={refreshing} onRefresh={triggerRefresh} />
            <LiveClock lastUpdated={currentMeta?.generated_at} />
          </div>
        </div>
        <DashboardTabs activeTab={activeTab} onTabChange={setActiveTab} />
      </header>

      <div className="panel">
        {activeTab !== 'waybills' && (
          <TrustBanner
            responseMeta={currentResponseMeta}
            waybillsSummary={{}}
            paymentScopeSummary={paymentScopeSummary}
            truthBoundarySummary={truthBoundarySummary}
            suppliersOnlyJournalOrBank={suppliersOnlyJournalOrBank}
          />
        )}

        {activeTab === 'suppliers' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <Suppliers
              suppliers={data.suppliers}
              localPayments={localPayments}
              meta={currentMeta}
              persistLocalPayments={persistLocalPayments}
              formatNumber={formatNumber}
              onSupplierClick={setSelectedSupplier}
              responseMeta={currentResponseMeta}
              supplierConcentration={data.supplier_concentration}
            />
          </Suspense>
        ) : activeTab === 'waybills' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <Waybills
              formatNumber={formatNumber}
              reloadKey={reloadKey}
              fromDate={globalFromDate}
              fromTime={globalFromTime}
              toDate={globalToDate}
              toTime={globalToTime}
            />
          </Suspense>
        ) : activeTab === 'analytics' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <Analytics suppliers={data.suppliers} localPayments={localPayments} />
          </Suspense>
        ) : activeTab === 'imported_products' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <ImportedProducts
              response={importedProductsResponse}
              loading={importedProductsLoading}
              error={importedProductsError}
              onRetry={() => setReloadKey((v) => v + 1)}
            />
          </Suspense>
        ) : activeTab === 'pnl' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <PnL monthlyPnl={monthlyPnl} />
          </Suspense>
        ) : activeTab === 'working_capital' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <WorkingCapital
              supplierAging={supplierAging}
              agingSummary={agingSummary}
              apMonthlyTrend={apMonthlyTrend}
              paymentScopeSummary={paymentScopeSummary}
              truthBoundarySummary={truthBoundarySummary}
              onSupplierClick={setSelectedSupplier}
            />
          </Suspense>
        ) : activeTab === 'ratios' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <Ratios financialRatios={financialRatios} />
          </Suspense>
        ) : activeTab === 'forecast' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <Forecast forecast={forecastBlock} monthlyPnl={monthlyPnl} />
          </Suspense>
        ) : activeTab === 'budget' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <Budget budget={budgetBlock} />
          </Suspense>
        ) : activeTab === 'valuation' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <Valuation companyValuation={companyValuation} />
          </Suspense>
        ) : activeTab === 'executive' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <Executive executiveSummary={executiveSummary} />
          </Suspense>
        ) : activeTab === 'retail_sales' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <RetailSales retailSales={data.retail_sales} responseMeta={currentResponseMeta} />
          </Suspense>
        ) : activeTab === 'dead_stock' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <DeadStock deadStock={data.dead_stock_summary} />
          </Suspense>
        ) : activeTab === 'debt_plan' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <DebtPlan />
          </Suspense>
        ) : activeTab === 'cashflow' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <Cashflow
              data={data}
              reloadKey={reloadKey}
              formatNumber={formatNumber}
            />
          </Suspense>
        ) : activeTab === 'insights' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <Insights
              reloadKey={reloadKey}
              fromDate={globalFromDate}
              fromTime={globalFromTime}
              toDate={globalToDate}
              toTime={globalToTime}
            />
          </Suspense>
        ) : activeTab === 'vat_audit' ? (
          <Suspense fallback={tabSuspenseFallback}>
            <VATAudit reloadKey={reloadKey} />
          </Suspense>
        ) : null}
      </div>
        </>
      )}
      {selectedSupplier && (
        <Suspense fallback={tabSuspenseFallback}>
          <SupplierModal
            supplier={selectedSupplier}
            agingData={supplierAging}
            truthBoundarySummary={truthBoundarySummary}
            onClose={() => setSelectedSupplier(null)}
          />
        </Suspense>
      )}
      <MobileNav activeTab={activeTab} onTabChange={setActiveTab} />
      <ChatAssistant />
    </div>
  );
}

export default App;
