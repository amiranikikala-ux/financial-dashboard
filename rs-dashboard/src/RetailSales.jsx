import { useState, useMemo } from 'react';
import {
  ResponsiveContainer,
  LineChart, Line,
  BarChart, Bar,
  AreaChart, Area,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import CollapsibleSection from './components/CollapsibleSection.jsx';
import ExportButton from './components/ExportButton.jsx';

const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#a855f7', '#06b6d4', '#84cc16', '#ec4899'];
const STORE_COLOR = {
  'დვაბზუ': '#3b82f6',
  'ოზურგეთი': '#10b981',
  'უცნობი': '#94a3b8',
};

function InfoTip({ text }) {
  const [show, setShow] = useState(false);
  if (!text) return null;
  return (
    <span
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      style={{ position: 'relative', display: 'inline-block', marginLeft: 6, lineHeight: 1 }}
    >
      <span
        style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 15, height: 15, borderRadius: '50%',
          background: '#475569', color: '#cbd5e1',
          fontSize: 10, fontWeight: 600, cursor: 'help', userSelect: 'none',
        }}
      >i</span>
      {show && (
        <span style={{
          position: 'absolute', bottom: '120%', left: '50%', transform: 'translateX(-50%)',
          background: '#0f172a', border: '1px solid #475569', borderRadius: 6,
          padding: '8px 10px', fontSize: 12, color: '#e2e8f0', width: 280,
          zIndex: 1000, boxShadow: '0 4px 14px rgba(0,0,0,0.5)',
          textTransform: 'none', letterSpacing: 0, fontWeight: 400,
          lineHeight: 1.45, whiteSpace: 'normal', textAlign: 'left', pointerEvents: 'none',
        }}>{text}</span>
      )}
    </span>
  );
}

const TIPS = {
  revenue: 'POS-ში რეგისტრირებული გაყიდვების ჯამი (ORD_jamjam — ფასდაკლების შემდეგ). წყარო: MegaPlus DB, ORDERS.ORD_ACT=1.',
  cost: 'ფაქტურიდან გათვლილი (imputed) თვითღირებულება — მომწოდებლის ფაქტურიდან ერთეულზე. POS-ის ცარიელ ORD_GETPRICE-ს ცვლის. შესაძლოა განსხვავდებოდეს რეგისტრირებული POS cost-ისგან.',
  profit: 'შემოსავალი − imputed cost. ფაქტურიდან გათვლილი მოგება. POS-რეგისტრირებული მოგებისგან განსხვავდება ფაქტურის cost-ის სიზუსტის მიხედვით.',
  margin: 'მოგება / შემოსავალი × 100. რადგან cost imputed-ია, რეალურ POS-მარჟასთან მცირე გადახრა შესაძლებელია.',
  rows: 'გაყიდვის ხაზების რაოდენობა (per-product per-receipt). 1 ჩეკში რამდენიმე ხაზი იქნება, ერთი ხაზი = ერთი პროდუქტი ერთ ჩეკში.',
  receipts: 'უნიკალური ჩეკების რაოდენობა (ORD_N). ერთ ჩეკში რამდენიმე ხაზია — საქონლის რაოდენობით.',
  aov: 'საშუალო ჩეკი (Average Order Value) = სულ შემოსავალი ÷ ჩეკების რაოდენობა. ერთ ვიზიტში დატოვებული საშუალო თანხა.',
  itemsPerBasket: 'ერთ ჩეკში რამდენი ხაზი (პროდუქტი) საშუალოდ. = ხაზები ÷ ჩეკები.',
  qtyPerBasket: 'ერთ ჩეკში რამდენი ცალი / კგ. = რაოდენობა ÷ ჩეკები.',
  payment: 'გადახდის ფორმის ჭრილი — ნაღდი ფული vs ბანკის ბარათი. წყარო: ORD_PAY_TYP. 0=ნაღდი, 1=ბარათი.',
  hour: 'რომელ საათში რამდენი გაიყიდა (0-23). ცარიელი თარიღის ხაზები გამოტოვებულია.',
  dow: 'კვირის რომელ დღეს რამდენი გაიყიდა (ორშაბათი-კვირა).',
  daily: 'ბოლო 365 დღის შემოსავალი — ერთ დღეზე. რეგრესი / ცემპი თვალით ჩანს.',
  calendar: 'კალენდრის თერმულ რუკა — ბოლო 365 დღე. მუქი = მეტი ჩეკი იმ დღეს.',
  cashier: 'მოლარის ჭრილი — სახელის წყარო DB-ში ცარიელია, ID-ს ვიყენებთ. AOV = ერთ ჩეკზე საშუალო თანხა.',
  register: 'სალარო-ის (cash-register) ჭრილი — ORD_TAB_ID-ის მიხედვით.',
  returns: 'ORD_ACT=2 დაბრუნება + ORD_ACT=0 გაუქმება. POS-ის ფასდაკლებად გადანაცვლებული გაყიდვები + ბათილი ჩეკები.',
  markdown: 'ფასდაკლება — სრული ფასი (ORD_FASDAKLEBAMDE) − გადახდილი (ORD_jamjam). რამდენ ფულზე იქნებოდა მეტი შემოსავალი ფასდაკლების გარეშე.',
  pareto: '80/20 — რამდენი პროდუქტი იძლევა შემოსავლის 80%-ს. რაც ნაკლები — მით უფრო დამოკიდებული ხარ ცოტა SKU-ზე.',
  hhi: 'Herfindahl-Hirschman Index — კონცენტრაციის კოეფიციენტი (პროდუქტის წილების კვადრატთა ჯამი). <1500 = დაბალი, 1500-2500 = საშუალო, >2500 = მაღალი (იშვიათი retail-ში — ისიც ცუდია).',
  shift: 'ცვლა = ერთი მოლარის მუშაობის დრო ერთ სალაროზე (ჩვეულებრივ 8 დილის - 1 ღამის). ID = YYMMDDHHMM. მოლარე #1 = მფლობელი (კაბ).',
  vat: 'დღგ = დამატებული ღირებულების გადასახადი (VAT). ORD_VAT = ხაზის დღგ ლარში. ეფექტური განაკვეთი = ჯამი დღგ ÷ ჯამი შემოსავალი. გამონაკლისი ხაზი = ORD_VAT=0 (ხშირად სიგარეტი).',
  returnsByProduct: 'რომელი პროდუქტი ბრუნდება ხშირად. მცირე რიცხვები ნორმალურია — შემთხვევითი დაბრუნებები. გამოიყენე მენეჯერული ცხნილი თუ რომელიმე SKU სტაბილურად დიდი წილით ბრუნდება.',
  returnsByMonth: 'დაბრუნების თვიური ცემპი. სტაბილურია? ან რომელიმე თვე გამოირჩევა? — გამოძიება საჭიროა.',
  discountLift: 'რა მოგება იქნებოდა ფასდაკლების გარეშე — actual vs hypothetical. დაკარგული მარჟა = ფასდაკლების ჯამი (cost ცვლილებას არ ექვემდებარება).',
  discountByCat: 'რომელი კატეგორია იღებს ფასდაკლებას. დიდი ფასდაკლება + დაბალი ფასდაკლების % = ფართო პოლიტიკა. მცირე ფასდაკლება + მაღალი % = სელექტიური clearance.',
  crossStore: 'მაღაზია vs მაღაზია — იგივე SKU. გვიჩვენებს რომელი პროდუქტი ორივე მაღაზიაში იყიდება განსხვავებული ფასით ან მარჟით. გაფილტრულია მხოლოდ რეალური EAN შტრიხკოდი (>=8 ციფრი). მაღაზიის ფილტრს არ ემორჩილება — comparison-ის არსი თვითონ cross-store-ია. ცხოვრების ჯამი (period filter არ ვრცელდება).',
  deadStock: 'მკვდარი მარაგი — პროდუქტი რომელიც ნაშთშია (P_QUANT > 0), მაგრამ დიდი ხანია არ გაყიდულა. წყარო: PRODUCTS.P_QUANT × P_GETPRICE = ნაშთის ღირებულება. ბუჩქი ბოლო გაყიდვის თარიღით განისაზღვრება (snapshot — ბოლო backup-ის თარიღი). უარყოფითი ნაშთი (P_QUANT < 0) = POS შეცდომა (გაყიდულია, მაგრამ ფაქტურით არ ჩამოსულა). უფასო პოზიციები (P_PRICE = 0) = ოპერაციული (მაგ. „უფასო პარკი"). მაღაზიის ფილტრს ემორჩილება. პერიოდის ფილტრი არ ვრცელდება — snapshot-ია, არა flow.',
};

const GEL = new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL', maximumFractionDigits: 0 });
const GEL2 = new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL', maximumFractionDigits: 2 });
const NUM = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 2 });
const INT = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 0 });

const asArray = (v) => (Array.isArray(v) ? v : []);
const toNum = (v) => Number(v) || 0;
const fmtMoney = (v) => GEL.format(toNum(v));
const fmtMoney2 = (v) => GEL2.format(toNum(v));
const fmtNum = (v) => NUM.format(toNum(v));
const fmtInt = (v) => INT.format(toNum(v));
const fmtPct = (v) => `${toNum(v).toFixed(2)}%`;

function renderMoneyClass(value) {
  return toNum(value) >= 0 ? 'amount-positive' : 'amount-negative';
}

function renderDateRange(range) {
  return `${range?.min || '—'} → ${range?.max || '—'}`;
}

// ─── Hour × Day-of-Week heatmap (7 rows × 24 cols = 168 cells) ──────────────
function HourDowHeatmap({ grid }) {
  const cellW = 22, cellH = 22, gap = 2;
  const dayLabels = { 1: 'ორშ', 2: 'სამ', 3: 'ოთხ', 4: 'ხუთ', 5: 'პარ', 6: 'შაბ', 7: 'კვი' };
  if (!grid || grid.length === 0) return <div className="kpi-sub">მონაცემი არ არის</div>;
  // Build (dow, hour) → revenue map
  const map = new Map();
  let maxRev = 0;
  grid.forEach((c) => {
    map.set(`${c.dow}-${c.hour}`, c);
    if (toNum(c.revenue_ge) > maxRev) maxRev = toNum(c.revenue_ge);
  });
  const intensity = (rev) => {
    if (!maxRev || !rev) return '#1e293b';
    const r = rev / maxRev;
    if (r > 0.75) return '#ef4444';
    if (r > 0.50) return '#f59e0b';
    if (r > 0.25) return '#eab308';
    if (r > 0.05) return '#84cc16';
    return '#1e293b';
  };
  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 4 }}>
        {/* Day labels column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap, marginRight: 6 }}>
          <div style={{ height: cellH, fontSize: 10, color: 'transparent' }}>·</div>
          {[1, 2, 3, 4, 5, 6, 7].map((d) => (
            <div key={d} style={{ height: cellH, fontSize: 11, color: '#94a3b8', lineHeight: `${cellH}px` }}>
              {dayLabels[d]}
            </div>
          ))}
        </div>
        {/* Grid */}
        <div style={{ display: 'flex', flexDirection: 'column', gap }}>
          {/* Hour labels row */}
          <div style={{ display: 'flex', gap }}>
            {Array.from({ length: 24 }, (_, h) => (
              <div key={h} style={{ width: cellW, height: cellH, fontSize: 10, color: '#94a3b8', textAlign: 'center', lineHeight: `${cellH}px` }}>
                {h % 3 === 0 ? `${String(h).padStart(2, '0')}` : ''}
              </div>
            ))}
          </div>
          {/* 7 rows */}
          {[1, 2, 3, 4, 5, 6, 7].map((dw) => (
            <div key={dw} style={{ display: 'flex', gap }}>
              {Array.from({ length: 24 }, (_, hr) => {
                const cell = map.get(`${dw}-${hr}`);
                const rev = toNum(cell?.revenue_ge);
                return (
                  <div
                    key={hr}
                    title={cell ? `${dayLabels[dw]} ${String(hr).padStart(2, '0')}:00 — ${fmtMoney(rev)} · ${fmtInt(cell.receipts)} ჩეკი` : ''}
                    style={{
                      width: cellW, height: cellH, borderRadius: 2,
                      background: intensity(rev),
                      cursor: 'help',
                    }}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, fontSize: 10, color: '#94a3b8' }}>
        <span>ცარიელი</span>
        {['#1e293b', '#84cc16', '#eab308', '#f59e0b', '#ef4444'].map((c) => (
          <span key={c} style={{ width: 12, height: 12, background: c, borderRadius: 2 }} />
        ))}
        <span>დაკავებული</span>
      </div>
    </div>
  );
}

// ─── Calendar heatmap (mirror Waybills) ─────────────────────────────────────
function CalendarHeatmap({ days }) {
  const cellSize = 12, cellGap = 2;
  const dayLabels = ['ორშ', 'სამ', 'ოთხ', 'ხუთ', 'პარ', 'შაბ', 'კვი'];
  const maxRev = days.reduce((m, d) => Math.max(m, toNum(d.revenue_ge)), 0);
  if (days.length === 0) return <div className="kpi-sub">მონაცემი არ არის</div>;
  const columns = [];
  let currentWeek = [];
  days.forEach((d, i) => {
    if (i === 0 && d.weekday > 0) {
      for (let p = 0; p < d.weekday; p++) currentWeek.push(null);
    }
    currentWeek.push(d);
    if (currentWeek.length === 7) {
      columns.push(currentWeek);
      currentWeek = [];
    }
  });
  if (currentWeek.length > 0) {
    while (currentWeek.length < 7) currentWeek.push(null);
    columns.push(currentWeek);
  }
  const intensity = (rev) => {
    if (!maxRev || !rev) return '#1e293b';
    const r = rev / maxRev;
    if (r > 0.75) return '#10b981';
    if (r > 0.50) return '#34d399';
    if (r > 0.25) return '#6ee7b7';
    if (r > 0.05) return '#a7f3d0';
    return '#1e293b';
  };
  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: cellGap, marginRight: 4 }}>
          {dayLabels.map((l, i) => (
            <div key={l} style={{ height: cellSize, fontSize: 9, color: '#94a3b8', lineHeight: `${cellSize}px` }}>
              {i % 2 === 0 ? l : ''}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: cellGap }}>
          {columns.map((col, ci) => (
            <div key={ci} style={{ display: 'flex', flexDirection: 'column', gap: cellGap }}>
              {col.map((d, di) => (
                <div
                  key={di}
                  title={d ? `${d.day} · ${fmtMoney(d.revenue_ge)} · ${fmtInt(d.receipts)} ჩეკი` : ''}
                  style={{
                    width: cellSize, height: cellSize, borderRadius: 2,
                    background: d ? intensity(d.revenue_ge) : 'transparent',
                    cursor: d ? 'help' : 'default',
                  }}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontSize: 10, color: '#94a3b8' }}>
        <span>ნაკლები</span>
        {['#1e293b', '#a7f3d0', '#6ee7b7', '#34d399', '#10b981'].map((c) => (
          <span key={c} style={{ width: 10, height: 10, background: c, borderRadius: 2 }} />
        ))}
        <span>მეტი</span>
      </div>
    </div>
  );
}

export default function RetailSales({ retailSales, responseMeta }) {
  const summary = retailSales && typeof retailSales === 'object' ? retailSales : null;
  const [topProductsLimit, setTopProductsLimit] = useState(20);
  const [storeFilter, setStoreFilter] = useState('all');
  const [productSearch, setProductSearch] = useState('');
  const [crossStoreSortBy, setCrossStoreSortBy] = useState('price_gap');
  const [deadStockBucket, setDeadStockBucket] = useState('dead_365d_plus');
  // Period filter — applies to time-series + KPI block. Aggregate
  // top-product / hour / dow lists stay lifetime (banner indicates).
  const [periodPreset, setPeriodPreset] = useState('all');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');

  if (!summary) {
    return (
      <div className="cashflow-page pnl-empty">
        <div className="kpi-card" style={{ maxWidth: 520, margin: '48px auto', textAlign: 'center' }}>
          <div className="kpi-label">Retail Sales summary ჯერ არ არის</div>
          <div className="kpi-sub" style={{ marginTop: 12 }}>გაუშვი ტერმინალში:</div>
          <code className="pnl-code-hint">python generate_dashboard_data.py</code>
        </div>
      </div>
    );
  }

  // Per-store view: when storeFilter !== 'all' we route every chart-/KPI-
  // bound source through per_object_view[store] so the page reflects ONLY
  // that store. When 'all' we use the combined summary as before.
  const perObjectViewMap = (summary.per_object_view && typeof summary.per_object_view === 'object') ? summary.per_object_view : {};
  const filteredView = storeFilter !== 'all' && perObjectViewMap[storeFilter];
  const view = filteredView || summary;

  const overall = view.overall || summary.overall || {};
  const periodMeta = summary.period_meta && typeof summary.period_meta === 'object' ? summary.period_meta : {};
  const dataQuality = summary.data_quality && typeof summary.data_quality === 'object' ? summary.data_quality : null;
  const dqNull = dataQuality?.null_timestamp || null;
  const dqLegacy = dataQuality?.legacy_pre_2023 || null;
  const dqPerObject = asArray(dataQuality?.per_object);
  const byObject = asArray(summary.by_object);
  const byMonth = asArray(view.by_month || summary.by_month);
  const topCategoriesByProfitLifetime = asArray(view.top_categories_by_profit || summary.top_categories_by_profit).slice(0, 12);
  const topProductsByRevenueAllLifetime = asArray(view.top_products_by_revenue || summary.top_products_by_revenue);
  const topProductsByProfitAllLifetime = asArray(view.top_products_by_profit || summary.top_products_by_profit);
  const byCategoryByMonth = asArray(view.by_category_by_month || summary.by_category_by_month);
  const byProductByMonth = asArray(view.by_product_by_month || summary.by_product_by_month);
  const duplicatePolicy = summary.duplicate_policy && typeof summary.duplicate_policy === 'object' ? summary.duplicate_policy : {};
  const suspectedFiles = asArray(duplicatePolicy.suspected_files);
  const categoriesShown = asArray(summary.by_category).length;
  const productsShown = asArray(summary.by_product).length;

  // Product search — case-insensitive substring match on name / code / barcode.
  const matchesSearch = (p) => {
    if (!productSearch) return true;
    const q = productSearch.toLowerCase().trim();
    if (!q) return true;
    return ((p.product_name || '').toLowerCase().includes(q)
         || (p.product_code || '').toLowerCase().includes(q)
         || (p.barcode || '').toLowerCase().includes(q));
  };
  // NB: `topProductsByRevenue` / `topProductsByProfit` (filtered) are computed
  // below where `topProductsByRevenueAll` / `...ProfitAll` exist (period-aware).

  // Per-store-filterable analytics blocks
  const basket = view.basket_metrics || summary.basket_metrics || {};
  const paymentBreakdown = asArray(view.payment_breakdown || summary.payment_breakdown);
  const dowBreakdown = asArray(view.dow_breakdown || summary.dow_breakdown);
  const hourBreakdown = asArray(view.hour_breakdown || summary.hour_breakdown);
  const hourDowGrid = asArray(view.hour_dow_grid || summary.hour_dow_grid);
  const dailyTrend = asArray(view.daily_trend || summary.daily_trend);
  const calendarHeatmap = asArray(view.calendar_heatmap || summary.calendar_heatmap);
  const returnsVoids = asArray(view.returns_voids || summary.returns_voids);
  const discount = view.discount_totals || summary.discount_totals || {};
  // Concentration follows the filter (each store has its own product mix
  // → a global HHI is misleading when scoped). Other cross-cutting blocks
  // (spike alerts, prev-period compare, slow movers, top recent movers,
  // forecast) stay global for now.
  const concentration = view.concentration || summary.concentration || {};
  // Sample for the line chart: 0-50 every step, then 50-500 every 10th rank.
  const paretoFull = asArray(concentration.pareto_top500);
  const paretoChart = paretoFull.filter((p, i) => i < 50 || i % 10 === 0);
  const registers = asArray(summary.registers_per_object);
  const cashiers = asArray(summary.cashiers_per_object);
  const prevCompare = summary.prev_period_compare || {};
  const momCompare = prevCompare.mom || null;
  const yoyCompare = prevCompare.yoy || null;
  const spikeAlerts = asArray(summary.spike_alerts);
  const forecast = summary.forecast_next30 || {};
  const forecastRows = asArray(forecast.rows);
  const slowMovers = summary.slow_movers || {};
  const topRecentMovers = asArray(summary.top_recent_movers);

  // Sprint 2 — shifts / VAT / returns-by-product / discount-lift.
  // All read from per-store view first (filterable), fall back to combined.
  const shifts = asArray(view.shifts || summary.shifts);
  const shiftSummary = view.shift_summary || summary.shift_summary || {};
  const shiftAnomalies = asArray(view.shift_anomalies || summary.shift_anomalies);
  const vatTotals = view.vat_totals || summary.vat_totals || {};
  const vatByMonth = asArray(view.vat_by_month || summary.vat_by_month);
  const vatByCategory = asArray(view.vat_by_category || summary.vat_by_category).slice(0, 12);
  const returnsByProduct = asArray(view.returns_by_product || summary.returns_by_product);
  const returnsByCashier = asArray(view.returns_by_cashier || summary.returns_by_cashier);
  const returnsByMonth = asArray(view.returns_by_month || summary.returns_by_month);
  const discountByCategory = asArray(view.discount_by_category || summary.discount_by_category).slice(0, 15);
  const discountLiftSummary = view.discount_lift_summary || summary.discount_lift_summary || {};
  // Cross-store comparison — combined-view only (the comparison itself is cross-store).
  const crossStore = summary.cross_store_comparison || {};
  const crossStoreItems = (() => {
    if (crossStoreSortBy === 'margin_gap') return asArray(crossStore.top_by_margin_gap);
    if (crossStoreSortBy === 'combined_rev') return asArray(crossStore.top_by_combined_revenue);
    return asArray(crossStore.top_by_price_gap);
  })();

  // Dead stock — snapshot, follows store filter (period filter does NOT apply).
  const deadStock = view.dead_stock_summary || summary.dead_stock_summary || {};
  const deadStockBuckets = deadStock.buckets || {};
  const deadStockNeg = deadStock.negative_stock_alert || {};
  const deadStockBucketDef = {
    dead_365d_plus: { label: '🔴 365+ დღე', color: '#ef4444' },
    dead_180_365d:  { label: '🟠 180-365 დღე', color: '#f59e0b' },
    slow_90_180d:   { label: '🟡 90-180 დღე', color: '#facc15' },
    free_stock:     { label: '💸 უფასო (P_PRICE=0)', color: '#94a3b8' },
    negative_stock: { label: '⚠ უარყოფითი ნაშთი', color: '#f43f5e' },
  };
  const deadStockActiveItems = (() => {
    if (deadStockBucket === 'negative_stock') return asArray(deadStockNeg.top_items);
    return asArray((deadStockBuckets[deadStockBucket] || {}).top_items);
  })();
  const deadStockHasData = Boolean(deadStock.snapshot_date);

  // Filter helper — applies store filter to per-object lists
  const matchStore = (obj) => storeFilter === 'all' || obj === storeFilter;
  const filteredCashiers = cashiers.filter((c) => matchStore(c.object));
  const filteredRegisters = registers.filter((r) => matchStore(r.object));

  // ─── Period filter (client-side) ──────────────────────────────────────
  // Three data sources used in priority order:
  //   1. daily_trend  — last 365 days, day-grain (most accurate, has cogs)
  //   2. by_month     — lifetime, month-grain (works for old months too)
  //   3. fallback     — banner only, stats unavailable
  // Filter lexicons:
  //   'all', '7d', '30d', '90d', 'mtd', 'ytd', 'custom',
  //   'month:YYYY-MM' (specific month),
  //   'year:YYYY'    (specific calendar year).
  const KA_MONTH = ['იანვარი','თებერვალი','მარტი','აპრილი','მაისი','ივნისი','ივლისი','აგვისტო','სექტემბერი','ოქტომბერი','ნოემბერი','დეკემბერი'];

  // Distinct (year, month) pairs from data — sorted desc (newest first).
  const availableMonthsDesc = useMemo(() => {
    const set = new Set();
    byMonth.forEach((m) => { if (m.month) set.add(m.month); });
    return Array.from(set).sort().reverse();
  }, [byMonth]);
  const availableYearsDesc = useMemo(() => {
    const set = new Set();
    availableMonthsDesc.forEach((m) => set.add(m.slice(0, 4)));
    return Array.from(set).sort().reverse();
  }, [availableMonthsDesc]);

  const periodRange = useMemo(() => {
    if (periodPreset === 'all') return null;
    // Specific month: 'month:YYYY-MM'
    if (periodPreset.startsWith('month:')) {
      const ym = periodPreset.slice(6); // 'YYYY-MM'
      if (!/^\d{4}-\d{2}$/.test(ym)) return null;
      const [y, m] = ym.split('-').map(Number);
      const firstDay = `${ym}-01`;
      const lastDay = new Date(y, m, 0).toISOString().slice(0, 10); // last day of month
      return { from: firstDay, to: lastDay, label_ka: `${KA_MONTH[m - 1]} ${y}`, scope: 'month' };
    }
    // Specific year: 'year:YYYY'
    if (periodPreset.startsWith('year:')) {
      const y = periodPreset.slice(5);
      if (!/^\d{4}$/.test(y)) return null;
      return { from: `${y}-01-01`, to: `${y}-12-31`, label_ka: `${y} წელი`, scope: 'year' };
    }
    // Relative presets — anchored to last day in daily_trend.
    const days = dailyTrend.map((d) => d.day).filter(Boolean).sort();
    if (!days.length) return null;
    const lastIso = days[days.length - 1];
    const last = new Date(lastIso + 'T00:00:00');
    const fmt = (d) => d.toISOString().slice(0, 10);
    if (periodPreset === '7d') {
      const from = new Date(last); from.setDate(from.getDate() - 6);
      return { from: fmt(from), to: lastIso, label_ka: 'ბოლო 7 დღე', scope: 'relative' };
    }
    if (periodPreset === '30d') {
      const from = new Date(last); from.setDate(from.getDate() - 29);
      return { from: fmt(from), to: lastIso, label_ka: 'ბოლო 30 დღე', scope: 'relative' };
    }
    if (periodPreset === '90d') {
      const from = new Date(last); from.setDate(from.getDate() - 89);
      return { from: fmt(from), to: lastIso, label_ka: 'ბოლო 90 დღე', scope: 'relative' };
    }
    if (periodPreset === 'mtd') {
      const from = new Date(last.getFullYear(), last.getMonth(), 1);
      return { from: fmt(from), to: lastIso, label_ka: 'მიმდინარე თვე', scope: 'relative' };
    }
    if (periodPreset === 'ytd') {
      const from = new Date(last.getFullYear(), 0, 1);
      return { from: fmt(from), to: lastIso, label_ka: 'მიმდინარე წელი', scope: 'relative' };
    }
    if (periodPreset === 'custom' && customFrom && customTo) {
      return { from: customFrom, to: customTo, label_ka: `${customFrom} → ${customTo}`, scope: 'custom' };
    }
    return null;
  }, [periodPreset, customFrom, customTo, dailyTrend]);

  const dailyFiltered = useMemo(() => {
    if (!periodRange) return dailyTrend;
    return dailyTrend.filter((d) => d.day >= periodRange.from && d.day <= periodRange.to);
  }, [dailyTrend, periodRange]);

  // Period KPIs — prefer daily_trend (richer cost data); fall back to by_month
  // when picked period extends earlier than daily_trend's 365-day window.
  const periodKpis = useMemo(() => {
    if (!periodRange) return null;
    // Detect coverage: only use daily if requested-from >= daily-earliest.
    const dailyEarliest = dailyTrend.length > 0 ? dailyTrend[0].day : null;
    const fullyInDaily = dailyEarliest && periodRange.from >= dailyEarliest;
    if (fullyInDaily && dailyFiltered.length > 0) {
      const sumRev = dailyFiltered.reduce((s, d) => s + toNum(d.revenue_ge), 0);
      const sumCost = dailyFiltered.reduce((s, d) => s + toNum(d.cost_ge), 0);
      const sumLines = dailyFiltered.reduce((s, d) => s + toNum(d.lines), 0);
      const sumReceipts = dailyFiltered.reduce((s, d) => s + toNum(d.receipts), 0);
      return {
        revenue_ge: sumRev,
        cost_ge: sumCost,
        profit_ge: sumRev - sumCost,
        gross_margin_pct: sumRev > 0 ? (sumRev - sumCost) / sumRev * 100 : 0,
        lines: sumLines,
        receipts: sumReceipts,
        aov: sumReceipts > 0 ? sumRev / sumReceipts : 0,
        items_per_basket: sumReceipts > 0 ? sumLines / sumReceipts : 0,
        day_count: dailyFiltered.length,
        from: periodRange.from,
        to: periodRange.to,
        label_ka: periodRange.label_ka,
        source: 'daily',
      };
    }
    // Fallback: aggregate from by_month for the requested window. This kicks
    // in for months / years that extend before daily_trend's coverage.
    const fromMonth = periodRange.from.slice(0, 7);
    const toMonth = periodRange.to.slice(0, 7);
    const monthsInRange = byMonth.filter((m) => m.month >= fromMonth && m.month <= toMonth);
    if (monthsInRange.length === 0) return null;
    const sumRev = monthsInRange.reduce((s, m) => s + toNum(m.revenue_ge), 0);
    const sumCost = monthsInRange.reduce((s, m) => s + toNum(m.cost_ge), 0);
    const sumLines = monthsInRange.reduce((s, m) => s + toNum(m.row_count), 0);
    const sumReceipts = monthsInRange.reduce((s, m) => s + toNum(m.receipts), 0);
    return {
      revenue_ge: sumRev,
      cost_ge: sumCost,
      profit_ge: sumRev - sumCost,
      gross_margin_pct: sumRev > 0 ? (sumRev - sumCost) / sumRev * 100 : 0,
      lines: sumLines,
      receipts: sumReceipts,
      aov: sumReceipts > 0 ? sumRev / sumReceipts : 0,
      items_per_basket: sumReceipts > 0 ? sumLines / sumReceipts : 0,
      day_count: null,
      month_count: monthsInRange.length,
      from: periodRange.from,
      to: periodRange.to,
      label_ka: periodRange.label_ka,
      source: 'monthly',
    };
  }, [periodRange, dailyFiltered, dailyTrend, byMonth]);

  // Effective values for KPI tiles (period-aware override).
  const eff = {
    revenue_ge: periodKpis ? periodKpis.revenue_ge : toNum(overall.revenue_ge),
    cost_ge: periodKpis ? periodKpis.cost_ge : toNum(overall.cost_ge),
    profit_ge: periodKpis ? periodKpis.profit_ge : toNum(overall.profit_ge),
    gross_margin_pct: periodKpis ? periodKpis.gross_margin_pct : toNum(overall.gross_margin_pct),
    receipts: periodKpis ? periodKpis.receipts : toNum(basket.receipts),
    aov: periodKpis ? periodKpis.aov : toNum(basket.aov),
    items_per_basket: periodKpis ? periodKpis.items_per_basket : toNum(basket.items_per_basket),
    lines: periodKpis ? periodKpis.lines : toNum(overall.row_count),
  };

  // Filtered monthly + daily for chart display.
  const byMonthFiltered = useMemo(() => {
    if (!periodRange) return byMonth;
    return byMonth.filter((m) => {
      if (!m.month) return false;
      // m.month is YYYY-MM. Compare against from/to as YYYY-MM.
      const mPrefix = m.month;
      return mPrefix >= periodRange.from.slice(0, 7) && mPrefix <= periodRange.to.slice(0, 7);
    });
  }, [byMonth, periodRange]);

  // Period-scoped top categories (sum by_category_by_month rows in range).
  const topCategoriesByProfit = useMemo(() => {
    if (!periodRange) return topCategoriesByProfitLifetime;
    const fromM = periodRange.from.slice(0, 7);
    const toM = periodRange.to.slice(0, 7);
    const acc = {};
    for (const r of byCategoryByMonth) {
      if (!r.month || r.month < fromM || r.month > toM) continue;
      const k = r.category || '(უცნობი)';
      const cur = acc[k] || { category: k, row_count: 0, total_quantity: 0, revenue_ge: 0, cost_ge: 0, profit_ge: 0 };
      cur.row_count += toNum(r.row_count);
      cur.total_quantity += toNum(r.total_quantity);
      cur.revenue_ge += toNum(r.revenue_ge);
      cur.cost_ge += toNum(r.cost_ge);
      cur.profit_ge += toNum(r.profit_ge);
      acc[k] = cur;
    }
    const out = Object.values(acc);
    out.forEach((r) => { r.gross_margin_pct = r.revenue_ge > 0 ? (r.profit_ge / r.revenue_ge) * 100 : 0; });
    return out.sort((a, b) => b.profit_ge - a.profit_ge).slice(0, 12);
  }, [periodRange, byCategoryByMonth, topCategoriesByProfitLifetime]);

  // Period-scoped top products (sum by_product_by_month rows in range).
  const topProductsByRevenueAll = useMemo(() => {
    if (!periodRange) return topProductsByRevenueAllLifetime;
    const fromM = periodRange.from.slice(0, 7);
    const toM = periodRange.to.slice(0, 7);
    const acc = {};
    for (const r of byProductByMonth) {
      if (!r.month || r.month < fromM || r.month > toM) continue;
      const k = r.barcode || r.product_code || r.product_name;
      if (!k) continue;
      const cur = acc[k] || {
        product_code: r.product_code, barcode: r.barcode,
        product_name: r.product_name, category: r.category,
        row_count: 0, qty_sold: 0, revenue_ge: 0, cost_ge: 0, profit_ge: 0,
      };
      cur.row_count += toNum(r.row_count);
      cur.qty_sold += toNum(r.qty_sold);
      cur.revenue_ge += toNum(r.revenue_ge);
      cur.cost_ge += toNum(r.cost_ge);
      cur.profit_ge += toNum(r.profit_ge);
      acc[k] = cur;
    }
    const out = Object.values(acc);
    out.forEach((r) => { r.gross_margin_pct = r.revenue_ge > 0 ? (r.profit_ge / r.revenue_ge) * 100 : 0; });
    return out.sort((a, b) => b.revenue_ge - a.revenue_ge);
  }, [periodRange, byProductByMonth, topProductsByRevenueAllLifetime]);

  const topProductsByProfitAll = useMemo(() => {
    if (!periodRange) return topProductsByProfitAllLifetime;
    return [...topProductsByRevenueAll].sort((a, b) => b.profit_ge - a.profit_ge);
  }, [periodRange, topProductsByRevenueAll, topProductsByProfitAllLifetime]);

  // Search-filtered + sliced top product lists (consumed by the UI tables).
  const topProductsByRevenue = topProductsByRevenueAll.filter(matchesSearch).slice(0, topProductsLimit);
  const topProductsByProfit = topProductsByProfitAll.filter(matchesSearch).slice(0, topProductsLimit);

  // Period-scoped shifts (filter by shift_start within range).
  const shiftsFiltered = useMemo(() => {
    if (!periodRange) return null;
    return shifts.filter((s) => {
      if (!s.shift_start) return false;
      const day = s.shift_start.slice(0, 10);
      return day >= periodRange.from && day <= periodRange.to;
    });
  }, [periodRange, shifts]);

  // Period-scoped VAT totals (sum vat_by_month in range).
  const vatTotalsPeriod = useMemo(() => {
    if (!periodRange) return null;
    const fromM = periodRange.from.slice(0, 7);
    const toM = periodRange.to.slice(0, 7);
    const filtered = vatByMonth.filter((m) => m.month >= fromM && m.month <= toM);
    if (!filtered.length) return null;
    const sumVat = filtered.reduce((s, m) => s + toNum(m.vat_collected_ge), 0);
    const sumRev = filtered.reduce((s, m) => s + toNum(m.revenue_ge), 0);
    return {
      vat_collected_ge: sumVat,
      revenue_ge: sumRev,
      effective_rate_pct: sumRev > 0 ? sumVat / sumRev * 100 : 0,
      months: filtered.length,
    };
  }, [periodRange, vatByMonth]);

  // Period-scoped returns total (sum returns_by_month).
  const returnsTotalsPeriod = useMemo(() => {
    if (!periodRange) return null;
    const fromM = periodRange.from.slice(0, 7);
    const toM = periodRange.to.slice(0, 7);
    const filtered = returnsByMonth.filter((m) => m.month >= fromM && m.month <= toM);
    if (!filtered.length) return null;
    return {
      lines: filtered.reduce((s, m) => s + toNum(m.lines), 0),
      receipts: filtered.reduce((s, m) => s + toNum(m.receipts), 0),
      revenue_ge: filtered.reduce((s, m) => s + toNum(m.revenue_ge), 0),
      quantity: filtered.reduce((s, m) => s + toNum(m.quantity), 0),
      months: filtered.length,
    };
  }, [periodRange, returnsByMonth]);

  const hasRows = toNum(overall.row_count) > 0 || byObject.length > 0 || byMonth.length > 0;
  const periodLabel = periodMeta.label_ka || (periodMeta.applied ? 'არჩეული პერიოდი' : 'ყველა პერიოდი');
  const periodCaveat = responseMeta?.period_caveat_ka || '';

  // Daily trend with 7-day moving average for line smoothness
  const dailyWithMA = useMemo(() => {
    const src = dailyFiltered;
    const out = [];
    for (let i = 0; i < src.length; i++) {
      const win = src.slice(Math.max(0, i - 6), i + 1);
      const ma = win.reduce((s, d) => s + toNum(d.revenue_ge), 0) / win.length;
      out.push({ ...src[i], ma7: Math.round(ma), forecast: null });
    }
    // Append 30-day forecast — only when no period filter is active.
    if (!periodRange) {
      forecastRows.forEach((f) => {
        out.push({ day: f.day, revenue_ge: null, ma7: null, forecast: toNum(f.revenue_ge) });
      });
    }
    return out;
  }, [dailyFiltered, forecastRows, periodRange]);

  // Delta helper for KPI ▲▼ chip
  const renderDelta = (delta, deltaPct) => {
    if (delta === undefined || delta === null) return null;
    const positive = delta >= 0;
    return (
      <span style={{
        marginLeft: 6, fontSize: 11, padding: '1px 6px', borderRadius: 4,
        background: positive ? '#064e3b' : '#7f1d1d',
        color: positive ? '#6ee7b7' : '#fca5a5',
      }}>
        {positive ? '▲' : '▼'} {fmtPct(Math.abs(deltaPct))}
      </span>
    );
  };

  // Recent monthly trend chart — period-filtered when active, else last 24 months.
  const monthlyChart = useMemo(() => {
    const src = periodRange ? byMonthFiltered : byMonth.slice(-24);
    return src.map((m) => ({
      month: m.month,
      revenue: toNum(m.revenue_ge),
      profit: toNum(m.profit_ge),
      margin: toNum(m.gross_margin_pct),
    }));
  }, [byMonth, byMonthFiltered, periodRange]);

  if (!hasRows) {
    return (
      <div className="cashflow-page pnl-empty">
        <div className="kpi-card" style={{ maxWidth: 560, margin: '48px auto', textAlign: 'center' }}>
          <div className="kpi-label">
            {periodMeta.applied ? 'არჩეულ პერიოდში Retail Sales არ მოიძებნა' : 'Retail Sales წყარო ცარიელია'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="cashflow-page">
      <div className="tab-hero">
        <span className="tab-hero-title">🛒 Retail Sales — full analytics</span>
        <span className="tab-hero-desc">
          {summary.notes_ka || 'დვაბზუ + ოზურგეთი retail sales — revenue / cost / profit / margin / basket / payment / time-of-day.'}
        </span>
        <ExportButton
          filename={`RetailSales_${new Date().toISOString().slice(0, 10)}.xlsx`}
          sheets={[
            { name: 'თვიური', rows: byMonth.map((m) => ({ თვე: m.month || '', შემოსავალი: toNum(m.revenue_ge), მოგება: toNum(m.profit_ge), margin_pct: toNum(m.gross_margin_pct) })) },
            { name: 'TOP Products', rows: topProductsByRevenue.map((p) => ({ პროდუქტი: p.product_name || '', შემოსავალი: toNum(p.revenue_ge), მოგება: toNum(p.profit_ge) })) },
            { name: 'მოლარეები', rows: cashiers.map((c) => ({ მაღაზია: c.object, user_id: c.user_id, ჩეკი: c.receipts, შემოსავალი: toNum(c.revenue), AOV: toNum(c.aov) })) },
            { name: 'საათობრივი', rows: hourBreakdown.map((h) => ({ საათი: h.hour, ხაზი: h.lines, ჩეკი: h.receipts, შემოსავალი: toNum(h.revenue_ge) })) },
          ]}
        />
      </div>

      {/* ─── Filters bar ─── */}
      <div className="controls controls-filters" style={{ marginTop: 12, marginBottom: 12, display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <span className="badge muted">პერიოდი: {periodKpis ? periodKpis.label_ka : periodLabel}<InfoTip text={TIPS.daily} /></span>
        <span className="badge muted">თარიღი: {renderDateRange(overall.date_range)}</span>
        <span style={{ marginLeft: 12, fontSize: 13, color: '#94a3b8' }}>მაღაზია:</span>
        <select
          value={storeFilter}
          onChange={(e) => setStoreFilter(e.target.value)}
          style={{ background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 6, padding: '4px 8px', fontSize: 13 }}
        >
          <option value="all">ყველა</option>
          {byObject.map((o) => (<option key={o.object} value={o.object}>{o.object}</option>))}
        </select>
        <span style={{ marginLeft: 12, fontSize: 13, color: '#94a3b8' }}>პერიოდი:</span>
        <select
          value={periodPreset}
          onChange={(e) => setPeriodPreset(e.target.value)}
          style={{ background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 6, padding: '4px 8px', fontSize: 13, minWidth: 200 }}
        >
          <option value="all">ყველა დრო</option>
          <optgroup label="ფარდობითი">
            <option value="7d">ბოლო 7 დღე</option>
            <option value="30d">ბოლო 30 დღე</option>
            <option value="90d">ბოლო 90 დღე</option>
            <option value="mtd">მიმდინარე თვე</option>
            <option value="ytd">მიმდინარე წელი</option>
          </optgroup>
          <optgroup label="კონკრეტული თვე">
            {availableMonthsDesc.map((ym) => {
              const [y, m] = ym.split('-');
              return <option key={`m-${ym}`} value={`month:${ym}`}>{`${y} — ${KA_MONTH[Number(m) - 1]}`}</option>;
            })}
          </optgroup>
          <optgroup label="კონკრეტული წელი">
            {availableYearsDesc.map((y) => (
              <option key={`y-${y}`} value={`year:${y}`}>{`${y} წელი`}</option>
            ))}
          </optgroup>
          <optgroup label="მორგებული">
            <option value="custom">მორგებული თარიღების შუალედი</option>
          </optgroup>
        </select>
        {periodPreset === 'custom' && (
          <>
            <input
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              style={{ background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 6, padding: '3px 6px', fontSize: 12 }}
            />
            <span style={{ color: '#94a3b8' }}>→</span>
            <input
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              style={{ background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 6, padding: '3px 6px', fontSize: 12 }}
            />
          </>
        )}
        {periodKpis && (
          <span style={{
            padding: '3px 10px', borderRadius: 4, fontSize: 12,
            background: '#334155', color: '#cbd5e1', border: '1px solid #475569',
          }}>
            <strong>{periodKpis.label_ka}</strong> ·{' '}
            {periodKpis.source === 'daily' ? `${periodKpis.day_count} დღე` : `${periodKpis.month_count} თვე`} ·{' '}
            {periodKpis.from} → {periodKpis.to}
          </span>
        )}
        {filteredView && (
          <span style={{
            padding: '3px 10px', borderRadius: 4, fontSize: 12,
            background: STORE_COLOR[storeFilter] ? `${STORE_COLOR[storeFilter]}30` : '#334155',
            color: STORE_COLOR[storeFilter] || '#cbd5e1',
            border: `1px solid ${STORE_COLOR[storeFilter] || '#475569'}`,
          }}>
            მაღაზია: <strong>{storeFilter}</strong>
          </span>
        )}
      </div>

      {periodKpis && (
        <div className="trust-banner-sub" style={{ background: '#1e293b', borderLeft: '3px solid #3b82f6', padding: '8px 12px', marginBottom: 8, fontSize: 12 }}>
          ⓘ პერიოდი <strong>{periodKpis.label_ka}</strong> ვრცელდება: KPI ბარათები, თვიური / დღიური ცემპი, კალენდარი, TOP კატეგორია, TOP პროდუქტი, ცვლები, დღგ.
          ლიფტაიმისაა: საათობრივი / დღის / Pareto / ფასდაკლების კატეგორიები / დაბრუნებული პროდუქტები / დღგ-ის გარეშე ხაზი.
        </div>
      )}

      {periodCaveat && (
        <div className="trust-banner-sub trust-banner-sub--warn">{periodCaveat}</div>
      )}

      <div className="local-pay-banner imported-products-reference-note" role="note">
        Reference-only წყაროა Megaplus DB-ის რეტეილ გაყიდვებიდან. ეს ბლოკი არ ერთვება supplier debt/AP,
        RS truth totals ან bank reconciliation ჯამებში; გამოიყენე როგორც დამატებითი ანალიზის ჭრილი.
      </div>

      {/* ─── Data quality warning ─── */}
      {(dqNull?.row_count > 0 || dqLegacy?.row_count > 0) && (
        <div className="chart-card" style={{ borderLeft: '3px solid #f59e0b', background: '#1c1917' }}>
          <h3 style={{ color: '#fbbf24' }}>⚠️ მონაცემთა ხარისხის შენიშვნა</h3>
          <p className="chart-desc" style={{ marginBottom: 10 }}>
            ქვემოთ ხაზები <strong>ჩათვლილია</strong> ზემოთ ჯამში (შემოსავალი / რაოდენობა / მოგება),
            მაგრამ შეიძლება <strong>ცხადად არ ჩანდნენ</strong> თვიური / დღიური ჭრილის გრაფიკში.
          </p>
          {dqNull?.row_count > 0 && (
            <div className="kpi-sub" style={{ marginBottom: 6 }}>
              <strong style={{ color: '#fbbf24' }}>თარიღი არ აქვს:</strong>{' '}
              {fmtInt(dqNull.row_count)} ხაზი · {fmtMoney(dqNull.revenue_ge)} · რაოდ. {fmtNum(dqNull.quantity)}
              <InfoTip text={dqNull.note_ka} />
            </div>
          )}
          {dqLegacy?.row_count > 0 && (
            <div className="kpi-sub" style={{ marginBottom: 6 }}>
              <strong style={{ color: '#fbbf24' }}>2023-01-01-მდე:</strong>{' '}
              {fmtInt(dqLegacy.row_count)} ხაზი · {fmtMoney(dqLegacy.revenue_ge)} · რაოდ. {fmtNum(dqLegacy.quantity)} (სავარაუდოდ DB-ის ისტორიული სატესტო)
              <InfoTip text={dqLegacy.note_ka} />
            </div>
          )}
          {dqPerObject.length > 0 && (
            <details style={{ marginTop: 10 }}>
              <summary style={{ cursor: 'pointer', fontSize: 12, color: '#94a3b8' }}>per-მაღაზია ჭრილი</summary>
              <table style={{ marginTop: 8, fontSize: 12, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '4px 8px' }}>მაღაზია</th>
                    <th style={{ textAlign: 'right', padding: '4px 8px' }}>NULL თარიღი</th>
                    <th style={{ textAlign: 'right', padding: '4px 8px' }}>NULL შემოს.</th>
                    <th style={{ textAlign: 'right', padding: '4px 8px' }}>2009 ხაზი</th>
                    <th style={{ textAlign: 'right', padding: '4px 8px' }}>2009 შემოს.</th>
                  </tr>
                </thead>
                <tbody>
                  {dqPerObject.map((r) => (
                    <tr key={`dq-${r.object || 'na'}`}>
                      <td style={{ padding: '4px 8px' }}>{r.object || 'უცნობი'}</td>
                      <td style={{ padding: '4px 8px', textAlign: 'right' }}>{fmtInt(r.null_timestamp_count)}</td>
                      <td style={{ padding: '4px 8px', textAlign: 'right' }}>{fmtMoney(r.null_timestamp_revenue)}</td>
                      <td style={{ padding: '4px 8px', textAlign: 'right' }}>{fmtInt(r.legacy_pre_2023_count)}</td>
                      <td style={{ padding: '4px 8px', textAlign: 'right' }}>{fmtMoney(r.legacy_pre_2023_revenue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
        </div>
      )}

      {/* ─── Prev-period compare (MoM + YoY) ─── */}
      {(momCompare || yoyCompare) && (
        <div className="chart-card">
          <h3>წინა პერიოდთან შედარება<InfoTip text="MoM = ბოლო თვე vs წინა თვე. YoY = ბოლო თვე vs იმავე თვე გასულ წელს. ბოლო თვე შეიძლება არასრული იყოს — შესადარისობა მიახლოებითია." /></h3>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 8 }}>
            {momCompare && (
              <div style={{ flex: '1 1 280px', minWidth: 280, background: '#1e293b', padding: 12, borderRadius: 6 }}>
                <div className="kpi-sub" style={{ marginBottom: 4 }}>
                  MoM · {momCompare.current_month} vs {momCompare.prev_month}
                </div>
                <div style={{ fontSize: 18, fontWeight: 600 }}>
                  {fmtMoney(momCompare.current_revenue)}
                  {renderDelta(momCompare.delta_revenue, momCompare.delta_revenue_pct)}
                </div>
                <div className="kpi-sub" style={{ marginTop: 4 }}>
                  წინა: {fmtMoney(momCompare.prev_revenue)} ·{' '}
                  მოგება {fmtMoney(momCompare.current_profit)} ({momCompare.delta_profit >= 0 ? '+' : ''}{fmtMoney(momCompare.delta_profit)}) ·{' '}
                  მარჟა {fmtPct(momCompare.current_margin_pct)}
                </div>
              </div>
            )}
            {yoyCompare && (
              <div style={{ flex: '1 1 280px', minWidth: 280, background: '#1e293b', padding: 12, borderRadius: 6 }}>
                <div className="kpi-sub" style={{ marginBottom: 4 }}>
                  YoY · {yoyCompare.current_month} vs {yoyCompare.yoy_month}
                </div>
                <div style={{ fontSize: 18, fontWeight: 600 }}>
                  {fmtMoney(yoyCompare.current_revenue)}
                  {renderDelta(yoyCompare.delta_revenue, yoyCompare.delta_revenue_pct)}
                </div>
                <div className="kpi-sub" style={{ marginTop: 4 }}>
                  გასული წლის: {fmtMoney(yoyCompare.yoy_revenue)} ·{' '}
                  მოგების ცვლა {yoyCompare.delta_profit >= 0 ? '+' : ''}{fmtMoney(yoyCompare.delta_profit)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Spike alerts ─── */}
      {spikeAlerts.length > 0 && (
        <div className="chart-card" style={{ borderLeft: '3px solid #a855f7' }}>
          <h3 style={{ color: '#c4b5fd' }}>🚨 ანომალიის ალერტი ({spikeAlerts.length})<InfoTip text="თვიური შემოსავალი > 2σ საშუალოზე ან ნაკლები. z-score-ის მიხედვით დალაგებული. 2009-სატესტო თვე გამოტოვებულია." /></h3>
          <p className="chart-desc">თვის შემოსავალი საშუალოდან ცაფფი მაღალი / დაბალი (z-score ≥ 2σ).</p>
          <table style={{ width: '100%', fontSize: 13, marginTop: 8 }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>თვე</th>
                <th style={{ textAlign: 'left' }}>ტიპი</th>
                <th style={{ textAlign: 'right' }}>შემოსავალი</th>
                <th style={{ textAlign: 'right' }}>საშ. შემოს.</th>
                <th style={{ textAlign: 'right' }}>z-score</th>
                <th style={{ textAlign: 'left' }}>აღწერა</th>
              </tr>
            </thead>
            <tbody>
              {spikeAlerts.map((s) => (
                <tr key={`spike-${s.month}`}>
                  <td>{s.month}</td>
                  <td>
                    <span style={{
                      padding: '2px 6px', borderRadius: 4, fontSize: 11,
                      background: s.kind === 'spike' ? '#064e3b' : '#7f1d1d',
                      color: s.kind === 'spike' ? '#6ee7b7' : '#fca5a5',
                    }}>{s.kind === 'spike' ? '▲ ცემპი' : '▼ ვარდნა'}</span>
                  </td>
                  <td style={{ textAlign: 'right' }}>{fmtMoney(s.revenue_ge)}</td>
                  <td style={{ textAlign: 'right' }}>{fmtMoney(s.mean_revenue_ge)}</td>
                  <td style={{ textAlign: 'right' }}>{s.z_score >= 0 ? '+' : ''}{fmtNum(s.z_score)}σ</td>
                  <td style={{ fontSize: 12, color: '#94a3b8' }}>{s.message_ka}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ─── KPI grid (12 cards) ─── */}
      <div className="kpi-grid retail-sales-kpi-grid">
        <div className="kpi-card kpi-card--accent">
          <div className="kpi-label">სულ შემოსავალი<InfoTip text={TIPS.revenue} /></div>
          <div className="kpi-value amount-positive">{fmtMoney(eff.revenue_ge)}</div>
          <div className="kpi-sub">{
            periodKpis
              ? (periodKpis.source === 'daily'
                  ? `${periodKpis.day_count} დღე`
                  : `${periodKpis.month_count} თვე`)
              : 'POS-რეგისტრირებული'
          }</div>
        </div>
        <div className="kpi-card kpi-card--warn">
          <div className="kpi-label">სულ თვითღირებულება<InfoTip text={TIPS.cost} /></div>
          <div className="kpi-value amount-negative">{fmtMoney(eff.cost_ge)}</div>
          <div className="kpi-sub">ფაქტურიდან გათვლილი</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">სულ მოგება<InfoTip text={TIPS.profit} /></div>
          <div className={`kpi-value ${renderMoneyClass(eff.profit_ge)}`}>{fmtMoney(eff.profit_ge)}</div>
          <div className="kpi-sub">შემოსავალი − imputed cost</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Gross Margin<InfoTip text={TIPS.margin} /></div>
          <div className="kpi-value amount-neutral">{fmtPct(eff.gross_margin_pct)}</div>
          <div className="kpi-sub">{fmtInt(overall.distinct_object_count)} ობიექტი</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">ჩეკები<InfoTip text={TIPS.receipts} /></div>
          <div className="kpi-value amount-neutral">{fmtInt(eff.receipts)}</div>
          <div className="kpi-sub">უნიკალური ORD_N</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">საშუალო ჩეკი (AOV)<InfoTip text={TIPS.aov} /></div>
          <div className="kpi-value amount-neutral">{fmtMoney2(eff.aov)}</div>
          <div className="kpi-sub">ერთ ჩეკზე საშ. თანხა</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">პროდუქტი / ჩეკი<InfoTip text={TIPS.itemsPerBasket} /></div>
          <div className="kpi-value amount-neutral">{fmtNum(eff.items_per_basket)}</div>
          <div className="kpi-sub">საშ. ხაზი ერთ ჩეკში</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">ხაზები / რაოდენობა<InfoTip text={TIPS.rows} /></div>
          <div className="kpi-value amount-neutral">{fmtInt(eff.lines)}</div>
          <div className="kpi-sub">{periodKpis ? '(მხოლოდ პერიოდში)' : `${fmtNum(overall.total_quantity)} ცალი / კგ`}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">ფასდაკლება ჯამში<InfoTip text={TIPS.markdown} /></div>
          <div className="kpi-value amount-neutral">{fmtMoney(discount.markdown_total_ge)}</div>
          <div className="kpi-sub">{fmtPct(discount.avg_markdown_pct)} საშ. სკიდკა</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">დაბრუნება / გაუქმება<InfoTip text={TIPS.returns} /></div>
          <div className="kpi-value amount-neutral">
            {fmtInt(returnsVoids.reduce((s, r) => s + toNum(r.lines), 0))}
          </div>
          <div className="kpi-sub">
            {fmtMoney(returnsVoids.reduce((s, r) => s + toNum(r.revenue_ge), 0))} ჯამი
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">კატეგორია / პროდუქტი</div>
          <div className="kpi-value amount-neutral">
            {fmtInt(overall.distinct_category_count)} / {fmtInt(overall.distinct_product_count)}
          </div>
          <div className="kpi-sub">{renderDateRange(overall.date_range)}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">80/20 პროდუქტი<InfoTip text={TIPS.pareto} /></div>
          <div className="kpi-value amount-neutral">{fmtInt(concentration.products_for_80pct_revenue)}</div>
          <div className="kpi-sub">პროდუქტი = 80% შემოს. (HHI {fmtNum(concentration.hhi)} {concentration.hhi_class})</div>
        </div>
      </div>

      {/* ─── Monthly trend chart ─── */}
      {monthlyChart.length > 0 && (
        <div className="chart-card">
          <h3>თვიური ტრენდი (ბოლო 24 თვე)<InfoTip text="თვიური შემოსავალი + მოგება + მარჟა %. წითელი ხაზი მარჟა-ს % აჩვენებს მარჯვენა ღერძზე." /></h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={monthlyChart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="month" stroke="#94a3b8" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="left" stroke="#94a3b8" tick={{ fontSize: 11 }} tickFormatter={(v) => fmtInt(v)} />
              <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                contentStyle={{ background: '#0f172a', border: '1px solid #334155' }}
                formatter={(v, name) => name === 'მარჟა %' ? `${v}%` : fmtMoney(v)}
              />
              <Legend />
              <Line yAxisId="left" type="monotone" dataKey="revenue" stroke="#3b82f6" name="შემოსავალი" strokeWidth={2} dot={false} />
              <Line yAxisId="left" type="monotone" dataKey="profit" stroke="#10b981" name="მოგება" strokeWidth={2} dot={false} />
              <Line yAxisId="right" type="monotone" dataKey="margin" stroke="#f59e0b" name="მარჟა %" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ─── Daily trend (last 365 days) + 30-day forecast ─── */}
      {dailyWithMA.length > 0 && (
        <div className="chart-card">
          <h3>დღიური ტრენდი — ბოლო 365 დღე + 30-დღიანი პროგნოზი<InfoTip text="ცისფერი ფონი = ფაქტი. ნარინჯისფერი = 7-დღიანი მძლავრი საშუალო. წყვეტილი მწვანე = trailing 30-დღის MA-ით პროგნოზი მომდევნო 30 დღისთვის." /></h3>
          {forecast.next_30d_total_revenue_ge > 0 && (
            <p className="chart-desc">
              30-დღიანი პროგნოზი: <strong>{fmtMoney(forecast.next_30d_total_revenue_ge)}</strong>{' '}
              ჯამში · დღიური საშ. <strong>{fmtMoney(forecast.next_30d_avg_daily_revenue_ge)}</strong>{' '}
              (ბოლო 30 დღის საშუალოს ვინარჩუნებთ — სეზონური ცვლილება არ არის გათვალისწინებული).
            </p>
          )}
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={dailyWithMA}>
              <defs>
                <linearGradient id="grRev" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="day" stroke="#94a3b8" tick={{ fontSize: 10 }} interval={Math.floor(dailyWithMA.length / 12)} />
              <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} tickFormatter={fmtInt} />
              <Tooltip
                contentStyle={{ background: '#0f172a', border: '1px solid #334155' }}
                formatter={(v) => v == null ? '—' : fmtMoney(v)}
              />
              <Legend />
              <Area type="monotone" dataKey="revenue_ge" stroke="#3b82f6" fillOpacity={1} fill="url(#grRev)" name="ფაქტი" connectNulls={false} />
              <Line type="monotone" dataKey="ma7" stroke="#f59e0b" strokeWidth={2} dot={false} name="7-დღიანი MA" connectNulls={false} />
              <Line type="monotone" dataKey="forecast" stroke="#10b981" strokeWidth={2} strokeDasharray="5 5" dot={false} name="30-დღ. პროგნოზი" connectNulls={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ─── Hour-of-day + Day-of-week ─── */}
      <div className="retail-sales-grid-2">
        {hourBreakdown.length > 0 && (
          <div className="chart-card">
            <h3>საათობრივი ცემპი<InfoTip text={TIPS.hour} /></h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={hourBreakdown}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="hour" stroke="#94a3b8" tick={{ fontSize: 11 }} tickFormatter={(h) => `${String(h).padStart(2, '0')}h`} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} tickFormatter={fmtInt} />
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155' }}
                  formatter={(v) => fmtMoney(v)}
                  labelFormatter={(h) => `${String(h).padStart(2, '0')}:00`}
                />
                <Bar dataKey="revenue_ge" fill="#3b82f6" name="შემოსავალი" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        {dowBreakdown.length > 0 && (
          <div className="chart-card">
            <h3>კვირის დღე<InfoTip text={TIPS.dow} /></h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={dowBreakdown}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="label_ka" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} tickFormatter={fmtInt} />
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155' }}
                  formatter={(v) => fmtMoney(v)}
                />
                <Bar dataKey="revenue_ge" fill="#10b981" name="შემოსავალი" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* ─── Hour × Day-of-week heatmap (combined 7×24 grid) ─── */}
      {hourDowGrid.length > 0 && (
        <div className="chart-card">
          <h3>საათი × კვირის-დღე რუკა<InfoTip text="168 უჯრედი (7 დღე × 24 საათი). წითელი = ყველაზე დაკავებული, მუქი = ცარიელი. სამუშაო გრაფიკის გადაწყობისთვის გამოგადგება — ცხადად ჩანს, რომელ კომბინაციაში ხდება ყველაზე მეტი გაყიდვა." /></h3>
          <p className="chart-desc">ცხადყოფს, კვირის რომელ დღეს და რომელ საათში მაქსიმუმი გაყიდვა. გადაატანე მაუსი უჯრაზე — დეტალი.</p>
          <HourDowHeatmap grid={hourDowGrid} />
        </div>
      )}

      {/* ─── Category mix over time (top 6 categories monthly trend) ─── */}
      {byCategoryByMonth.length > 0 && (() => {
        // Build monthly buckets keyed by (month, category) → revenue. Pick
        // top 6 categories by total revenue and pivot to a chart-friendly shape.
        const catTotals = new Map();
        byCategoryByMonth.forEach((cm) => {
          const k = cm.category || '(უცნობი)';
          catTotals.set(k, (catTotals.get(k) || 0) + toNum(cm.revenue_ge));
        });
        const topCats = Array.from(catTotals.entries()).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k]) => k);
        const months = Array.from(new Set(byCategoryByMonth.map((c) => c.month))).filter(Boolean).sort();
        const recentMonths = months.slice(-24);
        const pivot = recentMonths.map((m) => {
          const row = { month: m };
          topCats.forEach((c) => { row[c] = 0; });
          byCategoryByMonth.forEach((cm) => {
            if (cm.month === m && topCats.includes(cm.category)) {
              row[cm.category] = (row[cm.category] || 0) + toNum(cm.revenue_ge);
            }
          });
          return row;
        });
        return (
          <div className="chart-card">
            <h3>კატეგორიები დროში — ბოლო 24 თვე<InfoTip text="ტოპ 6 კატეგორიის თვიური შემოსავალი. ცხადყოფს — რომელი კატეგორია იწევს, რომელი ეცემა. იგივე კატეგორია სხვადასხვა ფერით." /></h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={pivot}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="month" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} tickFormatter={fmtInt} />
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155' }}
                  formatter={(v) => fmtMoney(v)}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {topCats.map((c, i) => (
                  <Line key={c} type="monotone" dataKey={c} stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2} dot={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        );
      })()}

      {/* ─── Calendar heatmap ─── */}
      {calendarHeatmap.length > 0 && (
        <div className="chart-card">
          <h3>კალენდრის თერმული რუკა {periodKpis ? `— ${periodKpis.label_ka}` : '— ბოლო 365 დღე'}<InfoTip text={TIPS.calendar} /></h3>
          <CalendarHeatmap days={periodRange ? calendarHeatmap.filter((d) => d.day >= periodRange.from && d.day <= periodRange.to) : calendarHeatmap} />
        </div>
      )}

      {/* ─── Payment + Store mix ─── */}
      <div className="retail-sales-grid-2">
        {paymentBreakdown.length > 0 && (
          <div className="chart-card">
            <h3>გადახდის ფორმა<InfoTip text={TIPS.payment} /></h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={paymentBreakdown}
                  dataKey="revenue_ge"
                  nameKey="label_ka"
                  outerRadius={80}
                  label={(entry) => `${entry.label_ka}: ${fmtPct(entry.share_pct)}`}
                >
                  {paymentBreakdown.map((p, i) => (
                    <Cell key={p.label_ka} fill={i === 0 ? '#10b981' : '#3b82f6'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155' }} formatter={(v) => fmtMoney(v)} />
              </PieChart>
            </ResponsiveContainer>
            <table style={{ width: '100%', fontSize: 12, marginTop: 8 }}>
              <thead><tr><th style={{ textAlign: 'left' }}>ფორმა</th><th style={{ textAlign: 'right' }}>ჩეკები</th><th style={{ textAlign: 'right' }}>შემოს.</th><th style={{ textAlign: 'right' }}>%</th></tr></thead>
              <tbody>
                {paymentBreakdown.map((p) => (
                  <tr key={p.label_ka}>
                    <td>{p.label_ka}</td>
                    <td style={{ textAlign: 'right' }}>{fmtInt(p.receipts)}</td>
                    <td style={{ textAlign: 'right' }}>{fmtMoney(p.revenue_ge)}</td>
                    <td style={{ textAlign: 'right' }}>{fmtPct(p.share_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {byObject.length > 0 && (
          <div className="chart-card">
            <h3>მაღაზიის mix<InfoTip text="მაღაზიების შემოსავალი ერთ ჩარდახში" /></h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={byObject}
                  dataKey="revenue_ge"
                  nameKey="object"
                  outerRadius={80}
                  label={(entry) => `${entry.object}: ${fmtMoney(entry.revenue_ge)}`}
                >
                  {byObject.map((o) => (
                    <Cell key={o.object} fill={STORE_COLOR[o.object] || '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155' }} formatter={(v) => fmtMoney(v)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* ─── Pareto + concentration ─── */}
      {paretoChart.length > 0 && (
        <div className="chart-card">
          <h3>Pareto — შემოსავლის კუმულატიური წილი<InfoTip text={TIPS.pareto} /></h3>
          <p className="chart-desc">
            HHI = <strong>{fmtNum(concentration.hhi)}</strong> ({concentration.hhi_class}).
            ჯამური {fmtInt(concentration.total_products_in_revenue)} პროდუქტიდან:{' '}
            <strong>{fmtInt(concentration.products_for_50pct_revenue)}</strong> = 50% შემოს. ·{' '}
            <strong>{fmtInt(concentration.products_for_80pct_revenue) || '>500'}</strong> = 80% ·{' '}
            <strong>{fmtInt(concentration.products_for_90pct_revenue) || '>500'}</strong> = 90%.
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={paretoChart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="rank" stroke="#94a3b8" tick={{ fontSize: 11 }} />
              <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} domain={[0, 100]} />
              <Tooltip
                contentStyle={{ background: '#0f172a', border: '1px solid #334155' }}
                formatter={(v) => `${v}%`}
                labelFormatter={(rank) => `რანკი ${rank}`}
              />
              <Line type="monotone" dataKey="cum_share_pct" stroke="#a855f7" strokeWidth={2} dot={false} name="კუმულ. წილი %" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ─── Cashier table ─── */}
      {cashiers.length > 0 && (
        <CollapsibleSection title="მოლარეების ცხრილი" badge={`${filteredCashiers.length}`}>
          <p className="chart-desc">
            <InfoTip text={TIPS.cashier} />
            სახელის წყარო DB-ში ცარიელია — მხოლოდ ID-ს ვიჩვენებთ. მოწმებიდან: მოლარე #1 = მფლობელი (კაბ), #2-დან მუშები.
          </p>
          <div className="table-wrapper cashflow-table retail-sales-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>მაღაზია</th>
                  <th>მოლარე ID</th>
                  <th>ჩეკები</th>
                  <th>ხაზები</th>
                  <th>შემოსავალი</th>
                  <th>AOV</th>
                  <th>პირველი გაყიდვა</th>
                  <th>ბოლო გაყიდვა</th>
                </tr>
              </thead>
              <tbody>
                {filteredCashiers.map((c) => (
                  <tr key={`cash-${c.object}-${c.user_id}`}>
                    <td>{c.object}</td>
                    <td>#{c.user_id ?? '?'}</td>
                    <td>{fmtInt(c.receipts)}</td>
                    <td>{fmtInt(c.lines)}</td>
                    <td className="amount-positive">{fmtMoney(c.revenue)}</td>
                    <td>{fmtMoney2(c.aov)}</td>
                    <td>{(c.first_sale || '').slice(0, 10) || '—'}</td>
                    <td>{(c.last_sale || '').slice(0, 10) || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}

      {/* ─── Register table ─── */}
      {registers.length > 0 && (
        <CollapsibleSection title="სალაროების (cash-register) ცხრილი" badge={`${filteredRegisters.length}`}>
          <p className="chart-desc"><InfoTip text={TIPS.register} />ORD_TAB_ID-ის ჭრილით.</p>
          <div className="table-wrapper cashflow-table retail-sales-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>მაღაზია</th>
                  <th>სალარო ID</th>
                  <th>ჩეკები</th>
                  <th>ხაზები</th>
                  <th>შემოსავალი</th>
                </tr>
              </thead>
              <tbody>
                {filteredRegisters.map((r) => (
                  <tr key={`reg-${r.object}-${r.tab_id}`}>
                    <td>{r.object}</td>
                    <td>#{r.tab_id ?? '?'}</td>
                    <td>{fmtInt(r.receipts)}</td>
                    <td>{fmtInt(r.lines)}</td>
                    <td className="amount-positive">{fmtMoney(r.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}

      {/* ─── Shifts (cashier sessions) ─── */}
      {shifts.length > 0 && (() => {
        // Period-aware shift summary: when period filter is active, recompute
        // stats from shiftsFiltered (which respects shift_start in range).
        // Anomalies (>30h) excluded from avg/best/worst even within period.
        const usingFiltered = !!shiftsFiltered;
        const baseShifts = usingFiltered ? shiftsFiltered : shifts;
        const normalShifts = baseShifts.filter((s) => !s.is_anomalous);
        const periodAnomalies = baseShifts.filter((s) => s.is_anomalous);
        const liveSummary = usingFiltered
          ? (() => {
              if (normalShifts.length === 0) {
                return { total_shifts: baseShifts.length, normal_shift_count: 0, anomalous_shift_count: periodAnomalies.length, avg_revenue_ge: 0, median_revenue_ge: 0, best_shift_revenue_ge: 0, worst_shift_revenue_ge: 0, avg_duration_hours: 0, last_shift_start: baseShifts[0]?.shift_start };
              }
              const revs = normalShifts.map((s) => toNum(s.revenue)).sort((a, b) => a - b);
              const durs = normalShifts.map((s) => toNum(s.duration_hours)).filter((d) => d > 0);
              return {
                total_shifts: baseShifts.length,
                normal_shift_count: normalShifts.length,
                anomalous_shift_count: periodAnomalies.length,
                avg_revenue_ge: revs.reduce((s, v) => s + v, 0) / revs.length,
                median_revenue_ge: revs[Math.floor(revs.length / 2)],
                best_shift_revenue_ge: revs[revs.length - 1],
                worst_shift_revenue_ge: revs[0],
                avg_duration_hours: durs.length ? durs.reduce((s, v) => s + v, 0) / durs.length : 0,
                last_shift_start: baseShifts[0]?.shift_start,
              };
            })()
          : shiftSummary;
        const displayShifts = baseShifts;
        const displayAnomalies = usingFiltered ? periodAnomalies : shiftAnomalies;
        return (
        <div className="chart-card">
          <h3>ცვლების ჭრილი {usingFiltered && periodKpis ? `— ${periodKpis.label_ka}` : ''}<InfoTip text={TIPS.shift} /></h3>
          <div className="kpi-grid retail-sales-kpi-grid" style={{ marginTop: 8 }}>
            <div className="kpi-card">
              <div className="kpi-label">ცვლები სულ</div>
              <div className="kpi-value amount-neutral">{fmtInt(liveSummary.total_shifts)}</div>
              <div className="kpi-sub">
                ნორმალური: {fmtInt(liveSummary.normal_shift_count)} ·
                ანომალია: {fmtInt(liveSummary.anomalous_shift_count)}
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">საშ. შემოსავ. ერთ ცვლაზე</div>
              <div className="kpi-value amount-positive">{fmtMoney(liveSummary.avg_revenue_ge)}</div>
              <div className="kpi-sub">მედიანა: {fmtMoney(liveSummary.median_revenue_ge)}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">საუკეთესო ცვლა</div>
              <div className="kpi-value amount-positive">{fmtMoney(liveSummary.best_shift_revenue_ge)}</div>
              <div className="kpi-sub">ერთ ცვლაში მაქს. შემოსავალი</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">საშ. ცვლის ხანგრძლივობა</div>
              <div className="kpi-value amount-neutral">{fmtNum(liveSummary.avg_duration_hours)} სთ</div>
              <div className="kpi-sub">ბოლო: {(liveSummary.last_shift_start || '').slice(0, 10) || '—'}</div>
            </div>
          </div>
          {displayAnomalies.length > 0 && (
            <div style={{ marginTop: 12, padding: 10, background: '#1f1916', border: '1px solid #92400e', borderRadius: 6 }}>
              <p style={{ fontSize: 12, color: '#fbbf24', margin: 0, marginBottom: 6 }}>
                ⚠️ {displayAnomalies.length} ცვლა {'>'}30 საათი — სავარაუდოდ მოლარემ არ დახურა ცვლა, ან ID განმეორებულად მოხვდა მონაცემებში. ჯამში ჩათვლილია, მაგრამ საშ./მაქს. ანგარიშიდან გამორიცხულია.
              </p>
              <div className="table-wrapper" style={{ fontSize: 12 }}>
                <table>
                  <thead><tr>
                    <th>shift_id</th><th>დაწყება</th><th>დასრ.</th><th>ხანგრძ.</th><th>ხაზები</th><th>შემოსავ.</th>
                    {storeFilter === 'all' && <th>მაღაზია</th>}
                  </tr></thead>
                  <tbody>
                    {displayAnomalies.map((a) => (
                      <tr key={`anom-${a.shift_id}-${a.object || ''}`}>
                        <td>{a.shift_id}</td>
                        <td>{(a.shift_start || '').slice(0, 10)}</td>
                        <td>{(a.shift_end || '').slice(0, 10)}</td>
                        <td>{fmtNum(a.duration_hours)} სთ</td>
                        <td>{fmtInt(a.lines)}</td>
                        <td>{fmtMoney(a.revenue)}</td>
                        {storeFilter === 'all' && <td>{a.object || '—'}</td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {displayShifts.length === 0 ? (
            <p className="chart-desc" style={{ marginTop: 8, fontSize: 12, color: '#94a3b8' }}>
              ⓘ არჩეულ პერიოდში ცვლა არ მოიძებნა.
            </p>
          ) : (
          <CollapsibleSection title={`${usingFiltered ? 'პერიოდის' : 'ბოლო'} ${displayShifts.length} ცვლა`} badge={`${displayShifts.length}`}>
            <div className="table-wrapper cashflow-table retail-sales-table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>დასაწყისი</th>
                    <th>ხანგრძ.</th>
                    <th>მაღაზია</th>
                    <th>მოლარე</th>
                    <th>სალარო</th>
                    <th>ჩეკები</th>
                    <th>ხაზები</th>
                    <th>შემოსავალი</th>
                    <th>AOV</th>
                  </tr>
                </thead>
                <tbody>
                  {displayShifts.slice(0, 60).map((s) => (
                    <tr key={`shift-${s.shift_id}-${s.object || ''}`}>
                      <td>{(s.shift_start || '').replace('T', ' ').slice(0, 16) || '—'}</td>
                      <td>{fmtNum(s.duration_hours)} სთ</td>
                      <td>
                        {s.object ? (
                          <span style={{
                            padding: '2px 6px', borderRadius: 4, fontSize: 11,
                            background: STORE_COLOR[s.object] ? `${STORE_COLOR[s.object]}30` : '#334155',
                            color: STORE_COLOR[s.object] || '#cbd5e1',
                            border: `1px solid ${STORE_COLOR[s.object] || '#475569'}`,
                          }}>{s.object}</span>
                        ) : '—'}
                      </td>
                      <td>#{s.user_id ?? '?'}</td>
                      <td>#{s.tab_id ?? '?'}</td>
                      <td>{fmtInt(s.receipts)}</td>
                      <td>{fmtInt(s.lines)}</td>
                      <td className="amount-positive">{fmtMoney(s.revenue)}</td>
                      <td>{fmtMoney2(s.aov)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CollapsibleSection>
          )}
        </div>
        );
      })()}

      {/* ─── Returns + voids ─── */}
      {returnsVoids.length > 0 && (
        <div className="chart-card">
          <h3>დაბრუნება + გაუქმება<InfoTip text={TIPS.returns} /></h3>
          <table style={{ width: '100%', fontSize: 13 }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>ტიპი</th>
                <th style={{ textAlign: 'right' }}>ხაზები</th>
                <th style={{ textAlign: 'right' }}>შემოსავალი</th>
                <th style={{ textAlign: 'right' }}>რაოდ.</th>
                <th style={{ textAlign: 'right' }}>%</th>
              </tr>
            </thead>
            <tbody>
              {returnsVoids.map((r) => (
                <tr key={`rv-${r.kind}`}>
                  <td>{r.label_ka} (act={r.act})</td>
                  <td style={{ textAlign: 'right' }}>{fmtInt(r.lines)}</td>
                  <td style={{ textAlign: 'right' }}>{fmtMoney(r.revenue_ge)}</td>
                  <td style={{ textAlign: 'right' }}>{fmtNum(r.quantity)}</td>
                  <td style={{ textAlign: 'right' }}>{fmtPct(r.share_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ─── Returns by product / cashier / month ─── */}
      {returnsByProduct.length > 0 && (
        <CollapsibleSection
          title="დაბრუნებული პროდუქტების top სია"
          badge={`${returnsByProduct.length}`}
        >
          <p className="chart-desc"><InfoTip text={TIPS.returnsByProduct} />ORD_ACT=2 ჯგუფირებული პროდუქტის მიხედვით.</p>
          <div className="table-wrapper cashflow-table retail-sales-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>პროდუქტი</th>
                  <th>კატეგორია</th>
                  <th>დაბრ. ხაზები</th>
                  <th>დაბრ. ჩეკი</th>
                  <th>დაბრ. შემოს.</th>
                  <th>რაოდ.</th>
                  <th>ბოლო დაბრ.</th>
                </tr>
              </thead>
              <tbody>
                {returnsByProduct.map((r, i) => (
                  <tr key={`rbp-${r.barcode || r.product_code || i}`}>
                    <td>{r.product_name || '—'}</td>
                    <td style={{ fontSize: 12, color: '#94a3b8' }}>{r.category || '—'}</td>
                    <td>{fmtInt(r.return_lines)}</td>
                    <td>{fmtInt(r.return_receipts)}</td>
                    <td className="amount-negative">{fmtMoney(r.return_revenue_ge)}</td>
                    <td>{fmtNum(r.return_quantity)}</td>
                    <td style={{ fontSize: 12 }}>{(r.last_return || '').slice(0, 10) || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}

      {returnsByMonth.length > 0 && (
        <div className="chart-card">
          <h3>დაბრუნების თვიური ცემპი<InfoTip text={TIPS.returnsByMonth} /></h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={returnsByMonth} margin={{ top: 10, right: 20, left: 30, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="month" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }}
                formatter={(value, key) => [
                  key === 'revenue_ge' ? fmtMoney(value) : fmtInt(value),
                  key === 'revenue_ge' ? 'შემოსავალი' : (key === 'lines' ? 'ხაზები' : 'ჩეკი'),
                ]}
              />
              <Legend />
              <Bar dataKey="revenue_ge" name="დაბრუნ. შემოსავ." fill="#ef4444" />
              <Bar dataKey="lines" name="ხაზები" fill="#f59e0b" yAxisId="right" />
              <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" fontSize={11} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {returnsByCashier.length > 0 && (
        <CollapsibleSection
          title="დაბრუნებები მოლარის მიხედვით"
          badge={`${returnsByCashier.length}`}
        >
          <p className="chart-desc">რომელმა მოლარემ რამდენი დაბრუნება მიიღო.</p>
          <div className="table-wrapper cashflow-table retail-sales-table-scroll">
            <table>
              <thead>
                <tr>
                  {storeFilter === 'all' && <th>მაღაზია</th>}
                  <th>მოლარე ID</th>
                  <th>დაბრ. ხაზები</th>
                  <th>დაბრ. ჩეკი</th>
                  <th>დაბრ. შემოს.</th>
                </tr>
              </thead>
              <tbody>
                {returnsByCashier.map((c, i) => (
                  <tr key={`rbc-${c.object || ''}-${c.user_id ?? i}`}>
                    {storeFilter === 'all' && <td>{c.object || '—'}</td>}
                    <td>#{c.user_id ?? '?'}</td>
                    <td>{fmtInt(c.return_lines)}</td>
                    <td>{fmtInt(c.return_receipts)}</td>
                    <td className="amount-negative">{fmtMoney(c.return_revenue_ge)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}

      {/* ─── Discount panel ─── */}
      {discount.discounted_lines > 0 && (
        <div className="chart-card">
          <h3>ფასდაკლების ანალიზი<InfoTip text={TIPS.markdown} /></h3>
          <div className="kpi-grid retail-sales-kpi-grid" style={{ marginTop: 8 }}>
            <div className="kpi-card">
              <div className="kpi-label">ფასდაკლების ჯამი</div>
              <div className="kpi-value amount-negative">{fmtMoney(discount.markdown_total_ge)}</div>
              <div className="kpi-sub">დახარჯული ფული რომ მომხმარებელი მოგვიზიდოთ</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">ფასდაკლებული ხაზი</div>
              <div className="kpi-value amount-neutral">{fmtInt(discount.discounted_lines)}</div>
              <div className="kpi-sub">{fmtInt(discount.discounted_receipts)} ჩეკში</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">საშ. ფასდაკლების %</div>
              <div className="kpi-value amount-neutral">{fmtPct(discount.avg_markdown_pct)}</div>
              <div className="kpi-sub">სრული ფასიდან რა შემცირდა</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">% შემოსავალში</div>
              <div className="kpi-value amount-neutral">{fmtPct(discount.share_of_revenue_pct)}</div>
              <div className="kpi-sub">ფასდაკლებული გაყიდვის წილი</div>
            </div>
          </div>
        </div>
      )}

      {/* ─── Discount lift — actual vs hypothetical-without-discount ─── */}
      {toNum(discountLiftSummary.markdown_total_ge) > 0 && (
        <div className="chart-card">
          <h3>ფასდაკლების შედეგი (Lift)<InfoTip text={TIPS.discountLift} /></h3>
          <div className="kpi-grid retail-sales-kpi-grid" style={{ marginTop: 8 }}>
            <div className="kpi-card">
              <div className="kpi-label">ფაქტობრივი მოგება</div>
              <div className="kpi-value amount-positive">{fmtMoney(discountLiftSummary.profit_actual_ge)}</div>
              <div className="kpi-sub">ფასდაკლებული გაყიდვებიდან</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">თუ ფასდაკლება არ ყოფილიყო</div>
              <div className="kpi-value amount-positive">{fmtMoney(discountLiftSummary.profit_if_no_discount_ge)}</div>
              <div className="kpi-sub">ჰიპოთეზა — სრული ფასით გაყიდვა</div>
            </div>
            <div className="kpi-card" style={{ borderLeft: '3px solid #f59e0b' }}>
              <div className="kpi-label">დაკარგული მოგება</div>
              <div className="kpi-value amount-negative">{fmtMoney(discountLiftSummary.profit_lost_ge)}</div>
              <div className="kpi-sub">ფასდაკლებაზე დახარჯული</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">კატეგორია ფასდაკლებით</div>
              <div className="kpi-value amount-neutral">{fmtInt(discountLiftSummary.categories_with_discount)}</div>
              <div className="kpi-sub">სულ რამდენ კატეგორიას ჰქონდა markdown</div>
            </div>
          </div>
          {discountByCategory.length > 0 && (
            <CollapsibleSection title="top კატეგორიები ფასდაკლებით" badge={`${discountByCategory.length}`}>
              <p className="chart-desc"><InfoTip text={TIPS.discountByCat} />ფასდაკლების ჯამი ჩამოთვლილი კატეგორიების მიხედვით.</p>
              <div className="table-wrapper cashflow-table retail-sales-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>კატეგორია</th>
                      <th>ხაზები</th>
                      <th>ფასდ. ჯამი</th>
                      <th>ფასდ. %</th>
                      <th>გაყიდვა (after)</th>
                      <th>თუ markdown არ ყოფილიყო</th>
                      <th>ფაქტ. მოგება</th>
                      <th>ალტერნ. მოგება</th>
                    </tr>
                  </thead>
                  <tbody>
                    {discountByCategory.map((c, i) => (
                      <tr key={`dbc-${c.category || i}`}>
                        <td>{c.category || '—'}</td>
                        <td>{fmtInt(c.lines)}</td>
                        <td className="amount-negative">{fmtMoney(c.markdown_total_ge)}</td>
                        <td>{fmtPct(c.markdown_pct)}</td>
                        <td className="amount-positive">{fmtMoney(c.revenue_after_markdown_ge)}</td>
                        <td>{fmtMoney(c.revenue_before_markdown_ge)}</td>
                        <td className={renderMoneyClass(c.profit_actual_ge)}>{fmtMoney(c.profit_actual_ge)}</td>
                        <td className={renderMoneyClass(c.profit_if_no_discount_ge)}>{fmtMoney(c.profit_if_no_discount_ge)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CollapsibleSection>
          )}
        </div>
      )}

      {/* ─── VAT (დღგ) ─── */}
      {toNum(vatTotals.vat_collected_ge) > 0 && (
        <div className="chart-card">
          <h3>დღგ (VAT) ანალიზი {vatTotalsPeriod && periodKpis ? `— ${periodKpis.label_ka}` : ''}<InfoTip text={TIPS.vat} /></h3>
          <div className="kpi-grid retail-sales-kpi-grid" style={{ marginTop: 8 }}>
            <div className="kpi-card">
              <div className="kpi-label">დღგ შეგროვილი</div>
              <div className="kpi-value amount-neutral">{fmtMoney(vatTotalsPeriod ? vatTotalsPeriod.vat_collected_ge : vatTotals.vat_collected_ge)}</div>
              <div className="kpi-sub">სრულ შემოსავალში: {fmtPct(vatTotalsPeriod ? vatTotalsPeriod.effective_rate_pct : vatTotals.effective_rate_pct)}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">პერიოდის შემოსავალი</div>
              <div className="kpi-value amount-positive">{fmtMoney(vatTotalsPeriod ? vatTotalsPeriod.revenue_ge : vatTotals.revenue_ge)}</div>
              <div className="kpi-sub">{vatTotalsPeriod ? `${vatTotalsPeriod.months} თვე` : 'ლიფტაიმი'}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">დღგ-ის გარეშე ხაზი (ლიფტაიმი)</div>
              <div className="kpi-value amount-neutral">{fmtInt(vatTotals.exempt_lines)}</div>
              <div className="kpi-sub">სულ {fmtInt(vatTotals.lines)} ხაზიდან · {fmtPct(vatTotals.exempt_share_pct)}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">ეფექტური განაკვეთი</div>
              <div className="kpi-value amount-neutral">{fmtPct(vatTotalsPeriod ? vatTotalsPeriod.effective_rate_pct : vatTotals.effective_rate_pct)}</div>
              <div className="kpi-sub">სტანდარტი: 18% / 1.18 = 15.25%</div>
            </div>
          </div>

          {vatByMonth.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h4 style={{ fontSize: 14, color: '#cbd5e1', marginBottom: 8 }}>თვიური დღგ-ს ცემპი</h4>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={vatByMonth} margin={{ top: 10, right: 20, left: 30, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="month" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }}
                    formatter={(value, key) => [
                      key === 'effective_rate_pct' ? fmtPct(value) : fmtMoney(value),
                      key === 'vat_collected_ge' ? 'დღგ' : (key === 'revenue_ge' ? 'შემოსავალი' : 'განაკვეთი'),
                    ]}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="vat_collected_ge" name="დღგ ჯამი" stroke="#3b82f6" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="effective_rate_pct" name="ეფექტ. %" stroke="#f59e0b" strokeWidth={1.5} dot={false} yAxisId="right" />
                  <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" fontSize={11} domain={[0, 20]} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {vatByCategory.length > 0 && (
            <CollapsibleSection title="top კატეგორიები დღგ-ის ჭრილში" badge={`${vatByCategory.length}`}>
              <div className="table-wrapper cashflow-table retail-sales-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>კატეგორია</th>
                      <th>დღგ შეგროვ.</th>
                      <th>შემოსავალი</th>
                      <th>ეფექტ. %</th>
                      <th>გამონ. ხაზი</th>
                      <th>გამონ. %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vatByCategory.map((c, i) => (
                      <tr key={`vbc-${c.category || i}`}>
                        <td>{c.category || '—'}</td>
                        <td className="amount-neutral">{fmtMoney(c.vat_collected_ge)}</td>
                        <td className="amount-positive">{fmtMoney(c.revenue_ge)}</td>
                        <td>
                          <span style={{
                            padding: '1px 6px', borderRadius: 4, fontSize: 11,
                            background: toNum(c.effective_rate_pct) > 16 ? '#7f1d1d' : '#334155',
                            color: toNum(c.effective_rate_pct) > 16 ? '#fca5a5' : '#cbd5e1',
                          }}>{fmtPct(c.effective_rate_pct)}</span>
                        </td>
                        <td>{fmtInt(c.exempt_lines)}</td>
                        <td>{fmtPct(c.exempt_share_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="chart-desc" style={{ marginTop: 8, fontSize: 11, color: '#94a3b8' }}>
                ⓘ თუ ეფექტ. % &gt; 16% — ეს მონაცემთა ხარისხის ნიშანია. სტანდარტი ≈15.25%.
              </p>
            </CollapsibleSection>
          )}
        </div>
      )}

      {/* ─── Top recent movers (365-day window vs lifetime) ─── */}
      {topRecentMovers.length > 0 && (
        <CollapsibleSection title="ბოლო 365 დღის ლიდერი პროდუქტები" badge={`${topRecentMovers.length}`}>
          <p className="chart-desc">
            <InfoTip text='ბოლო 365 დღის რანკი vs lifetime რანკი. "rank ცვლა" დადებითი = ცემპი (აიწია); უარყოფითი = ვარდნა (დაეცა).' />
            ცვლა ცხადყოფს რა საქონელი იწევა / ეცემა — recent რანკი vs lifetime.
          </p>
          <div className="table-wrapper cashflow-table retail-sales-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>recent #</th>
                  <th>lifetime #</th>
                  <th>ცვლა</th>
                  <th>პროდუქტი</th>
                  <th>კატეგორია</th>
                  <th>დომინანტი მაღაზია</th>
                  <th>365-დღ. შემოს.</th>
                  <th>365-დღ. მოგება</th>
                  <th>Margin</th>
                </tr>
              </thead>
              <tbody>
                {topRecentMovers.map((p) => {
                  const breakdown = p.store_breakdown || {};
                  const dvabzu = toNum(breakdown['დვაბზუ']);
                  const ozurgeti = toNum(breakdown['ოზურგეთი']);
                  const isExclusive = (dvabzu === 0 && ozurgeti > 0) || (ozurgeti === 0 && dvabzu > 0);
                  return (
                    <tr key={`mover-${p.product_code || p.product_name}-${p.rank_recent}`}>
                      <td>#{p.rank_recent}</td>
                      <td>{p.rank_lifetime ? `#${p.rank_lifetime}` : '—'}</td>
                      <td>
                        {p.rank_change == null ? '—' : (
                          <span style={{
                            padding: '1px 6px', borderRadius: 4, fontSize: 11,
                            background: p.rank_change > 0 ? '#064e3b' : (p.rank_change < 0 ? '#7f1d1d' : '#334155'),
                            color: p.rank_change > 0 ? '#6ee7b7' : (p.rank_change < 0 ? '#fca5a5' : '#cbd5e1'),
                          }}>{p.rank_change > 0 ? '▲' : (p.rank_change < 0 ? '▼' : '=')} {Math.abs(p.rank_change)}</span>
                        )}
                      </td>
                      <td>{p.product_name || 'უცნობი'}</td>
                      <td style={{ fontSize: 12, color: '#94a3b8' }}>{p.category || '—'}</td>
                      <td>
                        <span style={{
                          padding: '2px 6px', borderRadius: 4, fontSize: 11,
                          background: STORE_COLOR[p.dominant_store] ? `${STORE_COLOR[p.dominant_store]}30` : '#334155',
                          color: STORE_COLOR[p.dominant_store] || '#cbd5e1',
                          border: `1px solid ${STORE_COLOR[p.dominant_store] || '#475569'}`,
                        }}>
                          {p.dominant_store || '—'} {isExclusive ? '(ერთადერთი)' : `${fmtNum(p.dominant_store_share_pct)}%`}
                        </span>
                        {!isExclusive && dvabzu > 0 && ozurgeti > 0 && (
                          <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>
                            დ: {fmtMoney(dvabzu)} · ო: {fmtMoney(ozurgeti)}
                          </div>
                        )}
                      </td>
                      <td className="amount-positive">{fmtMoney(p.revenue_ge_recent)}</td>
                      <td className={renderMoneyClass(p.profit_ge_recent)}>{fmtMoney(p.profit_ge_recent)}</td>
                      <td>{fmtPct(p.gross_margin_pct_recent)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}

      {/* ─── Slow movers / dead stock candidates ─── */}
      {(slowMovers.bucket_30_60_count > 0 || slowMovers.bucket_60_90_count > 0 || slowMovers.bucket_90_plus_count > 0) && (
        <div className="chart-card" style={{ borderLeft: '3px solid #ef4444' }}>
          <h3 style={{ color: '#fca5a5' }}>🐢 slow movers / dead stock candidates<InfoTip text="ბოლო გაყიდვის თარიღიდან 30/60/90+ დღე. ჯერ კიდევ ნაშთშია? — ფული ცხნად ჩარიცხული. რაც უფრო მაღალი lifetime შემოსავალი, მით უფრო მნიშვნელოვანი — ცარიელი ფული." /></h3>
          <p className="chart-desc">
            Anchor: {slowMovers.anchor_date || '—'} · 30-60 დღე: {fmtInt(slowMovers.bucket_30_60_count)} პროდუქტი ·{' '}
            60-90 დღე: {fmtInt(slowMovers.bucket_60_90_count)} ·{' '}
            90+ დღე: {fmtInt(slowMovers.bucket_90_plus_count)}
          </p>
          {asArray(slowMovers.top_90_plus).length > 0 && (
            <CollapsibleSection title={`90+ დღე გაყიდვის გარეშე — top ${asArray(slowMovers.top_90_plus).length}`} badge={`${slowMovers.bucket_90_plus_count}`}>
              <div className="table-wrapper cashflow-table retail-sales-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>პროდუქტი</th>
                      <th>კატეგორია</th>
                      <th>მაღაზია</th>
                      <th>lifetime შემოს.</th>
                      <th>lifetime რაოდ.</th>
                      <th>ბოლო გაყიდვა</th>
                      <th>დღე გაყიდვის გარეშე</th>
                    </tr>
                  </thead>
                  <tbody>
                    {asArray(slowMovers.top_90_plus).map((p) => {
                      const bd = p.store_breakdown || {};
                      const stores = Object.keys(bd);
                      const exclusive = stores.length === 1;
                      return (
                        <tr key={`slow90-${p.product_code || p.product_name}`}>
                          <td>{p.product_name || 'უცნობი'}</td>
                          <td style={{ fontSize: 12, color: '#94a3b8' }}>{p.category || '—'}</td>
                          <td>
                            <span style={{
                              padding: '2px 6px', borderRadius: 4, fontSize: 11,
                              background: STORE_COLOR[p.dominant_store] ? `${STORE_COLOR[p.dominant_store]}30` : '#334155',
                              color: STORE_COLOR[p.dominant_store] || '#cbd5e1',
                              border: `1px solid ${STORE_COLOR[p.dominant_store] || '#475569'}`,
                            }}>
                              {p.dominant_store || '—'} {exclusive ? '(ერთადერთი)' : `${fmtNum(p.dominant_store_share_pct)}%`}
                            </span>
                          </td>
                          <td className="amount-positive">{fmtMoney(p.revenue_ge)}</td>
                          <td>{fmtNum(p.total_quantity)}</td>
                          <td>{p.last_sale_date || '—'}</td>
                          <td>
                            <span style={{ padding: '1px 6px', borderRadius: 4, fontSize: 11, background: '#7f1d1d', color: '#fca5a5' }}>
                              {p.days_since_sale} დღე
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CollapsibleSection>
          )}
          {asArray(slowMovers.top_60_90).length > 0 && (
            <CollapsibleSection title={`60-90 დღე გაყიდვის გარეშე — top ${asArray(slowMovers.top_60_90).length}`} badge={`${slowMovers.bucket_60_90_count}`}>
              <div className="table-wrapper cashflow-table retail-sales-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>პროდუქტი</th>
                      <th>მაღაზია</th>
                      <th>lifetime შემოს.</th>
                      <th>ბოლო გაყიდვა</th>
                      <th>დღე</th>
                    </tr>
                  </thead>
                  <tbody>
                    {asArray(slowMovers.top_60_90).map((p) => {
                      const bd = p.store_breakdown || {};
                      const exclusive = Object.keys(bd).length === 1;
                      return (
                        <tr key={`slow60-${p.product_code || p.product_name}`}>
                          <td>{p.product_name || 'უცნობი'}</td>
                          <td>
                            <span style={{
                              padding: '2px 6px', borderRadius: 4, fontSize: 11,
                              background: STORE_COLOR[p.dominant_store] ? `${STORE_COLOR[p.dominant_store]}30` : '#334155',
                              color: STORE_COLOR[p.dominant_store] || '#cbd5e1',
                              border: `1px solid ${STORE_COLOR[p.dominant_store] || '#475569'}`,
                            }}>
                              {p.dominant_store || '—'} {exclusive ? '(ერთადერთი)' : `${fmtNum(p.dominant_store_share_pct)}%`}
                            </span>
                          </td>
                          <td className="amount-positive">{fmtMoney(p.revenue_ge)}</td>
                          <td>{p.last_sale_date || '—'}</td>
                          <td>{p.days_since_sale}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CollapsibleSection>
          )}
          {asArray(slowMovers.top_30_60).length > 0 && (
            <CollapsibleSection title={`30-60 დღე გაყიდვის გარეშე — top ${asArray(slowMovers.top_30_60).length}`} badge={`${slowMovers.bucket_30_60_count}`}>
              <div className="table-wrapper cashflow-table retail-sales-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>პროდუქტი</th>
                      <th>მაღაზია</th>
                      <th>lifetime შემოს.</th>
                      <th>ბოლო გაყიდვა</th>
                      <th>დღე</th>
                    </tr>
                  </thead>
                  <tbody>
                    {asArray(slowMovers.top_30_60).map((p) => {
                      const bd = p.store_breakdown || {};
                      const exclusive = Object.keys(bd).length === 1;
                      return (
                        <tr key={`slow30-${p.product_code || p.product_name}`}>
                          <td>{p.product_name || 'უცნობი'}</td>
                          <td>
                            <span style={{
                              padding: '2px 6px', borderRadius: 4, fontSize: 11,
                              background: STORE_COLOR[p.dominant_store] ? `${STORE_COLOR[p.dominant_store]}30` : '#334155',
                              color: STORE_COLOR[p.dominant_store] || '#cbd5e1',
                              border: `1px solid ${STORE_COLOR[p.dominant_store] || '#475569'}`,
                            }}>
                              {p.dominant_store || '—'} {exclusive ? '(ერთადერთი)' : `${fmtNum(p.dominant_store_share_pct)}%`}
                            </span>
                          </td>
                          <td className="amount-positive">{fmtMoney(p.revenue_ge)}</td>
                          <td>{p.last_sale_date || '—'}</td>
                          <td>{p.days_since_sale}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CollapsibleSection>
          )}
        </div>
      )}

      {/* ─── Coverage + duplicate policy ─── */}
      <div className="chart-card">
        <h3>Coverage და duplicate policy<InfoTip text={TIPS.coverage} /></h3>
        <p className="chart-desc">
          Source files: ნაპოვნი {fmtInt(summary.files_found_count)} · წაკითხული{' '}
          {fmtInt(summary.files_read_count)} · policy-skip {fmtInt(summary.files_skipped_by_policy_count)}
          {' '}· errors {fmtInt(summary.files_error_count)}
        </p>
        <div className="retail-sales-badge-row">
          <span className={`badge ${summary.categories_truncated ? 'conf-medium' : 'conf-high'}`}>
            კატეგორიები: {fmtInt(categoriesShown)} / {fmtInt(summary.category_total_count)}
          </span>
          <span className={`badge ${summary.products_truncated ? 'conf-medium' : 'conf-high'}`}>
            პროდუქტები: {fmtInt(productsShown)} / {fmtInt(summary.products_total_count)}
          </span>
          <span className={`badge ${toNum(duplicatePolicy.excluded_file_count) > 0 ? 'conf-low' : 'conf-high'}`}>
            duplicate excluded: {fmtInt(duplicatePolicy.excluded_file_count)}
          </span>
        </div>
        {suspectedFiles.length > 0 && (
          <ul className="retail-sales-policy-list">
            {suspectedFiles.map((item) => (
              <li
                key={`${item.relative_path || 'missing'}-${item.suspected_duplicate_of || 'none'}`}
                className="retail-sales-policy-item"
              >
                <div className="retail-sales-policy-path"><code>{item.relative_path || 'უცნობი ფაილი'}</code></div>
                <div className="kpi-sub">suspected duplicate of: <code>{item.suspected_duplicate_of || '—'}</code></div>
                {item.reason_ka ? <div className="chart-desc">{item.reason_ka}</div> : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ─── Per-store summary table ─── */}
      <div className="chart-card">
        <h3>ობიექტების summary</h3>
        <div className="table-wrapper cashflow-table retail-sales-table-scroll">
          <table>
            <thead>
              <tr>
                <th>ობიექტი</th>
                <th>ხაზები</th>
                <th>რაოდენობა</th>
                <th>შემოსავალი</th>
                <th>თვითღირებულება</th>
                <th>მოგება</th>
                <th>Margin</th>
                <th>კატ./პროდ.</th>
                <th>პერიოდი</th>
              </tr>
            </thead>
            <tbody>
              {byObject.map((row) => (
                <tr key={`retail-object-${row.object || 'unknown'}`}>
                  <td>{row.object || 'უცნობი'}</td>
                  <td>{fmtInt(row.row_count)}</td>
                  <td>{fmtNum(row.total_quantity)}</td>
                  <td className="amount-positive">{fmtMoney(row.revenue_ge)}</td>
                  <td className="amount-negative">{fmtMoney(row.cost_ge)}</td>
                  <td className={renderMoneyClass(row.profit_ge)}>{fmtMoney(row.profit_ge)}</td>
                  <td>{fmtPct(row.gross_margin_pct)}</td>
                  <td>{fmtInt(row.distinct_category_count)} / {fmtInt(row.distinct_product_count)}</td>
                  <td>{renderDateRange(row.date_range)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ─── Monthly table ─── */}
      <div className="chart-card">
        <h3>თვიური ცხრილი</h3>
        <div className="table-wrapper cashflow-table retail-sales-table-scroll">
          <table>
            <thead>
              <tr>
                <th>თვე</th>
                <th>ხაზები</th>
                <th>რაოდენობა</th>
                <th>შემოსავალი</th>
                <th>თვითღირებულება</th>
                <th>მოგება</th>
                <th>Margin</th>
              </tr>
            </thead>
            <tbody>
              {byMonth.map((row) => (
                <tr key={`retail-month-${row.month || 'unknown'}`}>
                  <td>{row.month || 'უცნობი თვე'}</td>
                  <td>{fmtInt(row.row_count)}</td>
                  <td>{fmtNum(row.total_quantity)}</td>
                  <td className="amount-positive">{fmtMoney(row.revenue_ge)}</td>
                  <td className="amount-negative">{fmtMoney(row.cost_ge)}</td>
                  <td className={renderMoneyClass(row.profit_ge)}>{fmtMoney(row.profit_ge)}</td>
                  <td>{fmtPct(row.gross_margin_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ─── TOP products selector + search ─── */}
      <div className="controls" style={{ marginTop: 12, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, color: '#94a3b8' }}>TOP პროდუქტების რაოდენობა:</span>
        <select
          value={topProductsLimit}
          onChange={(e) => setTopProductsLimit(Number(e.target.value))}
          style={{ background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 6, padding: '4px 8px', fontSize: 13 }}
        >
          <option value={20}>20</option>
          <option value={30}>30</option>
          <option value={50}>50</option>
        </select>
        <span style={{ fontSize: 13, color: '#94a3b8', marginLeft: 12 }}>ძიება:</span>
        <input
          type="text"
          value={productSearch}
          onChange={(e) => setProductSearch(e.target.value)}
          placeholder="პროდუქტის სახელი / კოდი / ბარკოდი"
          style={{ background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 6, padding: '4px 10px', fontSize: 13, minWidth: 280 }}
        />
        {productSearch && (
          <button
            onClick={() => setProductSearch('')}
            style={{ background: '#7f1d1d', color: '#fca5a5', border: '1px solid #b91c1c', borderRadius: 4, padding: '3px 8px', fontSize: 11, cursor: 'pointer' }}
          >
            გაწმენდა
          </button>
        )}
        {productSearch && (
          <span className="kpi-sub" style={{ marginLeft: 6 }}>
            ნაპოვნი: {fmtInt(topProductsByRevenue.length)} (რევენიუთი) / {fmtInt(topProductsByProfit.length)} (მოგებით)
          </span>
        )}
      </div>

      <div className="retail-sales-grid-2">
        <CollapsibleSection title="TOP კატეგორიები — მოგებით" badge={`${topCategoriesByProfit.length}`}>
          <div className="table-wrapper cashflow-table retail-sales-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>კატეგორია</th>
                  <th>შემოსავალი</th>
                  <th>თვითღირებულება</th>
                  <th>მოგება</th>
                  <th>Margin</th>
                </tr>
              </thead>
              <tbody>
                {topCategoriesByProfit.map((row) => (
                  <tr key={`retail-cat-${row.category || 'unknown'}`}>
                    <td>{row.category || 'უცნობი კატეგორია'}</td>
                    <td className="amount-positive">{fmtMoney(row.revenue_ge)}</td>
                    <td className="amount-negative">{fmtMoney(row.cost_ge)}</td>
                    <td className={renderMoneyClass(row.profit_ge)}>{fmtMoney(row.profit_ge)}</td>
                    <td>{fmtPct(row.gross_margin_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>

        <CollapsibleSection title="TOP პროდუქტები — შემოსავლით" badge={`${topProductsByRevenue.length}`}>
          <div className="table-wrapper cashflow-table retail-sales-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>პროდუქტი</th>
                  <th>კოდი</th>
                  <th>შემოსავალი</th>
                  <th>მოგება</th>
                  <th>Margin</th>
                </tr>
              </thead>
              <tbody>
                {topProductsByRevenue.map((row) => (
                  <tr key={`retail-revenue-${row.product_code || 'na'}-${row.product_name || 'na'}-${toNum(row.revenue_ge)}`}>
                    <td>{row.product_name || 'უცნობი პროდუქტი'}</td>
                    <td>{row.product_code || '—'}</td>
                    <td className="amount-positive">{fmtMoney(row.revenue_ge)}</td>
                    <td className={renderMoneyClass(row.profit_ge)}>{fmtMoney(row.profit_ge)}</td>
                    <td>{fmtPct(row.gross_margin_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      </div>

      <CollapsibleSection title="TOP პროდუქტები — მოგებით" badge={`${topProductsByProfit.length}`}>
        <div className="table-wrapper cashflow-table retail-sales-table-scroll">
          <table>
            <thead>
              <tr>
                <th>პროდუქტი</th>
                <th>კოდი</th>
                <th>კატეგორია</th>
                <th>შემოსავალი</th>
                <th>თვითღირებულება</th>
                <th>მოგება</th>
                <th>Margin</th>
              </tr>
            </thead>
            <tbody>
              {topProductsByProfit.map((row) => (
                <tr key={`retail-profit-${row.product_code || 'na'}-${row.product_name || 'na'}-${toNum(row.profit_ge)}`}>
                  <td>{row.product_name || 'უცნობი პროდუქტი'}</td>
                  <td>{row.product_code || '—'}</td>
                  <td>{row.category || '—'}</td>
                  <td className="amount-positive">{fmtMoney(row.revenue_ge)}</td>
                  <td className="amount-negative">{fmtMoney(row.cost_ge)}</td>
                  <td className={renderMoneyClass(row.profit_ge)}>{fmtMoney(row.profit_ge)}</td>
                  <td>{fmtPct(row.gross_margin_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CollapsibleSection>

      {/* ── Cross-store SKU comparison ─────────────────────────────────── */}
      {toNum(crossStore.shared_sku_count) > 0 && (
        <div style={{ marginTop: 24 }}>
          <h3 style={{ marginBottom: 12, color: '#e2e8f0' }}>
            მაღაზია vs მაღაზია — იგივე SKU
            <InfoTip text={TIPS.crossStore} />
          </h3>

          {/* Banner — cross-store is lifetime + ignores store filter */}
          <div style={{
            padding: '8px 12px', marginBottom: 12,
            background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
            fontSize: 13, color: '#cbd5e1',
          }}>
            ეს ცხრილი ყოველთვის ცხოვრების ჯამია — მაღაზიის ფილტრი / პერიოდის ფილტრი მასზე არ ვრცელდება.
            {' '}{crossStore.filter_notes_ka}
          </div>

          {/* KPI cards */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
            <div className="kpi-card" style={{ flex: '1 1 200px', padding: 12, background: '#1e293b', borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>SKU ორივე მაღაზიაში</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#e2e8f0' }}>{fmtInt(crossStore.shared_sku_count)}</div>
            </div>
            <div className="kpi-card" style={{ flex: '1 1 200px', padding: 12, background: '#1e293b', borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>ფასით განსხვავებული (≥5%)</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#f59e0b' }}>{fmtInt(crossStore.big_price_gap_count)}</div>
            </div>
            <div className="kpi-card" style={{ flex: '1 1 200px', padding: 12, background: '#1e293b', borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>მარჟით განსხვავებული (≥5pp)</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#ef4444' }}>{fmtInt(crossStore.big_margin_gap_count)}</div>
            </div>
          </div>

          {/* Sort selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ color: '#cbd5e1', fontSize: 13 }}>დახარისხება:</span>
            <select
              value={crossStoreSortBy}
              onChange={(e) => setCrossStoreSortBy(e.target.value)}
              style={{ padding: '4px 8px', background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 4 }}
            >
              <option value="price_gap">ფასის სხვაობით (top 50)</option>
              <option value="margin_gap">მარჟის სხვაობით (top 50)</option>
              <option value="combined_rev">ჯამური შემოსავლით (top 50)</option>
            </select>
          </div>

          <CollapsibleSection title={`top ${crossStoreItems.length} SKU`} badge={`${crossStoreItems.length}`}>
            <div className="table-wrapper cashflow-table retail-sales-table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>შტრიხკოდი</th>
                    <th>დასახელება</th>
                    <th>კატეგორია</th>
                    <th>დვაბზუ რაოდ.</th>
                    <th>ოზურგ. რაოდ.</th>
                    <th>დვაბზუ ფასი</th>
                    <th>ოზურგ. ფასი</th>
                    <th>ფასის სხვაობა</th>
                    <th>დვაბზუ მარჟა</th>
                    <th>ოზურგ. მარჟა</th>
                    <th>მარჟის სხვაობა</th>
                    <th>ჯამური შემოს.</th>
                  </tr>
                </thead>
                <tbody>
                  {crossStoreItems.map((row) => {
                    const priceDiff = toNum(row.price_diff_ge);
                    const marginDiff = toNum(row.margin_diff_pp);
                    return (
                      <tr key={`cross-${row.barcode}-${row.product_name}`}>
                        <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{row.barcode}</td>
                        <td>{row.product_name || 'უცნობი'}</td>
                        <td>{row.category || '—'}</td>
                        <td style={{ textAlign: 'right' }}>{fmtNum(row.qty_dvabzu)}</td>
                        <td style={{ textAlign: 'right' }}>{fmtNum(row.qty_ozurgeti)}</td>
                        <td style={{ textAlign: 'right' }}>{fmtMoney2(row.avg_price_dvabzu_ge)}</td>
                        <td style={{ textAlign: 'right' }}>{fmtMoney2(row.avg_price_ozurgeti_ge)}</td>
                        <td style={{ textAlign: 'right', color: priceDiff >= 0 ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                          {priceDiff >= 0 ? '+' : ''}{fmtMoney2(priceDiff)}
                          <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 4 }}>
                            ({toNum(row.price_diff_pct) >= 0 ? '+' : ''}{toNum(row.price_diff_pct).toFixed(1)}%)
                          </span>
                        </td>
                        <td style={{ textAlign: 'right' }}>{fmtPct(row.margin_dvabzu_pct)}</td>
                        <td style={{ textAlign: 'right' }}>{fmtPct(row.margin_ozurgeti_pct)}</td>
                        <td style={{ textAlign: 'right', color: marginDiff >= 0 ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                          {marginDiff >= 0 ? '+' : ''}{toNum(marginDiff).toFixed(2)}pp
                        </td>
                        <td style={{ textAlign: 'right' }}>{fmtMoney(row.revenue_combined_ge)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CollapsibleSection>
        </div>
      )}

      {/* ── Dead stock — inventory aging snapshot ──────────────────────── */}
      {deadStockHasData && (
        <div style={{ marginTop: 24 }}>
          <h3 style={{ marginBottom: 12, color: '#e2e8f0' }}>
            მკვდარი მარაგი (Dead Stock)
            <InfoTip text={TIPS.deadStock} />
          </h3>

          <div style={{
            padding: '8px 12px', marginBottom: 12,
            background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
            fontSize: 13, color: '#cbd5e1',
          }}>
            ნაშთი = backup-ის <strong>{(deadStock.snapshot_date || '').slice(0, 10) || '—'}</strong> მდგომარეობით.
            მაღაზიის ფილტრს ემორჩილება. პერიოდის ფილტრი არ ვრცელდება — snapshot-ია, არა flow.
            {storeFilter === 'all' && deadStock.snapshot_dates_per_store && (
              <span style={{ marginLeft: 8, fontSize: 12, color: '#94a3b8' }}>
                (per-store: {Object.entries(deadStock.snapshot_dates_per_store).map(([s, d]) => `${s} ${(d || '').slice(0, 10)}`).join(' · ')})
              </span>
            )}
          </div>

          {/* KPI cards — total stock / dead value / dead pct / 365+ count */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
            <div className="kpi-card" style={{ flex: '1 1 200px', padding: 12, background: '#1e293b', borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>სულ ნაშთის ღირებულება</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#e2e8f0' }}>{fmtMoney(deadStock.total_stock_value)}</div>
            </div>
            <div className="kpi-card" style={{ flex: '1 1 200px', padding: 12, background: '#1e293b', borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>მკვდარი + ნელი (90+ დღე)</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#ef4444' }}>{fmtMoney(deadStock.dead_stock_value)}</div>
            </div>
            <div className="kpi-card" style={{ flex: '1 1 200px', padding: 12, background: '#1e293b', borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>მკვდარი წილი ნაშთიდან</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#f59e0b' }}>{toNum(deadStock.dead_stock_pct).toFixed(1)}%</div>
            </div>
            <div className="kpi-card" style={{ flex: '1 1 200px', padding: 12, background: '#1e293b', borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>365+ დღე გაუყიდველი SKU</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#ef4444' }}>{fmtInt((deadStockBuckets.dead_365d_plus || {}).count)}</div>
            </div>
          </div>

          {/* Bucket breakdown — counts + values per bucket */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
            {Object.entries(deadStockBucketDef).map(([key, def]) => {
              const isNeg = key === 'negative_stock';
              const data = isNeg ? deadStockNeg : (deadStockBuckets[key] || {});
              const count = toNum(data.count);
              const value = isNeg ? toNum(data.abs_value_total) : toNum(data.stock_value);
              const isActive = deadStockBucket === key;
              return (
                <button
                  key={key}
                  onClick={() => setDeadStockBucket(key)}
                  style={{
                    flex: '1 1 180px', textAlign: 'left',
                    padding: 10, background: isActive ? '#0f172a' : '#1e293b',
                    border: `1px solid ${isActive ? def.color : '#334155'}`,
                    borderLeft: `4px solid ${def.color}`,
                    borderRadius: 6, cursor: 'pointer', color: '#e2e8f0',
                  }}
                >
                  <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>{def.label}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <span style={{ fontSize: 18, fontWeight: 600 }}>{fmtInt(count)} SKU</span>
                    <span style={{ fontSize: 13, color: def.color, fontWeight: 600 }}>{fmtMoney(value)}</span>
                  </div>
                  {!isNeg && toNum((deadStockBuckets[key] || {}).never_sold_count) > 0 && (
                    <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                      აქედან {fmtInt((deadStockBuckets[key] || {}).never_sold_count)} — არასოდეს გაყიდულა
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Items table for selected bucket */}
          <CollapsibleSection
            title={`${deadStockBucketDef[deadStockBucket].label} — top ${deadStockActiveItems.length} SKU`}
            badge={`${deadStockActiveItems.length}`}
          >
            <div className="table-wrapper cashflow-table retail-sales-table-scroll">
              <table>
                <thead>
                  <tr>
                    {storeFilter === 'all' && <th>მაღაზია</th>}
                    <th>კოდი</th>
                    <th>შტრიხკოდი</th>
                    <th>დასახელება</th>
                    <th>კატეგორია</th>
                    <th style={{ textAlign: 'right' }}>რაოდ.</th>
                    <th style={{ textAlign: 'right' }}>თვითღ.</th>
                    <th style={{ textAlign: 'right' }}>გასაყ. ფასი</th>
                    <th style={{ textAlign: 'right' }}>ნაშთის ღირებ.</th>
                    <th>ბოლო გაყიდვა</th>
                    <th style={{ textAlign: 'right' }}>დღე</th>
                  </tr>
                </thead>
                <tbody>
                  {deadStockActiveItems.map((it, idx) => {
                    const days = it.days_since_sale;
                    const lastSale = it.last_sale_date ? (it.last_sale_date.slice(0, 10)) : 'არასოდეს';
                    return (
                      <tr key={`ds-${deadStockBucket}-${it.product_id}-${idx}`}>
                        {storeFilter === 'all' && <td>{it.store || '—'}</td>}
                        <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{it.product_code || '—'}</td>
                        <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{it.barcode || '—'}</td>
                        <td>{it.product_name || 'უცნობი'}</td>
                        <td>{it.category || '—'}</td>
                        <td style={{ textAlign: 'right' }}>{fmtNum(it.qty)}</td>
                        <td style={{ textAlign: 'right' }}>{fmtMoney2(it.getprice)}</td>
                        <td style={{ textAlign: 'right' }}>{fmtMoney2(it.sellprice)}</td>
                        <td style={{ textAlign: 'right', fontWeight: 600, color: deadStockBucketDef[deadStockBucket].color }}>
                          {fmtMoney(it.stock_value)}
                        </td>
                        <td style={{ fontSize: 12, color: it.last_sale_date ? '#cbd5e1' : '#94a3b8' }}>{lastSale}</td>
                        <td style={{ textAlign: 'right', color: '#94a3b8' }}>{days != null ? fmtInt(days) : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CollapsibleSection>
        </div>
      )}
    </div>
  );
}
