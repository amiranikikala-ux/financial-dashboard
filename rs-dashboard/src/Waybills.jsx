import { useState, useEffect, useMemo } from 'react';
import { fetchApiJson } from './lib/api.js';
import TrustBanner from './components/TrustBanner.jsx';

const WAYBILL_SORT_OPTIONS = [
  { value: 'amount_asc', label: 'თანხა ზრდით' },
  { value: 'amount_desc', label: 'თანხა კლებით' },
  { value: 'date_desc', label: 'თარიღი ახლიდან' },
  { value: 'date_asc', label: 'თარიღი ძველიდან' },
];

function getWaybillAmount(wb) {
  const effective = Number(wb?.effective_amount);
  if (Number.isFinite(effective)) return effective;
  const nominal = Number(wb?.nominal_amount);
  return Number.isFinite(nominal) ? nominal : 0;
}

const COUNT = new Intl.NumberFormat('ka-GE', {
  maximumFractionDigits: 0,
});

function formatCount(value) {
  return COUNT.format(Number(value) || 0);
}

export default function Waybills({ formatNumber, reloadKey, fromDate, fromTime, toDate, toTime }) {
  const [searchName, setSearchName] = useState('');
  const [waybillSortKey, setWaybillSortKey] = useState('amount_asc');
  const [data, setData] = useState({ waybills: [], waybills_summary: null, response_meta: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const hasActivePeriodFilter = Boolean(fromDate || toDate);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const handle = setTimeout(() => {
      if (!active) return;
      setTimeout(() => {
        if (active) {
          setLoading(true);
          setError(null);
        }
      }, 0);

      const params = new URLSearchParams({
        tab: 'waybills',
        sort: waybillSortKey,
      });
      const needle = searchName.trim();
      if (needle) params.set('q', needle);
      if (hasActivePeriodFilter) {
        params.set('from_date', fromDate || toDate || '');
        params.set('to_date', toDate || fromDate || '');
        params.set('from_time', fromTime || '00:00');
        params.set('to_time', toTime || '23:59');
      }

      fetchApiJson(`/api/data?${params.toString()}`, { signal: controller.signal })
        .then((json) => {
          if (!active) return;
          setData({
            waybills: json.waybills || [],
            waybills_summary: json.waybills_summary || null,
            response_meta: json.response_meta || null,
          });
          setLoading(false);
        })
        .catch((err) => {
          if (!active || err.name === 'AbortError') return;
          console.error('Failed to load waybills:', err);
          setError(err.message);
          setLoading(false);
        });
    }, 600);

    return () => {
      active = false;
      clearTimeout(handle);
      controller.abort();
    };
  }, [fromDate, fromTime, hasActivePeriodFilter, reloadKey, searchName, toDate, toTime, waybillSortKey]);

  const filteredWaybills = useMemo(() => {
    return Array.isArray(data.waybills) ? data.waybills : [];
  }, [data.waybills]);

  const waybillsSummary = data.waybills_summary || {};
  const statusBreakdown = Array.isArray(waybillsSummary.status_breakdown)
    ? waybillsSummary.status_breakdown
    : [];
  const periodMeta = waybillsSummary.period_meta || {};
  const periodLabel = periodMeta.label_ka || (hasActivePeriodFilter ? 'არჩეული პერიოდი' : 'პერიოდი');
  const periodCaveat = data.response_meta?.period_caveat_ka || '';

  if (error) {
    return (
      <div className="local-pay-banner" style={{ background: '#ef4444', color: '#fff' }} role="alert">
        <strong>შეცდომა:</strong> {error}
      </div>
    );
  }

  if (loading) {
    return <div className="loading">იტვირთება ზედნადებები...</div>;
  }

  return (
    <>
      <TrustBanner
        responseMeta={data.response_meta}
        waybillsSummary={waybillsSummary}
        paymentScopeSummary={{}}
        truthBoundarySummary={{}}
        suppliersOnlyJournalOrBank={0}
      />

      <div className="controls controls-filters">
        <label className="filter-field">
          <span className="filter-label">ძებნა</span>
          <input
            type="text"
            className="search-input search-input-compact"
            placeholder="კომპანია ან ზედნადები…"
            value={searchName}
            onChange={(e) => setSearchName(e.target.value)}
            autoComplete="off"
          />
        </label>
        <label className="filter-field">
          <span className="filter-label">სორტი</span>
          <select
            className="pnl-month-select"
            value={waybillSortKey}
            onChange={(e) => setWaybillSortKey(e.target.value)}
          >
            {WAYBILL_SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Tab Hero */}
      <div className="tab-hero">
        <span className="tab-hero-title">📄 ზედნადებები</span>
        <span className="tab-hero-desc">
          RS ზედნადებების დეტალური სია · {periodMeta.applied ? periodLabel : 'ყველა პერიოდი'}
        </span>
      </div>

      <div className="controls controls-filters" style={{ marginTop: 12, marginBottom: 12 }}>
        <span className="badge muted">პერიოდი: {periodMeta.applied ? periodLabel : 'ყველა პერიოდი'}</span>
        <span className="badge muted">ჩანაწერი: {formatCount(waybillsSummary.total_count || filteredWaybills.length)}</span>
        <span className="badge muted">ნომინალური: {formatNumber(waybillsSummary.total_nominal_amount || 0)}</span>
        <span className="badge muted">ეფექტური: {formatNumber(waybillsSummary.total_effective_amount || 0)}</span>
      </div>

      {statusBreakdown.length > 0 && (
        <div className="controls controls-filters" style={{ marginTop: -4, marginBottom: 16 }}>
          {statusBreakdown.map((item) => (
            <span key={`status-${item.status || 'unknown'}`} className="badge muted">
              {item.status || 'უცნობი'}: {formatCount(item.row_count)}
            </span>
          ))}
        </div>
      )}

      {periodCaveat && (
        <div className="trust-banner-sub trust-banner-sub--warn">
          {periodCaveat}
        </div>
      )}

      <div className="table-wrapper table-premium">
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
            {filteredWaybills.map((wb, idx) => {
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
                    {formatNumber(getWaybillAmount(wb))}
                  </td>
                  <td>
                    <span className={badgeClass}>{badgeText}</span>
                  </td>
                </tr>
              );
            })}
            {waybillsSummary.has_more && (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center', color: 'var(--warning)' }}>
                  ჩაიტვირთა მხოლოდ პირველი {formatCount(waybillsSummary.returned_count || filteredWaybills.length)} ჩანაწერი
                  {' '}({formatCount(waybillsSummary.total_count || filteredWaybills.length)} შედეგიდან)
                </td>
              </tr>
            )}
            {filteredWaybills.length === 0 && (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center' }}>
                  {periodMeta.applied
                    ? `არჩეულ პერიოდში ჩანაწერები ვერ მოიძებნა${searchName.trim() ? ' მოცემული ძებნისთვის' : ''}`
                    : 'მონაცემები არ მოიძებნა'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
