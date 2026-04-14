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
      'ორგანიზაცია': '(111111111) ტესტ მომწოდებელი',
      tax_id: '111111111',
      normalized_supplier: 'ტესტ მომწოდებელი',
      waybills_count: 12,
      total_nominal: 55000,
      total_returned: -5000,
      total_effective: 50000,
      total_paid: 45000,
      total_debt: 5000,
      bank_paid: 40000,
      manual_paid: 5000,
      strict_bank_paid: 40000,
      payment_scope: 'bank_matched',
      payment_scope_note: 'ბანკით დამთხვეული',
    },
    {
      'ორგანიზაცია': '(222222222) მეორე მომწოდებელი',
      tax_id: '222222222',
      normalized_supplier: 'მეორე მომწოდებელი',
      waybills_count: 8,
      total_nominal: 30000,
      total_returned: 0,
      total_effective: 30000,
      total_paid: 30000,
      total_debt: 0,
      bank_paid: 30000,
      manual_paid: 0,
      strict_bank_paid: 30000,
      payment_scope: 'bank_matched',
      payment_scope_note: '',
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
    overall: { row_count: 100, total_revenue: 150000, total_cost: 90000, total_profit: 60000 },
    by_object: [
      { object: 'დვაბზუ', revenue: 80000, cost: 48000, profit: 32000 },
      { object: 'ოზურგეთი', revenue: 70000, cost: 42000, profit: 28000 },
    ],
    by_month: [
      { month: '2025-01', object: 'დვაბზუ', revenue: 50000, cost: 30000, profit: 20000, margin_pct: 40 },
      { month: '2025-02', object: 'დვაბზუ', revenue: 50000, cost: 30000, profit: 20000, margin_pct: 40 },
      { month: '2025-03', object: 'ოზურგეთი', revenue: 50000, cost: 30000, profit: 20000, margin_pct: 40 },
    ],
    top_products_by_revenue: [
      { product: 'ტესტ პროდუქტი', revenue: 30000, profit: 12000 },
    ],
    top_products_by_profit: [],
    top_categories_by_profit: [],
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

export const MOCK_IMPORTED_SUPPLIER_DETAIL = {
  imported_products_supplier_detail: {
    match_type: 'tax_id',
    has_source: true,
    ambiguous: false,
    truncation_suspected_any: false,
    supplier_top_products_limit: 5,
    label_ka: 'შემოტანილი პროდუქცია (reference)',
    entry: {
      total_amount_ge: 42000,
      distinct_product_count: 3,
      distinct_waybill_count: 7,
      date_range: { start: '2025-01-05', end: '2025-03-15' },
      top_products: [
        { product_name: 'ტესტ პროდუქტი A', product_code: 'PA01', total_amount_ge: 20000, total_quantity: 500, unit: 'კგ', distinct_waybill_count: 3 },
        { product_name: 'ტესტ პროდუქტი B', product_code: 'PB02', total_amount_ge: 15000, total_quantity: 300, unit: 'ლ', distinct_waybill_count: 2 },
      ],
    },
  },
  meta: MOCK_META,
  response_meta: { tab: 'imported_products_supplier_detail', row_count: 1, source: 'artifact' },
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
    imported_products_supplier_detail: MOCK_IMPORTED_SUPPLIER_DETAIL,
    retail_sales: MOCK_RETAIL_SALES,
  };
  return map[tab] || MOCK_SUPPLIERS;
}
