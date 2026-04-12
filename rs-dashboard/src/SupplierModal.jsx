import { useEffect, useMemo, useState } from 'react';

const GEL = new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL', maximumFractionDigits: 0 });
const COUNT = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 0 });
const QUANTITY = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 2 });
const fmt = (v) => GEL.format(Number(v) || 0);
const fmtCount = (v) => COUNT.format(Number(v) || 0);
const fmtQuantity = (v) => QUANTITY.format(Number(v) || 0);

const OBJECT_COLORS = { 'ოზურგეთი': '#4f8ef7', 'დვაბზუ': '#34c97e' };

const PAYMENT_SCOPE_META = {
  strict_bank_plus_manual: {
    label: 'Strict + manual',
    className: 'payment-scope-badge--split',
  },
  strict_bank_only: {
    label: 'Strict bank only',
    className: 'payment-scope-badge--strict',
  },
  manual_only: {
    label: 'Manual only',
    className: 'payment-scope-badge--manual',
  },
  unpaid_or_unmatched: {
    label: 'No paid proof',
    className: 'payment-scope-badge--unpaid',
  },
  negative_adjustment: {
    label: 'Negative adj.',
    className: 'payment-scope-badge--negative',
  },
};

const TRUTH_LAYER_LABELS = {
  'bank.raw_tax_id': 'raw tax id',
  'bank.extracted_tax_id': 'extracted tax id',
  'supplier_matching_registry.official_name': 'registry official name',
  'supplier_matching_registry.alias': 'registry alias',
  'supplier_matching_registry.person_alias': 'registry person alias',
  'supplier_matching_registry.iban': 'registry IBAN',
  'supplier_matching_registry.account_hint': 'registry account hint',
  'rs_waybills.organization_name': 'RS exact name',
  'rs_waybills.waybill_reference': 'RS waybill reference',
  'legacy_truth_assist.partner_iban_map': 'legacy IBAN audit-only',
  'legacy_truth_assist.known_aliases': 'legacy alias audit-only',
};

function getPaymentScopeMeta(scope) {
  return PAYMENT_SCOPE_META[String(scope || '').trim()] || {
    label: String(scope || 'Unknown scope'),
    className: 'payment-scope-badge--unpaid',
  };
}

function getOfficialNameSourceMeta(source) {
  const raw = String(source || '').trim();
  if (raw === 'supplier_matching_registry.official_name') {
    return { label: 'Registry primary', className: 'truth-source-badge--registry' };
  }
  if (raw === 'rs_waybills.organization_name') {
    return { label: 'RS backstop', className: 'truth-source-badge--rs' };
  }
  if (raw.startsWith('legacy_truth_assist.')) {
    return { label: 'Legacy audit-only', className: 'truth-source-badge--legacy' };
  }
  if (raw) {
    return { label: 'Other source', className: 'truth-source-badge--other' };
  }
  return { label: 'Truth pending', className: 'truth-source-badge--other' };
}

function normalizeTruthSources(raw) {
  if (Array.isArray(raw)) {
    return raw.map((value) => String(value || '').trim()).filter(Boolean);
  }
  const text = String(raw || '').trim();
  return text ? [text] : [];
}

function formatTruthLayerLabel(source) {
  return TRUTH_LAYER_LABELS[source] || source;
}

function buildTruthBoundaryBadges(summary) {
  return [
    {
      key: 'registry',
      label: `registry primary ${Number(summary?.registry_primary_supplier_count) || 0}`,
      className: 'truth-source-badge--registry',
    },
    {
      key: 'rs',
      label: `RS backstop ${Number(summary?.rs_backstop_supplier_count) || 0}`,
      className: 'truth-source-badge--rs',
    },
    {
      key: 'legacy',
      label: `legacy audit-only ${Number(summary?.legacy_truth_assist_supplier_count) || 0}`,
      className: 'truth-source-badge--legacy',
    },
  ];
}

function agingBadgeClass(bucket) {
  const map = { '0-30': 'aging-0-30', '31-60': 'aging-31-60', '61-90': 'aging-61-90', '91-180': 'aging-91-180', '180+': 'aging-180-plus' };
  return map[String(bucket)] || 'aging-0-30';
}

function paymentColor(pct) {
  if (pct >= 90) return '#22c55e';
  if (pct >= 70) return '#eab308';
  return '#ef4444';
}

function extractTaxIdFromOrg(org) {
  const m = String(org || '').match(/\((\d+)/);
  return m ? m[1] : null;
}

function cleanSupplierDisplay(value) {
  const text = String(value || '').trim();
  if (!text) return '';

  let cleaned = text;
  // Full RS/tax prefix in parentheses, e.g. "(406181616-დღგ)" or "(406181616)" — must run before bare-ID replace
  cleaned = cleaned.replace(/^\(\d{8,11}[^)]*\)\s*/, '');
  // Remnants when only the numeric id was stripped and "-დღგ)" was left behind
  cleaned = cleaned.replace(/^\([^)]*დღგ\)\s*/u, '');
  for (const taxId of cleaned.match(/\d{8,11}/g) || []) {
    cleaned = cleaned.replace(new RegExp(`\\(?\\s*${taxId}\\s*\\)?`, 'g'), ' ');
  }
  cleaned = cleaned.replace(/\s+/g, ' ').trim();
  cleaned = cleaned.replace(/^[\s\-–,]+|[\s\-–,]+$/g, '');
  return cleaned || text;
}

function normalizeSupplierName(value) {
  let text = cleanSupplierDisplay(value).toLowerCase().trim();
  if (!text) return '';
  text = text.replace(/["'„«»()[\]]/g, '');
  text = text.replace(/^(შპს|სს|ი\/მ|ი\.მ|შ\.პ\.ს)\s*/g, '').trim();
  text = text.replace(/\s+/g, ' ').trim();
  text = text.replace(/-დღგ$/g, '').trim();
  return text;
}

function formatDateRange(range) {
  const min = range?.min || null;
  const max = range?.max || null;
  if (min && max) return min === max ? min : `${min} - ${max}`;
  return min || max || '—';
}

export default function SupplierModal({
  supplier,
  agingData: initialAgingData,
  truthBoundarySummary,
  onClose,
}) {
  const [fetchedAging, setFetchedAging] = useState(null);
  const [agingLoading, setAgingLoading] = useState(!initialAgingData || initialAgingData.length === 0);
  const [importedResult, setImportedResult] = useState({ key: '', detail: null, error: '' });

  useEffect(() => {
    if (initialAgingData && initialAgingData.length > 0) {
      setTimeout(() => setAgingLoading(false), 0);
      return;
    }
    
    let active = true;
    setTimeout(() => {
      if (active) setAgingLoading(true);
    }, 0);
    
    fetch('/api/data?tab=working_capital')
      .then(res => res.json())
      .then(json => {
        if (!active) return;
        setFetchedAging(json.supplier_aging || []);
        setAgingLoading(false);
      })
      .catch(err => {
        if (!active) return;
        console.error('Failed to fetch aging data:', err);
        setAgingLoading(false);
      });
      
    return () => {
      active = false;
    };
  }, [initialAgingData]);

  const agingData = (initialAgingData && initialAgingData.length > 0) ? initialAgingData : (fetchedAging || []);
  const supplierOrg = supplier?.['ორგანიზაცია'] || supplier?.org || '';
  const supplierFallbackName = supplier?.supplier || '';
  const org = supplierOrg || supplierFallbackName || '—';
  const displayOrg = cleanSupplierDisplay(org) || String(org).replace(/^\(\d+.*?\)\s*/, '') || '—';
  const taxId = supplier ? String(supplier.tax_id || extractTaxIdFromOrg(org) || '').trim() || null : null;
  const normalizedSupplier = useMemo(
    () => normalizeSupplierName(supplierOrg || supplierFallbackName),
    [supplierFallbackName, supplierOrg],
  );
  const importedLookupKey = `${taxId || ''}::${normalizedSupplier || ''}`;

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ tab: 'imported_products_supplier_detail' });
    if (taxId) params.set('tax_id', taxId);
    if (normalizedSupplier) params.set('normalized_supplier', normalizedSupplier);

    fetch(`/api/data?${params.toString()}`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((json) => {
        setImportedResult({
          key: importedLookupKey,
          detail: json.imported_products_supplier_detail || {},
          error: '',
        });
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        console.error('Failed to fetch imported products supplier detail:', err);
        setImportedResult({
          key: importedLookupKey,
          detail: null,
          error: err.message || 'უცნობი შეცდომა',
        });
      });

    return () => controller.abort();
  }, [importedLookupKey, normalizedSupplier, taxId]);

  const importedDetail = importedResult.key === importedLookupKey ? importedResult.detail : null;
  const importedError = importedResult.key === importedLookupKey ? importedResult.error : '';
  const importedLoading = Boolean(importedLookupKey) && importedResult.key !== importedLookupKey;
  const importedEntry = importedDetail?.entry || null;
  const importedTopProducts = Array.isArray(importedEntry?.top_products) ? importedEntry.top_products : [];
  const importedHasSource = Boolean(importedDetail?.has_source);
  const importedTopLimit = Number(importedDetail?.supplier_top_products_limit) || 0;
  const importedSectionTitle = importedDetail?.label_ka || 'შემოტანილი პროდუქცია (reference)';

  const aging = agingData?.find((r) => {
    if (taxId && r.tax_id && String(r.tax_id) === String(taxId)) return true;
    const rOrg = String(r.org || '').trim();
    const sOrg = String(supplier?.['ორგანიზაცია'] || supplier?.org || supplier?.supplier || '').trim();
    return rOrg && sOrg && rOrg === sOrg;
  });

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  if (!supplier) return null;

  const effective = Number(supplier.total_effective ?? aging?.total_effective) || 0;
  const paid = Number(supplier.total_paid ?? aging?.total_paid) || 0;
  const debt = Number(supplier.total_debt ?? aging?.total_debt) || 0;
  const days = Number(aging?.days_since_last) || 0;
  const lastDate = aging?.last_waybill_date || '—';
  const agingBucket = aging?.aging_bucket;
  const obj = aging?.object || supplier.object;
  const strictBankPaid = Number(supplier.strict_bank_paid ?? aging?.strict_bank_paid) || 0;
  const manualPaid = Number(supplier.manual_paid ?? aging?.manual_paid) || 0;
  const paymentScopeRaw =
    String(supplier.payment_scope || aging?.payment_scope || '').trim() || 'unpaid_or_unmatched';
  const paymentScopeNote = String(
    supplier.payment_scope_note || aging?.payment_scope_note || '',
  ).trim();
  const paymentScopeMeta = getPaymentScopeMeta(paymentScopeRaw);
  const supplierTruthSummary = String(
    supplier.supplier_truth_summary || aging?.supplier_truth_summary || '',
  ).trim();
  const officialNameTruthSource = String(
    supplier.official_name_truth_source || aging?.official_name_truth_source || '',
  ).trim();
  const officialNameSourceMeta = getOfficialNameSourceMeta(officialNameTruthSource);
  const supplierTruthSources = normalizeTruthSources(
    supplier.supplier_truth_sources ?? aging?.supplier_truth_sources,
  );
  const truthBoundaryBadges = buildTruthBoundaryBadges(truthBoundarySummary);
  const truthBoundarySummaryText = String(truthBoundarySummary?.summary_ka || '').trim();
  const paymentRatioRaw = effective > 0 ? (paid / effective) * 100 : 0;
  const paymentRatio = Math.min(100, paymentRatioRaw);
  const prColor = paymentColor(paymentRatio);
  const waybillCount = Number(aging?.waybill_count ?? supplier.waybills_count ?? supplier.waybill_count) || 0;
  let importedStatusClass = 'badge muted';
  let importedStatusLabel = 'იტვირთება...';

  if (!importedLoading) {
    if (importedError) {
      importedStatusClass = 'badge canceled';
      importedStatusLabel = 'შეცდომა';
    } else if (importedEntry && importedDetail?.match_type === 'tax_id') {
      importedStatusClass = 'badge active';
      importedStatusLabel = 'ნაპოვნია (ID)';
    } else if (importedEntry) {
      importedStatusClass = 'badge return';
      importedStatusLabel = 'ნაპოვნია (სახელით)';
    } else if (!importedHasSource) {
      importedStatusClass = 'badge muted';
      importedStatusLabel = 'წყარო ცარიელია';
    } else if (importedDetail?.ambiguous) {
      importedStatusClass = 'badge return';
      importedStatusLabel = 'რამდენიმე შესაძლო დამთხვევა';
    } else {
      importedStatusClass = 'badge canceled';
      importedStatusLabel = 'ვერ მოიძებნა';
    }
  }

  return (
    <>
      <div className="supplier-modal-backdrop" onClick={onClose} />
      <div className="supplier-modal" role="dialog" aria-modal="true" aria-labelledby="supplier-modal-title">
        <button type="button" className="supplier-modal-close" onClick={onClose} aria-label="დახურვა">✕</button>

        {/* Header */}
        <div className="supplier-modal-header">
          <div className="supplier-modal-org" id="supplier-modal-title">{displayOrg}</div>
          {taxId && <div className="supplier-modal-taxid">ID: {taxId}</div>}
          {waybillCount > 0 && <div className="supplier-modal-taxid">{waybillCount} ზედნადები</div>}
        </div>

        {/* 3 KPI */}
        <div className="supplier-modal-kpis">
          <div className="supplier-modal-kpi">
            <div className="kpi-label">რეალური ჯამი</div>
            <div className="kpi-value amount-neutral" style={{ fontSize: '1.2rem' }}>{fmt(effective)}</div>
          </div>
          <div className="supplier-modal-kpi">
            <div className="kpi-label">სულ გადახდილი</div>
            <div className="kpi-value amount-positive" style={{ fontSize: '1.2rem' }}>{fmt(paid)}</div>
          </div>
          <div className="supplier-modal-kpi">
            <div className="kpi-label">დავალიანება</div>
            <div className="kpi-value amount-negative" style={{ fontSize: '1.2rem' }}>{fmt(debt)}</div>
          </div>
        </div>

        <div className="supplier-modal-section">
          <div className="supplier-modal-section-title">Payment split</div>
          <div className="supplier-modal-split-grid">
            <div className="supplier-modal-split-card supplier-modal-split-card--strict">
              <div className="supplier-modal-split-label">Strict ბანკი</div>
              <div className="supplier-modal-split-value amount-positive">{fmt(strictBankPaid)}</div>
            </div>
            <div className="supplier-modal-split-card supplier-modal-split-card--manual">
              <div className="supplier-modal-split-label">Manual / off-bank</div>
              <div className="supplier-modal-split-value amount-neutral">{fmt(manualPaid)}</div>
            </div>
            <div className="supplier-modal-split-card supplier-modal-split-card--combined">
              <div className="supplier-modal-split-label">Supplier total_paid</div>
              <div className="supplier-modal-split-value amount-positive">{fmt(paid)}</div>
            </div>
          </div>
          <div className="supplier-modal-row">
            <span className="supplier-modal-row-label">გადახდის scope</span>
            <span
              className={`badge payment-scope-badge ${paymentScopeMeta.className}`}
              title={paymentScopeRaw}
            >
              {paymentScopeMeta.label}
            </span>
          </div>
          {paymentScopeNote ? (
            <div className="supplier-modal-note">{paymentScopeNote}</div>
          ) : null}
        </div>

        {/* Aging info */}
        <div className="supplier-modal-section">
          <div className="supplier-modal-section-title">Aging {agingLoading && <span style={{ fontSize: '0.8rem', color: '#8899aa', marginLeft: 8 }}>(იტვირთება...)</span>}</div>
          <div className="supplier-modal-row">
            <span className="supplier-modal-row-label">ბოლო ზედნადები</span>
            <span>{agingLoading ? '—' : lastDate}{days > 0 ? ` (${days} დღის წინ)` : ''}</span>
          </div>
          {agingBucket && (
            <div className="supplier-modal-row">
              <span className="supplier-modal-row-label">Aging Bucket</span>
              <span className={`badge ${agingBadgeClass(agingBucket)}`}>{agingBucket}</span>
            </div>
          )}
          <div className="supplier-modal-row">
            <span className="supplier-modal-row-label">Payment Ratio</span>
            <span style={{ color: prColor, fontWeight: 700 }}>{paymentRatio.toFixed(1)}%</span>
          </div>
          <div className="ratio-gauge" style={{ marginTop: 6 }}>
            <div className="ratio-gauge-fill" style={{ width: `${paymentRatio}%`, background: prColor }} />
          </div>
        </div>

        {/* Object */}
        {obj && (
          <div className="supplier-modal-section">
            <div className="supplier-modal-section-title">ობიექტი</div>
            <span className="badge" style={{
              background: `${OBJECT_COLORS[obj] || '#8899aa'}22`,
              color: OBJECT_COLORS[obj] || '#8899aa',
              border: `1px solid ${OBJECT_COLORS[obj] || '#8899aa'}55`,
            }}>
              {obj}
            </span>
          </div>
        )}

        <div className="supplier-modal-section">
          <div className="supplier-modal-section-title">Strict supplier truth</div>
          <div className="supplier-modal-row">
            <span className="supplier-modal-row-label">Official name source</span>
            <span
              className={`badge truth-source-badge ${officialNameSourceMeta.className}`}
              title={officialNameTruthSource || officialNameSourceMeta.label}
            >
              {officialNameSourceMeta.label}
            </span>
          </div>

          {supplierTruthSummary ? (
            <div className="supplier-modal-note supplier-modal-note--truth">
              {supplierTruthSummary}
            </div>
          ) : (
            <div className="supplier-modal-note">
              Strict truth summary ამ supplier-ზე ჯერ ცალკე არ ჩანს.
            </div>
          )}

          {supplierTruthSources.length > 0 ? (
            <div className="supplier-modal-chip-row">
              {supplierTruthSources.map((source, i) => (
                <span
                  key={`truth-src-${i}-${String(source)}`}
                  className="badge truth-layer-chip"
                  title={source}
                >
                  {formatTruthLayerLabel(source)}
                </span>
              ))}
            </div>
          ) : null}

          <div className="supplier-modal-chip-row">
            {truthBoundaryBadges.map((item) => (
              <span key={item.key} className={`badge truth-source-badge ${item.className}`}>
                {item.label}
              </span>
            ))}
          </div>

          {truthBoundarySummaryText ? (
            <div className="supplier-modal-note">{truthBoundarySummaryText}</div>
          ) : null}
        </div>

        <div className="supplier-modal-section">
          <div className="supplier-modal-section-title">
            {importedSectionTitle}
            {importedLoading && <span className="supplier-modal-section-hint"> (იტვირთება...)</span>}
          </div>
          <div className="supplier-modal-row">
            <span className="supplier-modal-row-label">Reference ჩანაწერი</span>
            <span className={importedStatusClass}>{importedStatusLabel}</span>
          </div>

          {importedEntry && (
            <>
              <div className="supplier-modal-row">
                <span className="supplier-modal-row-label">სულ თანხა</span>
                <span className="amount-neutral">{fmt(importedEntry.total_amount_ge)}</span>
              </div>
              <div className="supplier-modal-row">
                <span className="supplier-modal-row-label">პროდუქტი</span>
                <span>{fmtCount(importedEntry.distinct_product_count)}</span>
              </div>
              <div className="supplier-modal-row">
                <span className="supplier-modal-row-label">ზედნადები</span>
                <span>{fmtCount(importedEntry.distinct_waybill_count)}</span>
              </div>
              <div className="supplier-modal-row">
                <span className="supplier-modal-row-label">პერიოდი</span>
                <span>{formatDateRange(importedEntry.date_range)}</span>
              </div>
            </>
          )}

          {!importedLoading && !importedError && (
            <div className="supplier-modal-note">
              Reference-only ბლოკია; supplier debt/AP ჯამებში არ შედის და სრული სურათი შეიძლება არ იყოს.
            </div>
          )}

          {!importedLoading && !importedError && importedDetail?.match_type === 'name_fallback' && (
            <div className="supplier-modal-note supplier-modal-note--warn">
              ID-ით არა, სახელის ზუსტი ნორმალიზაციით დაემთხვა. გადაამოწმე ხელით.
            </div>
          )}

          {!importedLoading && !importedError && importedDetail?.ambiguous && !importedEntry && (
            <div className="supplier-modal-note supplier-modal-note--warn">
              სახელით რამდენიმე შესაძლო დამთხვევა გამოჩნდა, ამიტომ ჩანაწერი არ ვაჩვენე.
            </div>
          )}

          {!importedLoading && !importedError && !importedHasSource && (
            <div className="supplier-modal-note">
              Imported-products reference წყარო ამ ეტაპზე ცარიელია.
            </div>
          )}

          {!importedLoading && !importedError && importedDetail?.truncation_suspected_any && (
            <div className="supplier-modal-note supplier-modal-note--warn">
              ზოგ ფაილში truncate/export limit სავარაუდოა, ამიტომ ეს ბლოკი შეიძლება არასრული იყოს.
            </div>
          )}

          {importedError && (
            <div className="supplier-modal-note supplier-modal-note--error">
              Imported-products ბლოკის ჩატვირთვა ვერ მოხერხდა: {importedError}
            </div>
          )}

          {importedEntry && (
            <>
              <div className="supplier-modal-section-title" style={{ marginTop: 8 }}>
                Top პროდუქტები
                {importedTopLimit > 0 && (
                  <span className="supplier-modal-section-hint"> (max {importedTopLimit})</span>
                )}
              </div>
              {importedTopProducts.length > 0 ? (
                <div className="supplier-modal-products">
                  {importedTopProducts.map((product, index) => (
                    <div
                      key={`${product.product_code || product.product_name || 'product'}-${index}`}
                      className="supplier-modal-product"
                    >
                      <div className="supplier-modal-product-top">
                        <span className="supplier-modal-product-name">
                          {product.product_name || product.product_code || 'უცნობი პროდუქცია'}
                        </span>
                        <span className="supplier-modal-product-amount amount-neutral">
                          {fmt(product.total_amount_ge)}
                        </span>
                      </div>
                      <div className="supplier-modal-product-meta">
                        {product.product_code ? (
                          <span className="supplier-modal-product-code">{product.product_code}</span>
                        ) : null}
                        {product.unit ? <span>{product.unit}</span> : null}
                        <span>{fmtCount(product.distinct_waybill_count)} ზედნადები</span>
                        <span>
                          {fmtQuantity(product.total_quantity)}
                          {product.unit ? ` ${product.unit}` : ''}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="supplier-modal-muted">Top პროდუქტები არ არის.</div>
              )}
            </>
          )}
        </div>

        <button type="button" className="supplier-modal-close-btn" onClick={onClose}>
          დახურვა
        </button>
      </div>
    </>
  );
}
