import { useState } from 'react';

const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 0,
});
const COUNT = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 0 });
const QUANTITY = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 2 });
const EMPTY_LIST = [];
const MONTH_PREVIEW_LIMIT = 12;

function formatMoney(value) {
  return GEL.format(Number(value) || 0);
}

function formatCount(value) {
  return COUNT.format(Number(value) || 0);
}

function formatQuantity(value) {
  return QUANTITY.format(Number(value) || 0);
}

function formatDateRange(range) {
  const min = range?.min || null;
  const max = range?.max || null;
  if (min && max) return min === max ? min : `${min} - ${max}`;
  return min || max || '—';
}

function normalizeText(value) {
  return String(value || '').trim().toLowerCase();
}

function statusBadgeClass(status) {
  const text = normalizeText(status);
  if (text.includes('გაუქმ')) return 'badge canceled';
  if (text.includes('დაბრუნ') || text.includes('უკან')) return 'badge return';
  return 'badge active';
}

function shareText(part, total) {
  const safeTotal = Number(total) || 0;
  if (safeTotal <= 0) return '—';
  return `${((Number(part) || 0) / safeTotal * 100).toFixed(1)}%`;
}

function monthBarWidth(total, maxTotal) {
  const safeMax = Math.max(Number(maxTotal) || 0, 1);
  const pct = ((Number(total) || 0) / safeMax) * 100;
  return `${Math.max(10, Math.min(100, pct))}%`;
}

function concentrationBadge(pct) {
  const val = Number(pct) || 0;
  if (val >= 80) return { label: 'მაღალი', className: 'badge conf-low' }; // Red for high concentration
  if (val >= 50) return { label: 'საშუალო', className: 'badge conf-medium' }; // Yellow
  return { label: 'განაწილებული', className: 'badge conf-high' }; // Green
}

export default function ImportedProducts({ response, loading, error, onRetry }) {
  const [supplierQuery, setSupplierQuery] = useState('');
  const [productQuery, setProductQuery] = useState('');

  const bundle = response?.imported_products || {};
  const overall = bundle.overall || {};
  const byStatus = Array.isArray(bundle.by_status) ? bundle.by_status : EMPTY_LIST;
  const byMonth = Array.isArray(bundle.by_month) ? bundle.by_month : EMPTY_LIST;
  const suppliers = Array.isArray(bundle.suppliers) ? bundle.suppliers : EMPTY_LIST;
  const products = Array.isArray(bundle.products) ? bundle.products : EMPTY_LIST;
  const topPairs = Array.isArray(bundle.top_supplier_product_pairs) ? bundle.top_supplier_product_pairs : EMPTY_LIST;
  const topSuppliers = Array.isArray(bundle.top_suppliers_by_amount) ? bundle.top_suppliers_by_amount : EMPTY_LIST;
  const topProducts = Array.isArray(bundle.top_products_by_amount) ? bundle.top_products_by_amount : EMPTY_LIST;
  const hasResponse = response != null;
  const hasRows =
    Number(overall.row_count) > 0 ||
    suppliers.length > 0 ||
    products.length > 0 ||
    topPairs.length > 0 ||
    topSuppliers.length > 0 ||
    topProducts.length > 0 ||
    byStatus.length > 0;

  const sourceFormatLabel =
    bundle.source_format === 'csv'
      ? 'CSV'
      : bundle.source_format === 'excel'
        ? 'Excel'
        : 'უცნობი';

  const filteredSuppliers = (() => {
    const needle = normalizeText(supplierQuery);
    if (!needle) return suppliers;
    return suppliers.filter((item) => {
      const supplier = normalizeText(item?.supplier);
      const taxId = normalizeText(item?.tax_id);
      return supplier.includes(needle) || taxId.includes(needle);
    });
  })();

  const visibleSuppliers = filteredSuppliers;

  const filteredProducts = (() => {
    const needle = normalizeText(productQuery);
    if (!needle) return products;
    return products.filter((item) => {
      const name = normalizeText(item?.product_name);
      const code = normalizeText(item?.product_code);
      return name.includes(needle) || code.includes(needle);
    });
  })();

  const visibleProducts = filteredProducts;

  const recentMonths = (() => {
    return byMonth
      .filter((item) => item?.month && item.month !== 'უცნობი თვე')
      .slice(-MONTH_PREVIEW_LIMIT)
      .reverse();
  })();

  const unknownMonth = byMonth.find((item) => item?.month === 'უცნობი თვე') || null;

  const maxRecentMonthTotal = (() => {
    return recentMonths.reduce((max, item) => {
      return Math.max(max, Number(item?.total_ge) || 0);
    }, 0);
  })();

  if (loading && !hasResponse) {
    return <div className="loading">იტვირთება შემოტანილი პროდუქციის ანალიზი...</div>;
  }

  return (
    <div className="imported-products-page">
      <div className="tab-hero">
        <span className="tab-hero-title">📦 შემოტანილი პროდუქცია</span>
        <span className="tab-hero-desc">Reference წყარო supplier / product-line ანალიზისთვის</span>
      </div>

      <div className="local-pay-banner imported-products-reference-note" role="note">
        Reference-only წყაროა imported-products export-იდან. ეს ბლოკი არ ერთვება supplier debt/AP,
        RS truth totals ან bank reconciliation ჯამებში; გამოიყენე როგორც დამატებითი ანალიზის ჭრილი.
      </div>

      <div className="analytics-toolbar imported-products-toolbar">
        <p className="analytics-note imported-products-summary">
          წყარო: <strong>{sourceFormatLabel}</strong> · წაკითხული ფაილები:{' '}
          <strong>{formatCount(bundle.files_read_count)}</strong> / {formatCount(bundle.files_found_count)}
          {loading ? ' · ახლდება...' : ''}
        </p>
        <div className="imported-products-meta">
          <span className="badge muted">Reference</span>
          <span className="badge muted">წყარო: {sourceFormatLabel}</span>
          <span className="badge muted">ფაილი: {formatCount(bundle.files_read_count)}</span>
        </div>
      </div>

      {error ? (
        <div className="filter-warning imported-products-error" role="alert">
          <strong>ჩატვირთვის გაფრთხილება:</strong> {error}
          <button type="button" className="btn-download-toggle imported-products-retry" onClick={onRetry}>
            თავიდან ცდა
          </button>
        </div>
      ) : null}

      {bundle.files_error_count > 0 ? (
        <div className="filter-warning" role="status">
          <strong>ყველა წყარო ვერ წაიკითხა.</strong> შეცდომით გამოტოვებულია {formatCount(bundle.files_error_count)} ფაილი,
          ამიტომ ეს view შეიძლება ნაწილობრივ არასრული იყოს.
        </div>
      ) : null}

      {bundle.truncation_suspected_any ? (
        <div className="filter-warning" role="alert">
          <strong>შესაძლო truncate/export limit.</strong> მინიმუმ {formatCount(bundle.truncation_suspected_file_count)} ფაილში
          სრული ექსპორტი საეჭვოა; თანხები და რაოდენობები გადაამოწმე წყაროსთან.
        </div>
      ) : null}

      <div className="kpi-grid">
        <div className="kpi-card kpi-card-blue">
          <div className="kpi-label">სულ თანხა</div>
          <div className="kpi-value">{formatMoney(overall.total_amount_ge)}</div>
          <div className="kpi-sub">{formatCount(overall.row_count)} ჩანაწერი</div>
        </div>
        <div className="kpi-card kpi-card-green">
          <div className="kpi-label">მომწოდებელი</div>
          <div className="kpi-value">{formatCount(overall.distinct_supplier_count)}</div>
          <div className="kpi-sub">distinct supplier</div>
        </div>
        <div className="kpi-card kpi-card-purple">
          <div className="kpi-label">პროდუქტი</div>
          <div className="kpi-value">{formatCount(overall.distinct_product_count)}</div>
          <div className="kpi-sub">distinct product</div>
        </div>
        <div className="kpi-card kpi-card-yellow">
          <div className="kpi-label">ზედნადები</div>
          <div className="kpi-value">{formatCount(overall.distinct_waybill_count)}</div>
          <div className="kpi-sub">distinct waybill</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">პერიოდი</div>
          <div className="kpi-value kpi-value--compact">{formatDateRange(overall.date_range)}</div>
          <div className="kpi-sub">{formatCount(bundle.files_read_count)} ფაილი</div>
        </div>
      </div>

      {!hasRows && !loading ? (
        <div className="chart-card">
          <h3>მონაცემები ჯერ არ არის</h3>
          <p className="chart-desc">Imported-products წყარო ცარიელია ან ჯერ ვერ ჩაიტვირთა.</p>
        </div>
      ) : null}

      {hasRows ? (
        <>
          <div className="charts-grid">
            <div className="chart-card">
              <div className="chart-card-header">
                <h3>TOP მომწოდებლები</h3>
                <span className="chart-card-header-desc">თანხით დალაგებული</span>
              </div>
              <div className="imported-ranking-list">
                {topSuppliers.map((item, index) => (
                  <div className="imported-ranking-item" key={`${item.supplier || 'supplier'}-${index}`}>
                    <div className="imported-ranking-main">
                      <span className="imported-ranking-rank">{index + 1}</span>
                      <div className="imported-ranking-text">
                        <div className="imported-ranking-title">{item.supplier || 'უცნობი მომწოდებელი'}</div>
                        <div className="imported-ranking-meta">
                          {formatCount(item.distinct_waybill_count)} ზედნადები · {formatCount(item.row_count)} ხაზი
                        </div>
                      </div>
                    </div>
                    <div className="imported-ranking-side">
                      <div className="imported-ranking-amount amount-neutral">{formatMoney(item.total_ge)}</div>
                    </div>
                  </div>
                ))}
                {topSuppliers.length === 0 ? (
                  <div className="taxonomy-preview-empty">TOP მომწოდებლები ჯერ არ არის.</div>
                ) : null}
              </div>
            </div>

            <div className="chart-card">
              <div className="chart-card-header">
                <h3>TOP პროდუქტები</h3>
                <span className="chart-card-header-desc">თანხით დალაგებული</span>
              </div>
              <div className="imported-ranking-list">
                {topProducts.map((item, index) => (
                  <div className="imported-ranking-item" key={`${item.product_code || item.product_name || 'product'}-${index}`}>
                    <div className="imported-ranking-main">
                      <span className="imported-ranking-rank">{index + 1}</span>
                      <div className="imported-ranking-text">
                        <div className="imported-ranking-title">
                          {item.product_name || item.product_code || 'უცნობი პროდუქცია'}
                        </div>
                        <div className="imported-ranking-meta">
                          {item.product_code ? <span className="imported-product-code">{item.product_code}</span> : null}
                          {formatCount(item.distinct_waybill_count)} ზედნადები
                          {item.unit ? ` · ${formatQuantity(item.quantity)} ${item.unit}` : ''}
                        </div>
                      </div>
                    </div>
                    <div className="imported-ranking-side">
                      <div className="imported-ranking-amount amount-neutral">{formatMoney(item.total_ge)}</div>
                    </div>
                  </div>
                ))}
                {topProducts.length === 0 ? (
                  <div className="taxonomy-preview-empty">TOP პროდუქტები ჯერ არ არის.</div>
                ) : null}
              </div>
            </div>

            <div className="chart-card">
              <div className="chart-card-header">
                <h3>სტატუსების შეჯამება</h3>
                <span className="chart-card-header-desc">row count + თანხის წილი</span>
              </div>
              <div className="table-wrapper cashflow-table">
                <table>
                  <thead>
                    <tr>
                      <th>სტატუსი</th>
                      <th>ხაზი</th>
                      <th>ჯამი</th>
                      <th>წილი</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byStatus.map((item) => (
                      <tr key={item.status}>
                        <td>
                          <span className={statusBadgeClass(item.status)}>{item.status}</span>
                        </td>
                        <td>{formatCount(item.row_count)}</td>
                        <td className="amount-neutral">{formatMoney(item.total_ge)}</td>
                        <td>{shareText(item.total_ge, overall.total_amount_ge)}</td>
                      </tr>
                    ))}
                    {byStatus.length === 0 ? (
                      <tr>
                        <td colSpan="4" style={{ textAlign: 'center' }}>
                          სტატუსების შეჯამება ჯერ არ არის.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="chart-card">
              <div className="chart-card-header">
                <h3>თვეების ჭრილი</h3>
                <span className="chart-card-header-desc">ბოლო 12 ცნობილი თვე</span>
              </div>
              <div className="imported-month-list">
                {recentMonths.map((item) => (
                  <div className="imported-month-row" key={item.month}>
                    <div className="imported-month-head">
                      <span className="imported-month-label">{item.month}</span>
                      <span className="imported-month-stats">
                        {formatMoney(item.total_ge)} · {formatCount(item.row_count)} ხაზი
                      </span>
                    </div>
                    <div className="imported-month-bar">
                      <div
                        className="imported-month-bar-fill"
                        style={{ width: monthBarWidth(item.total_ge, maxRecentMonthTotal) }}
                      />
                    </div>
                  </div>
                ))}
                {recentMonths.length === 0 ? (
                  <div className="taxonomy-preview-empty">თვეების breakdown ჯერ არ არის.</div>
                ) : null}
              </div>
              {unknownMonth ? (
                <p className="chart-desc imported-month-footnote">
                  უცნობი თვე: {formatMoney(unknownMonth.total_ge)} · {formatCount(unknownMonth.row_count)} ხაზი
                </p>
              ) : null}
            </div>
          </div>

          {topPairs.length > 0 ? (
            <div className="chart-card chart-card--wide">
              <div className="chart-card-header">
                <h3>დომინანტური მომწოდებელი-პროდუქტი წყვილები</h3>
                <span className="chart-card-header-desc">TOP 20 ყველაზე მსხვილი მიწოდების ხაზი</span>
              </div>
              <div className="table-wrapper cashflow-table">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>მომწოდებელი</th>
                      <th>პროდუქტი</th>
                      <th>კოდი</th>
                      <th>ჯამი</th>
                      <th>რაოდენობა</th>
                      <th>ზედნადები</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topPairs.slice(0, 20).map((item, index) => (
                      <tr key={`pair-${index}`}>
                        <td>{index + 1}</td>
                        <td style={{ fontWeight: 600, color: '#e2e8f0' }}>{item.supplier || '—'}</td>
                        <td>{item.product_name || '—'}</td>
                        <td>{item.product_code || '—'}</td>
                        <td className="amount-neutral">{formatMoney(item.total_amount_ge || item.total_ge)}</td>
                        <td>{item.quantity ? `${formatQuantity(item.quantity)} ${item.unit || ''}` : '—'}</td>
                        <td>{formatCount(item.distinct_waybill_count)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          <div className="chart-card chart-card--wide imported-products-card">
            <div className="chart-card-header">
              <h3>პროდუქტების reference სია</h3>
              <span className="chart-card-header-desc">
                სრული სია ფილტრის მიხედვით (თანხით დალაგებული მონაცემიდან)
              </span>
            </div>

            <div className="controls controls-filters imported-products-controls">
              <label className="filter-field">
                <span className="filter-label">პროდუქტი / კოდი</span>
                <input
                  type="text"
                  className="search-input search-input-compact"
                  placeholder="დასახელება ან კოდი..."
                  value={productQuery}
                  onChange={(e) => setProductQuery(e.target.value)}
                  autoComplete="off"
                />
              </label>
              <div className="imported-products-count">
                ნაპოვნია {formatCount(filteredProducts.length)} პროდუქტი
              </div>
            </div>

            <div className="table-wrapper cashflow-table">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>პროდუქტი</th>
                    <th>კოდი</th>
                    <th>ჯამი</th>
                    <th>მომწოდებლები</th>
                    <th>კონცენტრაცია (TOP მომწ.)</th>
                    <th>ზედნადები</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleProducts.map((item, index) => {
                    const sharePct = Number(item.top_supplier_share_pct) || 0;
                    const conc = concentrationBadge(sharePct);
                    return (
                      <tr key={`${item.product_code || item.product_name || 'prod'}-${index}`}>
                        <td>{index + 1}</td>
                        <td>{item.product_name || 'უცნობი პროდუქტი'}</td>
                        <td>{item.product_code || '—'}</td>
                        <td className="amount-neutral">{formatMoney(item.total_amount_ge || item.total_ge)}</td>
                        <td>{formatCount(item.distinct_supplier_count)}</td>
                        <td>
                          {item.distinct_supplier_count > 0 ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span className={conc.className} title={`TOP მომწოდებელს მიაქვს ${sharePct.toFixed(1)}%`}>
                                {conc.label}
                              </span>
                              <span className="kpi-sub" style={{ margin: 0 }}>{sharePct.toFixed(0)}%</span>
                            </div>
                          ) : '—'}
                        </td>
                        <td>{formatCount(item.distinct_waybill_count)}</td>
                      </tr>
                    );
                  })}
                  {visibleProducts.length === 0 ? (
                    <tr>
                      <td colSpan="7" style={{ textAlign: 'center' }}>
                        ასეთი პროდუქტი ვერ მოიძებნა.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>

            <div className="imported-table-note">
              ძებნა ცარიელია — ნაჩვენებია სრული პროდუქტების სია (თანხით დალაგებული).
            </div>
          </div>

          <div className="chart-card chart-card--wide imported-suppliers-card">
            <div className="chart-card-header">
              <h3>მომწოდებლების reference სია</h3>
              <span className="chart-card-header-desc">
                სრული სია ფილტრის მიხედვით (თანხით დალაგებული მონაცემიდან)
              </span>
            </div>

            <div className="controls controls-filters imported-products-controls">
              <label className="filter-field">
                <span className="filter-label">მომწოდებელი / ID</span>
                <input
                  type="text"
                  className="search-input search-input-compact"
                  placeholder="სახელი ან საიდენტიფიკაციო..."
                  value={supplierQuery}
                  onChange={(e) => setSupplierQuery(e.target.value)}
                  autoComplete="off"
                />
              </label>
              <div className="imported-products-count">
                ნაპოვნია {formatCount(filteredSuppliers.length)} supplier
              </div>
            </div>

            <div className="table-wrapper cashflow-table">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>მომწოდებელი</th>
                    <th>ID</th>
                    <th>ჯამი</th>
                    <th>პროდუქტი</th>
                    <th>ზედნადები</th>
                    <th>პერიოდი</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleSuppliers.map((item, index) => (
                    <tr key={`${item.tax_id || item.supplier || 'supplier'}-${index}`}>
                      <td>{index + 1}</td>
                      <td>{item.supplier || 'უცნობი მომწოდებელი'}</td>
                      <td>{item.tax_id || '—'}</td>
                      <td className="amount-neutral">{formatMoney(item.total_amount_ge)}</td>
                      <td>{formatCount(item.distinct_product_count)}</td>
                      <td>{formatCount(item.distinct_waybill_count)}</td>
                      <td>{formatDateRange(item.date_range)}</td>
                    </tr>
                  ))}
                  {visibleSuppliers.length === 0 ? (
                    <tr>
                      <td colSpan="7" style={{ textAlign: 'center' }}>
                        ასეთი მომწოდებელი ვერ მოიძებნა.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>

            <div className="imported-table-note">
              ძებნა ცარიელია — ნაჩვენებია სრული მომწოდებლების სია (თანხით დალაგებული).
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
