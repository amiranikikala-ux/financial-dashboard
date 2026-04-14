/**
 * Mock API responses for E2E tests.
 * Mirrors the shape of real /api/data?tab=... responses.
 */

export const MOCK_META = {
  data_period_label: '2025-01 – 2025-03',
  strict_bank_only_total: 150000,
  combined_supplier_paid_total: 120000,
  suppliers_only_journal_or_bank: 3,
  generated_at: new Date().toISOString(),
  payment_scope_summary: { bank: 100000, journal: 20000 },
  truth_boundary_summary: { matched: 90, unmatched: 10 },
};

export const MOCK_SUPPLIERS = {
  suppliers: [
    {
      normalized_supplier: 'ტესტ მომწოდებელი',
      tax_id: '111111111',
      total_amount: 50000,
      paid_amount: 45000,
      balance: 5000,
      waybill_count: 12,
    },
    {
      normalized_supplier: 'მეორე მომწოდებელი',
      tax_id: '222222222',
      total_amount: 30000,
      paid_amount: 30000,
      balance: 0,
      waybill_count: 8,
    },
  ],
  meta: MOCK_META,
  response_meta: { tab: 'suppliers', row_count: 2, source: 'artifact' },
};

export const MOCK_PNL = {
  monthly_pnl: [
    { month: '2025-01', revenue: 80000, cogs: 50000, gross_profit: 30000 },
    { month: '2025-02', revenue: 90000, cogs: 55000, gross_profit: 35000 },
  ],
  meta: MOCK_META,
  response_meta: { tab: 'pnl_summary', row_count: 2, source: 'artifact' },
};

export const MOCK_ANALYTICS = {
  suppliers: MOCK_SUPPLIERS.suppliers,
  meta: MOCK_META,
  response_meta: { tab: 'analytics', row_count: 2, source: 'artifact' },
};

export const MOCK_CASHFLOW = {
  cashflow_summary: {
    total_inflow: 200000,
    total_outflow: 180000,
    net_cashflow: 20000,
    monthly: [
      { month: '2025-01', inflow: 100000, outflow: 90000 },
      { month: '2025-02', inflow: 100000, outflow: 90000 },
    ],
  },
  meta: MOCK_META,
  response_meta: { tab: 'cashflow_summary', row_count: 2, source: 'artifact' },
};

export const MOCK_WORKING_CAPITAL = {
  supplier_aging: [
    { supplier: 'ტესტ მომწოდებელი', current: 5000, overdue_30: 0, overdue_60: 0 },
  ],
  aging_summary: { total_current: 5000, total_overdue: 0 },
  ap_monthly_trend: [{ month: '2025-01', amount: 50000 }],
  meta: MOCK_META,
  response_meta: { tab: 'working_capital', row_count: 1, source: 'artifact' },
};

export const MOCK_RATIOS = {
  financial_ratios: {
    current_ratio: 1.5,
    quick_ratio: 1.2,
    debt_to_equity: 0.8,
    gross_margin: 0.35,
    net_margin: 0.12,
  },
  meta: MOCK_META,
  response_meta: { tab: 'ratios', row_count: 1, source: 'artifact' },
};

export const MOCK_FORECAST = {
  forecast: {
    months: ['2025-04', '2025-05', '2025-06'],
    revenue: [95000, 98000, 102000],
    expenses: [60000, 62000, 65000],
  },
  monthly_pnl: MOCK_PNL.monthly_pnl,
  meta: MOCK_META,
  response_meta: { tab: 'forecast', row_count: 3, source: 'artifact' },
};

export const MOCK_BUDGET = {
  budget: {
    categories: [
      { name: 'Revenue', planned: 300000, actual: 270000 },
      { name: 'COGS', planned: 180000, actual: 160000 },
    ],
  },
  meta: MOCK_META,
  response_meta: { tab: 'budget', row_count: 2, source: 'artifact' },
};

export const MOCK_VALUATION = {
  company_valuation: {
    dcf_value: 2500000,
    multiple_value: 2200000,
    book_value: 1800000,
  },
  meta: MOCK_META,
  response_meta: { tab: 'valuation', row_count: 1, source: 'artifact' },
};

export const MOCK_EXECUTIVE = {
  executive_summary: {
    kpis: { revenue: 270000, profit: 65000, margin: 0.24 },
    alerts: ['Cash flow positive trend detected'],
  },
  meta: MOCK_META,
  response_meta: { tab: 'executive', row_count: 1, source: 'artifact' },
};

export const MOCK_IMPORTED_PRODUCTS = {
  imported_products: {
    summary: { total_products: 50, total_value: 80000 },
    items: [
      { code: 'P001', name: 'ტესტ პროდუქტი', quantity: 100, value: 5000 },
    ],
  },
  meta: MOCK_META,
  response_meta: { tab: 'imported_products', row_count: 1, source: 'artifact' },
};

export const MOCK_RETAIL_SALES = {
  retail_sales: {
    summary: { total_sales: 150000, transaction_count: 3000 },
    monthly: [
      { month: '2025-01', amount: 50000 },
      { month: '2025-02', amount: 50000 },
      { month: '2025-03', amount: 50000 },
    ],
  },
  meta: MOCK_META,
  response_meta: { tab: 'retail_sales', row_count: 3, source: 'artifact' },
};

export const MOCK_STATUS = {
  data_file_modified: new Date().toISOString(),
  data_age_seconds: 120,
  pipeline: {
    state: 'idle',
    last_run: new Date().toISOString(),
    last_duration_s: 45.2,
    last_error: null,
    runs_total: 5,
    schedule_interval_min: 30,
  },
  server_time: new Date().toISOString(),
};

/** Map tab query param → mock response */
export function getMockForTab(tab) {
  const map = {
    suppliers: MOCK_SUPPLIERS,
    pnl_summary: MOCK_PNL,
    analytics: MOCK_ANALYTICS,
    cashflow_summary: MOCK_CASHFLOW,
    working_capital: MOCK_WORKING_CAPITAL,
    ratios: MOCK_RATIOS,
    forecast: MOCK_FORECAST,
    budget: MOCK_BUDGET,
    valuation: MOCK_VALUATION,
    executive: MOCK_EXECUTIVE,
    imported_products: MOCK_IMPORTED_PRODUCTS,
    retail_sales: MOCK_RETAIL_SALES,
  };
  return map[tab] || MOCK_SUPPLIERS;
}
