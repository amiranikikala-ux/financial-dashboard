import CollapsibleSection from './components/CollapsibleSection.jsx';
import ExportButton from './components/ExportButton.jsx';

const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 0,
});

const NUM = new Intl.NumberFormat('ka-GE', {
  maximumFractionDigits: 2,
});

const INT = new Intl.NumberFormat('ka-GE', {
  maximumFractionDigits: 0,
});

const asArray = (value) => (Array.isArray(value) ? value : []);
const toNum = (value) => Number(value) || 0;
const fmtMoney = (value) => GEL.format(toNum(value));
const fmtNum = (value) => NUM.format(toNum(value));
const fmtInt = (value) => INT.format(toNum(value));
const fmtPct = (value) => `${toNum(value).toFixed(2)}%`;

function renderMoneyClass(value) {
  if (toNum(value) >= 0) return 'amount-positive';
  return 'amount-negative';
}

function renderDateRange(range) {
  const min = range?.min || '—';
  const max = range?.max || '—';
  return `${min} → ${max}`;
}

export default function RetailSales({ retailSales, responseMeta }) {
  const summary = retailSales && typeof retailSales === 'object' ? retailSales : null;

  if (!summary) {
    return (
      <div className="cashflow-page pnl-empty">
        <div className="kpi-card" style={{ maxWidth: 520, margin: '48px auto', textAlign: 'center' }}>
          <div className="kpi-label">Retail Sales summary ჯერ არ არის</div>
          <div className="kpi-sub" style={{ marginTop: 12 }}>
            გაუშვი ტერმინალში:
          </div>
          <code className="pnl-code-hint">python generate_dashboard_data.py</code>
        </div>
      </div>
    );
  }

  const overall = summary.overall || {};
  const periodMeta = summary.period_meta && typeof summary.period_meta === 'object'
    ? summary.period_meta
    : {};
  const byObject = asArray(summary.by_object);
  const byMonth = asArray(summary.by_month);
  const topCategoriesByProfit = asArray(summary.top_categories_by_profit).slice(0, 12);
  const topProductsByRevenue = asArray(summary.top_products_by_revenue).slice(0, 12);
  const topProductsByProfit = asArray(summary.top_products_by_profit).slice(0, 12);
  const duplicatePolicy =
    summary.duplicate_policy && typeof summary.duplicate_policy === 'object'
      ? summary.duplicate_policy
      : {};
  const suspectedFiles = asArray(duplicatePolicy.suspected_files);
  const categoriesShown = asArray(summary.by_category).length;
  const productsShown = asArray(summary.by_product).length;
  const hasRows =
    toNum(overall.row_count) > 0 || byObject.length > 0 || byMonth.length > 0;
  const periodLabel = periodMeta.label_ka || (periodMeta.applied ? 'არჩეული პერიოდი' : 'ყველა პერიოდი');
  const periodCaveat = responseMeta?.period_caveat_ka || '';

  if (!hasRows) {
    return (
      <div className="cashflow-page pnl-empty">
        <div className="kpi-card" style={{ maxWidth: 560, margin: '48px auto', textAlign: 'center' }}>
          <div className="kpi-label">
            {periodMeta.applied ? 'არჩეულ პერიოდში Retail Sales არ მოიძებნა' : 'Retail Sales წყარო ცარიელია'}
          </div>
          <div className="kpi-sub" style={{ marginTop: 10 }}>
            {periodMeta.applied ? `ფილტრი: ${periodLabel}` : 'გადაამოწმე ფაილები:'}
          </div>
          {periodMeta.applied ? (
            <div className="chart-desc" style={{ marginTop: 12 }}>
              სულ ნანახი: {fmtInt(periodMeta.total_rows_seen)} · დამთხვეული: {fmtInt(periodMeta.matched_rows)}
            </div>
          ) : (
            <>
              <code className="pnl-code-hint">Financial_Analysis/გაყიდული პროდუქტები სოფ დვაბზუ/*.xlsx</code>
              <code className="pnl-code-hint">Financial_Analysis/გაყიდული პროდუქტები სოფ ოზურგეთი/*.xlsx</code>
            </>
          )}
          {periodCaveat ? <div className="chart-desc" style={{ marginTop: 12 }}>{periodCaveat}</div> : null}
        </div>
      </div>
    );
  }

  return (
    <div className="cashflow-page">
      <div className="tab-hero">
        <span className="tab-hero-title">🛒 Retail Sales — summary</span>
        <span className="tab-hero-desc">
          {summary.notes_ka ||
            'დვაბზუ + ოზურგეთი retail sales source: revenue / cost / profit / margin.'}
        </span>
        <ExportButton
          filename={`RetailSales_${new Date().toISOString().slice(0, 10)}.xlsx`}
          sheets={[
            {
              name: 'თვიური',
              rows: byMonth.map((m) => ({
                თვე: m.month || '',
                ობიექტი: m.object || '',
                შემოსავალი: Number(m.revenue) || 0,
                თვითთვალი: Number(m.cost) || 0,
                მოგება: Number(m.profit) || 0,
                margin_pct: Number(m.margin_pct) || 0,
              })),
            },
            {
              name: 'Top Products',
              rows: topProductsByRevenue.map((p) => ({
                პროდუქტი: p.product || '',
                შემოსავალი: Number(p.revenue) || 0,
                მოგება: Number(p.profit) || 0,
              })),
            },
          ]}
        />
      </div>

      <div className="controls controls-filters" style={{ marginTop: 12, marginBottom: 12 }}>
        <span className="badge muted">პერიოდი: {periodMeta.applied ? periodLabel : 'ყველა პერიოდი'}</span>
        <span className="badge muted">ნანახი ხაზები: {fmtInt(periodMeta.total_rows_seen)}</span>
        <span className="badge muted">დამთხვეული: {fmtInt(periodMeta.matched_rows)}</span>
        {toNum(periodMeta.excluded_unparseable_count) > 0 && (
          <span className="badge conf-low">ვერ დაიპარსა: {fmtInt(periodMeta.excluded_unparseable_count)}</span>
        )}
      </div>

      {periodCaveat ? (
        <div className="trust-banner-sub trust-banner-sub--warn">
          {periodCaveat}
        </div>
      ) : null}

      <div className="local-pay-banner imported-products-reference-note" role="note">
        Reference-only წყაროა retail-sales export-იდან. ეს ბლოკი არ ერთვება supplier debt/AP,
        RS truth totals ან bank reconciliation ჯამებში; გამოიყენე როგორც დამატებითი ანალიზის ჭრილი.
      </div>

      <div className="kpi-grid retail-sales-kpi-grid">
        <div className="kpi-card kpi-card--accent">
          <div className="kpi-label">სულ შემოსავალი</div>
          <div className="kpi-value amount-positive">{fmtMoney(overall.revenue_ge)}</div>
          <div className="kpi-sub">retail source revenue</div>
        </div>
        <div className="kpi-card kpi-card--warn">
          <div className="kpi-label">სულ თვითღირებულება</div>
          <div className="kpi-value amount-negative">{fmtMoney(overall.cost_ge)}</div>
          <div className="kpi-sub">retail source cost</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">სულ მოგება</div>
          <div className={`kpi-value ${renderMoneyClass(overall.profit_ge)}`}>
            {fmtMoney(overall.profit_ge)}
          </div>
          <div className="kpi-sub">შემოსავალი - თვითღირებულება</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Gross Margin</div>
          <div className="kpi-value amount-neutral">{fmtPct(overall.gross_margin_pct)}</div>
          <div className="kpi-sub">{fmtInt(overall.distinct_object_count)} ობიექტი</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">ხაზები / რაოდენობა</div>
          <div className="kpi-value amount-neutral">{fmtInt(overall.row_count)}</div>
          <div className="kpi-sub">რაოდ.: {fmtNum(overall.total_quantity)}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">კატეგორია / პროდუქტი</div>
          <div className="kpi-value amount-neutral">
            {fmtInt(overall.distinct_category_count)} / {fmtInt(overall.distinct_product_count)}
          </div>
          <div className="kpi-sub">{renderDateRange(overall.date_range)}</div>
        </div>
      </div>

      <div className="chart-card">
        <h3>Coverage და duplicate policy</h3>
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
                <div className="retail-sales-policy-path">
                  <code>{item.relative_path || 'უცნობი ფაილი'}</code>
                </div>
                <div className="kpi-sub">
                  suspected duplicate of: <code>{item.suspected_duplicate_of || '—'}</code>
                </div>
                {item.reason_ka ? <div className="chart-desc">{item.reason_ka}</div> : null}
              </li>
            ))}
          </ul>
        )}
      </div>

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
                <th>კატეგორია/პროდუქტი</th>
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
              {byObject.length === 0 && (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center' }}>
                    ობიექტების summary ვერ მოიძებნა
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="chart-card">
        <h3>თვიური დინამიკა</h3>
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
              {byMonth.length === 0 && (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center' }}>
                    თვიური summary ცარიელია
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="retail-sales-grid-2">
        <CollapsibleSection
          title="TOP კატეგორიები — მოგებით"
          badge={`${topCategoriesByProfit.length}`}
        >
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
                {topCategoriesByProfit.length === 0 && (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center' }}>
                      TOP კატეგორიები არ არის
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>

        <CollapsibleSection
          title="TOP პროდუქტები — შემოსავლით"
          badge={`${topProductsByRevenue.length}`}
        >
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
                  <tr
                    key={`retail-revenue-${row.product_code || 'na'}-${row.product_name || 'na'}-${toNum(row.revenue_ge)}`}
                  >
                    <td>{row.product_name || 'უცნობი პროდუქტი'}</td>
                    <td>{row.product_code || '—'}</td>
                    <td className="amount-positive">{fmtMoney(row.revenue_ge)}</td>
                    <td className={renderMoneyClass(row.profit_ge)}>{fmtMoney(row.profit_ge)}</td>
                    <td>{fmtPct(row.gross_margin_pct)}</td>
                  </tr>
                ))}
                {topProductsByRevenue.length === 0 && (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center' }}>
                      TOP პროდუქტები არ არის
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      </div>

      <CollapsibleSection
        title="TOP პროდუქტები — მოგებით"
        badge={`${topProductsByProfit.length}`}
      >
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
                <tr
                  key={`retail-profit-${row.product_code || 'na'}-${row.product_name || 'na'}-${toNum(row.profit_ge)}`}
                >
                  <td>{row.product_name || 'უცნობი პროდუქტი'}</td>
                  <td>{row.product_code || '—'}</td>
                  <td>{row.category || '—'}</td>
                  <td className="amount-positive">{fmtMoney(row.revenue_ge)}</td>
                  <td className="amount-negative">{fmtMoney(row.cost_ge)}</td>
                  <td className={renderMoneyClass(row.profit_ge)}>{fmtMoney(row.profit_ge)}</td>
                  <td>{fmtPct(row.gross_margin_pct)}</td>
                </tr>
              ))}
              {topProductsByProfit.length === 0 && (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center' }}>
                    TOP პროდუქტები არ არის
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CollapsibleSection>
    </div>
  );
}
