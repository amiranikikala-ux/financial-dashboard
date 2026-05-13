import { useEffect, useMemo, useState } from 'react';

const GEL = new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL', maximumFractionDigits: 0 });
const GEL_PRECISE = new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL', maximumFractionDigits: 2 });
const COUNT = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 0 });
const QUANTITY = new Intl.NumberFormat('ka-GE', { maximumFractionDigits: 2 });
const fmt = (v) => GEL.format(Number(v) || 0);
const fmtPrecise = (v) => GEL_PRECISE.format(Number(v) || 0);
const fmtCount = (v) => COUNT.format(Number(v) || 0);
const fmtQuantity = (v) => QUANTITY.format(Number(v) || 0);
const fmtPct = (v, decimals = 1) => {
  const n = Number(v);
  if (!isFinite(n)) return '—';
  return `${n.toFixed(decimals)}%`;
};

const OBJECT_COLORS = { 'ოზურგეთი': '#4f8ef7', 'დვაბზუ': '#34c97e' };

// Suppliers paid in cash on each waybill receipt — each waybill needs a
// matching cash entry in the manual journal. UI surfaces ✅/❌ buttons
// per waybill so the owner can confirm payments as goods arrive.
const CASH_ON_RECEIPT_TAX_IDS = new Set(['406181616']); // ჯიდიაი

// მარჟის ფერი — მკვეთრად მაღალი მწვანე, საშუალო ცისფერი, დაბალი ყვითელი, უარყოფითი წითელი.
// "Perfect or silent" — მცირე ცდომილების ფერი (≤2pp 0-დან) ნეიტრალურად.
function marginColor(pct) {
  const n = Number(pct);
  if (!isFinite(n)) return 'var(--text-secondary)';
  if (n >= 15) return '#86efac';
  if (n >= 5) return '#bbf7d0';
  if (n >= 0) return '#fde68a';
  return '#fecaca';
}

const PROFITABILITY_STATUS_META = {
  verified: { label: '✅ ანალიზი დადასტურებულია', tone: 'ok', hint: 'ბარკოდები ემთხვევა MAX-ის ბაზას — რიცხვები 100%-ით სანდოა.' },
  partial: { label: '🟡 ანალიზი ნაწილობრივი', tone: 'mild', hint: 'ნაწილი პროდუქცია ჯერ ვერ დაუკავშირდა MAX-ის ბაზას — ქვემოთ ხედავ რა აკლია.' },
  protected: { label: '🔒 დაცული კატეგორია', tone: 'medium', hint: 'სიგარეტი/ალკოჰოლი — მარჟის ოპტიმიზაციის რჩევები არ მოქმედებს.' },
  unverified: { label: '📋 ჯერ ვერ ანალიზდება', tone: 'muted', hint: 'სუპლაიერი იყენებს შიდა SKU კოდს — საჭიროა ხელით ალიასი.' },
  empty: { label: '— პროდუქცია არ არის შემოტანილი', tone: 'muted', hint: '' },
};

const PAYMENT_SCOPE_KA = {
  strict_bank_plus_manual: { label: 'ბანკი + ნაღდი', className: 'payment-scope-badge--split' },
  strict_bank_only: { label: 'ბანკით დადასტურებული', className: 'payment-scope-badge--strict' },
  manual_only: { label: 'მხოლოდ ნაღდი / ჟურნალი', className: 'payment-scope-badge--manual' },
  unpaid_or_unmatched: { label: 'გადაუხდელი / დაუდგენელი', className: 'payment-scope-badge--unpaid' },
  negative_adjustment: { label: 'უარყოფითი ცვლილება', className: 'payment-scope-badge--negative' },
};

const OFFICIAL_NAME_SOURCE_KA = {
  'supplier_matching_registry.official_name': { label: 'რეესტრი (ოფიციალური)', className: 'truth-source-badge--registry' },
  'rs_waybills.organization_name': { label: 'RS-ის ზედნადები', className: 'truth-source-badge--rs' },
};

const AGING_BUCKET_KA = {
  '0-30': '🟢 0–30 დღე',
  '31-60': '🟡 31–60 დღე',
  '61-90': '🟠 61–90 დღე',
  '91-180': '🔴 91–180 დღე',
  '180+': '🔴 180+ დღე',
};

const URGENCY_BY_BUCKET = {
  '0-30': { tone: 'ok', text: 'ჩვეულებრივი — დროზე ვართ' },
  '31-60': { tone: 'mild', text: 'ყურადღებით — ერთი თვე გავიდა' },
  '61-90': { tone: 'medium', text: 'პრიორიტეტი — 2 თვეზე მეტი გავიდა' },
  '91-180': { tone: 'high', text: 'მაღალი რისკი — 3 თვეზე მეტი ვალი' },
  '180+': { tone: 'critical', text: 'კრიტიკული — ვალი ნახევარ წელზე მეტია გადაუხდელი' },
};

function getPaymentScopeMeta(scope) {
  return PAYMENT_SCOPE_KA[String(scope || '').trim()] || {
    label: 'სტატუსი დაუდგენელი',
    className: 'payment-scope-badge--unpaid',
  };
}

function getOfficialNameSourceMeta(source) {
  const raw = String(source || '').trim();
  if (OFFICIAL_NAME_SOURCE_KA[raw]) return OFFICIAL_NAME_SOURCE_KA[raw];
  if (raw.startsWith('legacy_truth_assist.')) {
    return { label: 'ძველი ბაზიდან (აუდიტისთვის)', className: 'truth-source-badge--legacy' };
  }
  return { label: 'წყარო დაუდგენელი', className: 'truth-source-badge--other' };
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
  cleaned = cleaned.replace(/^\(\d{8,11}[^)]*\)\s*/, '');
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
  if (min && max) return min === max ? min : `${min} → ${max}`;
  return min || max || '—';
}

// ერთი მატჩი (verified product) — top/bottom/dead სიებში გამოიყენება ერთნაირი ფორმით,
// მხოლოდ accent ფერი იცვლება (top=green, bottom=red, dead=orange).
function ProfitProductRow({ product, accent }) {
  const margin = Number(product?.margin_pct);
  const marginText = isFinite(margin) && (Number(product?.revenue_sold_ge) || 0) > 0 ? fmtPct(margin) : '—';
  const isProtected = !!product?.is_protected;
  const isDead = !!product?.is_dead_stock;
  const profit = Number(product?.profit_ge) || 0;
  return (
    <div className={`supplier-modal-product supplier-modal-profit-product supplier-modal-profit-product--${accent}`}>
      <div className="supplier-modal-product-top">
        <span className="supplier-modal-product-name">
          {product?.imported_name || product?.retail_name || product?.imported_code || 'უცნობი'}
          {isProtected && <span className="supplier-modal-profit-protected-tag" title="დაცული კატეგორია">🔒</span>}
        </span>
        <span
          className="supplier-modal-product-amount"
          style={{ color: marginColor(margin), fontWeight: 700 }}
        >
          {marginText}
        </span>
      </div>
      <div className="supplier-modal-product-meta">
        <span>შემოვიდა {fmt(product?.cost_imported_ge)}</span>
        <span>გაიყიდა {fmt(product?.revenue_sold_ge)}</span>
        <span style={{ color: profit >= 0 ? '#bbf7d0' : '#fecaca', fontWeight: 600 }}>
          მოგება {fmtPrecise(profit)}
        </span>
        {isDead && product?.last_sale_date && (
          <span className="supplier-modal-profit-dead-tag">
            ბოლო გაყიდვა: {product.last_sale_date}
            {product?.days_since_last_sale != null ? ` (${product.days_since_last_sale} დღის წინ)` : ''}
          </span>
        )}
        {isDead && !product?.last_sale_date && (
          <span className="supplier-modal-profit-dead-tag">არცერთხელ არ გაიყიდა</span>
        )}
      </div>
    </div>
  );
}

// Unmatched/ambiguous პროდუქცია — ჯერ ვერ დაუკავშირდა MAX-ს, ალიასის კანდიდატია.
// მარჟა/მოგება უცნობია — ვაჩვენებთ კოდს/ერთეულს/ხარჯს. თუ pipeline-მა იპოვა
// ცოცხალი name-candidate (1 retail row ემთხვევა სახელით), inline „დადასტურდი
// ალიასი" ღილაკი ერთი click-ით აფიქსირებს product_aliases.json-ში.
function UnmatchedProductRow({
  product,
  ambiguous = false,
  onConfirm = null,
  confirmed = false,
  pending = false,
}) {
  const candidate = product?.name_candidate || null;
  const variantCls = confirmed
    ? 'confirmed'
    : candidate
    ? 'has-candidate'
    : ambiguous
    ? 'ambiguous'
    : 'unmatched';
  const canConfirm = !!candidate && !!onConfirm && !confirmed && !pending;

  return (
    <div
      className={`supplier-modal-product supplier-modal-profit-product supplier-modal-profit-product--${variantCls}`}
    >
      <div className="supplier-modal-product-top">
        <span className="supplier-modal-product-name">
          {product?.imported_name || product?.imported_code || 'უცნობი'}
          {ambiguous && !confirmed && (
            <span className="supplier-modal-profit-ambiguous-tag" title="რამდენიმე შესაძლო დამთხვევა">⚖️</span>
          )}
          {candidate && !confirmed && (
            <span className="supplier-modal-profit-candidate-tag" title="MAX-ში სახელით ემთხვევა — დადასტურება ერთი ნაბიჯია">💡</span>
          )}
          {confirmed && (
            <span className="supplier-modal-profit-confirmed-tag" title="ალიასი დადასტურდა — მომდევნო pipeline run-ი ანალიზში დაამატებს">✅</span>
          )}
        </span>
        <span className="supplier-modal-product-amount amount-neutral">{fmt(product?.cost_imported_ge)}</span>
      </div>
      <div className="supplier-modal-product-meta">
        {product?.imported_code && <span className="supplier-modal-product-code">კოდი: {product.imported_code}</span>}
        {product?.imported_unit && <span>{product.imported_unit}</span>}
        {product?.quantity_imported != null && (
          <span>
            {fmtQuantity(product.quantity_imported)}
            {product?.imported_unit ? ` ${product.imported_unit}` : ''}
          </span>
        )}
      </div>
      {candidate && (
        <div className="supplier-modal-profit-candidate">
          <div className="supplier-modal-profit-candidate-arrow">→</div>
          <div className="supplier-modal-profit-candidate-body">
            <div className="supplier-modal-profit-candidate-title">MAX-ის შესაძლო შესაბამისობა</div>
            <div className="supplier-modal-profit-candidate-name">
              {candidate.retail_name || '—'}
            </div>
            <div className="supplier-modal-profit-candidate-meta">
              {candidate.retail_product_code && (
                <span className="supplier-modal-product-code">კოდი: {candidate.retail_product_code}</span>
              )}
              {candidate.retail_barcode && (
                <span className="supplier-modal-product-code">ბარკოდი: {candidate.retail_barcode}</span>
              )}
              {candidate.retail_category && <span>{candidate.retail_category}</span>}
            </div>
            {onConfirm && (
              <div className="supplier-modal-profit-candidate-action">
                {confirmed ? (
                  <span className="supplier-modal-profit-confirm-status supplier-modal-profit-confirm-status--ok">
                    ✅ დადასტურდა — შემდეგ pipeline run-ი დაითვლის
                  </span>
                ) : (
                  <button
                    type="button"
                    className="supplier-modal-profit-confirm-btn"
                    disabled={!canConfirm}
                    onClick={() => onConfirm(product)}
                  >
                    {pending ? '⏳ ვამოწმებ…' : '✓ დადასტურდი ალიასი'}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SupplierModal({
  supplier,
  agingData: initialAgingData,
  localPayments = {},
  persistLocalPayments,
  allSuppliers,
  paymentLines = {},
  waybillLines = {},
  supplierInvoices = {},
  supplierInvoicesSummary = {},
  onClose,
  deletedManualPaymentIds,
  onDeleteManualPayment,
  onJournalChange,
}) {
  const [deletingPaymentIds, setDeletingPaymentIds] = useState(() => new Set());
  const [paymentDeleteError, setPaymentDeleteError] = useState('');
  const [liveJournalEntries, setLiveJournalEntries] = useState([]);
  const [journalRefreshTick, setJournalRefreshTick] = useState(0);
  const [fetchedAging, setFetchedAging] = useState(null);
  const [agingLoading, setAgingLoading] = useState(!initialAgingData || initialAgingData.length === 0);
  const [importedResult, setImportedResult] = useState({ key: '', detail: null, error: '' });
  const [payAmount, setPayAmount] = useState('');
  const [recordedFlash, setRecordedFlash] = useState(false);
  const [confirmingWaybillKey, setConfirmingWaybillKey] = useState('');
  const [autoConfirmedKeys, setAutoConfirmedKeys] = useState(() => new Set());
  // per-store toggle: 'total' = ყველა მაღაზია; სხვა მნიშვნელობა = კონკრეტული object (ოზურგეთი / დვაბზუ / ...)
  const [profitStoreFilter, setProfitStoreFilter] = useState('total');
  // Sprint C — alias confirmation state. confirmedAliases: Set<imported_code> that
  // succeeded this session (faded + ✅ in UI). pendingAliases: in-flight POSTs
  // (button shows ⏳). aliasError: last failure {code, message} surfaced once below
  // the candidate list.
  const [confirmedAliases, setConfirmedAliases] = useState(() => new Set());
  const [pendingAliases, setPendingAliases] = useState(() => new Set());
  const [aliasError, setAliasError] = useState(null);
  const [paymentsExpanded, setPaymentsExpanded] = useState(false);
  const [paymentsMonthFilter, setPaymentsMonthFilter] = useState('');
  const [paymentsShowOlder, setPaymentsShowOlder] = useState(false);
  const [waybillsExpanded, setWaybillsExpanded] = useState(false);
  const [waybillsMonthFilter, setWaybillsMonthFilter] = useState('');
  const [waybillsShowOlder, setWaybillsShowOlder] = useState(false);
  const [invoicesExpanded, setInvoicesExpanded] = useState(false);

  const handleConfirmAlias = async (product) => {
    const cand = product?.name_candidate;
    const importedCode = product?.imported_code;
    if (!cand || !importedCode) return;
    if (confirmedAliases.has(importedCode) || pendingAliases.has(importedCode)) return;

    const target = (cand.retail_barcode || cand.retail_product_code || '').trim();
    if (!target) {
      setAliasError({ code: importedCode, message: 'candidate-ს არც ბარკოდი აქვს, არც product_code' });
      return;
    }

    setPendingAliases((prev) => {
      const next = new Set(prev);
      next.add(importedCode);
      return next;
    });
    setAliasError(null);

    try {
      const resp = await fetch('/api/aliases/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          imported_code: importedCode,
          retail_code_or_barcode: target,
          imported_supplier_taxid: taxId || '',
          imported_name_sample: product.imported_name || '',
        }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${resp.status}`);
      }
      setConfirmedAliases((prev) => {
        const next = new Set(prev);
        next.add(importedCode);
        return next;
      });
    } catch (err) {
      setAliasError({ code: importedCode, message: String(err?.message || err) });
    } finally {
      setPendingAliases((prev) => {
        const next = new Set(prev);
        next.delete(importedCode);
        return next;
      });
    }
  };

  useEffect(() => {
    if (initialAgingData && initialAgingData.length > 0) {
      setTimeout(() => setAgingLoading(false), 0);
      return;
    }
    let active = true;
    setTimeout(() => { if (active) setAgingLoading(true); }, 0);
    fetch('/api/data?tab=working_capital')
      .then((res) => res.json())
      .then((json) => {
        if (!active) return;
        setFetchedAging(json.supplier_aging || []);
        setAgingLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        console.error('Failed to fetch aging data:', err);
        setAgingLoading(false);
      });
    return () => { active = false; };
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
      .then((res) => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json(); })
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
        setImportedResult({ key: importedLookupKey, detail: null, error: err.message || 'უცნობი შეცდომა' });
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

  const [productLimit, setProductLimit] = useState(20);
  const [productSearch, setProductSearch] = useState('');

  useEffect(() => {
    if (!taxId) {
      setLiveJournalEntries([]);
      return;
    }
    let cancelled = false;
    fetch(`/api/manual-payments?tax_id=${encodeURIComponent(taxId)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then((body) => {
        if (cancelled) return;
        const entries = Array.isArray(body?.entries) ? body.entries : [];
        setLiveJournalEntries(
          entries.map((e) => ({
            date: e.date || '',
            amount: Number(e.amount) || 0,
            source: 'manual',
            purpose: e.comment || 'ხელით ჟურნალი',
            id: e.id,
          })),
        );
      })
      .catch(() => {
        if (!cancelled) setLiveJournalEntries([]);
      });
    return () => {
      cancelled = true;
    };
  }, [taxId, journalRefreshTick]);

  const supplierPayments = useMemo(() => {
    if (!taxId) return [];
    const raw = Array.isArray(paymentLines?.[taxId]) ? paymentLines[taxId] : [];
    const seenJournalIds = new Set();
    for (const p of raw) {
      if (p?.id) seenJournalIds.add(p.id);
    }
    const liveOnly = liveJournalEntries.filter((e) => !seenJournalIds.has(e.id));
    const merged = [...liveOnly, ...raw];
    if (deletedManualPaymentIds && deletedManualPaymentIds.size > 0) {
      return merged.filter((p) => !(p?.id && deletedManualPaymentIds.has(p.id)));
    }
    return merged;
  }, [taxId, paymentLines, liveJournalEntries, deletedManualPaymentIds]);

  const handleDeleteManualPayment = async (id) => {
    if (!id || !onDeleteManualPayment) return;
    if (!window.confirm('გადახდის ჩანაწერი წავშალოთ?')) return;
    setDeletingPaymentIds((prev) => new Set([...prev, id]));
    setPaymentDeleteError('');
    try {
      await onDeleteManualPayment(id);
    } catch (e) {
      setPaymentDeleteError(e?.message || 'წაშლა ვერ მოხერხდა');
    } finally {
      setDeletingPaymentIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const paymentMonths = useMemo(() => {
    const months = new Set();
    for (const p of supplierPayments) {
      const d = String(p?.date || '');
      if (d.length >= 7) months.add(d.slice(0, 7));
    }
    return Array.from(months).sort().reverse();
  }, [supplierPayments]);

  const undatedPaymentsCount = useMemo(
    () => supplierPayments.filter((p) => !String(p?.date || '').trim()).length,
    [supplierPayments],
  );

  const effectivePaymentsMonth = paymentsMonthFilter === '__all__' || paymentsMonthFilter === '__undated__'
    ? paymentsMonthFilter
    : (paymentsMonthFilter || paymentMonths[0] || '');

  const filteredPayments = useMemo(() => {
    if (effectivePaymentsMonth === '__all__' || !effectivePaymentsMonth) return supplierPayments;
    if (effectivePaymentsMonth === '__undated__') {
      return supplierPayments.filter((p) => !String(p?.date || '').trim());
    }
    return supplierPayments.filter((p) => String(p?.date || '').startsWith(effectivePaymentsMonth));
  }, [supplierPayments, effectivePaymentsMonth]);

  const filteredPaymentsTotal = useMemo(() => {
    return filteredPayments.reduce((acc, p) => acc + (Number(p?.amount) || 0), 0);
  }, [filteredPayments]);

  const supplierWaybills = useMemo(() => {
    if (!taxId) return [];
    return Array.isArray(waybillLines?.[taxId]) ? waybillLines[taxId] : [];
  }, [taxId, waybillLines]);

  const waybillMonths = useMemo(() => {
    const months = new Set();
    for (const w of supplierWaybills) {
      const d = String(w?.date || '');
      if (d.length >= 7) months.add(d.slice(0, 7));
    }
    return Array.from(months).sort().reverse();
  }, [supplierWaybills]);

  const effectiveWaybillsMonth = waybillsMonthFilter === '__all__'
    ? ''
    : (waybillsMonthFilter || waybillMonths[0] || '');

  const filteredWaybills = useMemo(() => {
    if (!effectiveWaybillsMonth) return supplierWaybills;
    return supplierWaybills.filter((w) => String(w?.date || '').startsWith(effectiveWaybillsMonth));
  }, [supplierWaybills, effectiveWaybillsMonth]);

  const filteredWaybillsTotals = useMemo(() => {
    let incoming = 0;
    let returns = 0;
    for (const w of filteredWaybills) {
      const v = Math.abs(Number(w?.amount) || 0);
      if (w?.is_return) returns += v;
      else incoming += v;
    }
    return { incoming, returns };
  }, [filteredWaybills]);
  const filteredTopProducts = useMemo(() => {
    const q = productSearch.trim().toLowerCase();
    const list = q
      ? importedTopProducts.filter((p) => {
          const name = String(p?.product_name || '').toLowerCase();
          const code = String(p?.product_code || '').toLowerCase();
          return name.includes(q) || code.includes(q);
        })
      : importedTopProducts;
    return list.slice(0, productLimit);
  }, [importedTopProducts, productSearch, productLimit]);
  // backend label-ი ხშირად შეიცავს „(REFERENCE)" ინგლისურად — ვაცილებთ
  // და ფიქსირებულ ქართულ სათაურს ვაჩვენებთ.
  const importedSectionTitle = 'შემოტანილი პროდუქცია — შესამოწმებლად';

  // === Profitability — Sprint A მონაცემი ===
  // pipeline-ი წერს `profitability` ველს თითოეულ supplier-ზე;
  // თუ pipeline ძველია (pre Sprint A), ვერ ვიპოვნით — section ჩუმად დაიმალება.
  const profitability = importedEntry?.profitability || null;

  // useMemo-ით ვასტაბილურებთ მითითებას — ცარიელი მასივი ყოველ render-ზე ახალი იქნებოდა და
  // downstream useMemo-ები უსარგებლოდ გადააიგებდნენ.
  const perStoreBreakdown = useMemo(
    () => (Array.isArray(profitability?.per_store_breakdown) ? profitability.per_store_breakdown : []),
    [profitability],
  );

  // toggle-ის options — ჯამი + ყოველი მაღაზია, რომელსაც აქვს რაიმე მასა (cost ან revenue ≠ 0).
  const profitStoreOptions = useMemo(() => {
    const opts = [{ key: 'total', label: 'ჯამი' }];
    for (const entry of perStoreBreakdown) {
      const name = entry?.object || '';
      if (!name) continue;
      const hasMass =
        Math.abs(Number(entry.cost_imported_ge) || 0) +
          Math.abs(Number(entry.revenue_sold_ge) || 0) >
        0;
      if (hasMass) opts.push({ key: name, label: name });
    }
    return opts;
  }, [perStoreBreakdown]);

  // Effective filter — თუ user-ის არჩევანი აღარ არის options-ში (სხვა supplier-ზე გადასვლა),
  // ვუბრუნდებით 'total'-ს render-ის დროს. setState useEffect-ში არ გვჭირდება.
  const effectiveProfitFilter = profitStoreOptions.some((o) => o.key === profitStoreFilter)
    ? profitStoreFilter
    : 'total';

  // KPI ცხრილში ნაჩვენები ციფრები — ჯამური „totals" ან კონკრეტული მაღაზიის row.
  const profitView = useMemo(() => {
    if (!profitability) return null;
    if (effectiveProfitFilter === 'total') {
      const t = profitability.totals || {};
      return {
        cost_imported_ge: Number(t.cost_imported_ge) || 0,
        revenue_sold_ge: Number(t.revenue_sold_ge) || 0,
        profit_ge: Number(t.profit_ge) || 0,
        margin_pct: Number(t.margin_pct) || 0,
        scope_label: 'ყველა მაღაზია',
      };
    }
    const row = perStoreBreakdown.find((e) => e?.object === effectiveProfitFilter);
    if (!row) return null;
    return {
      cost_imported_ge: Number(row.cost_imported_ge) || 0,
      revenue_sold_ge: Number(row.revenue_sold_ge) || 0,
      profit_ge: Number(row.profit_ge) || 0,
      margin_pct: Number(row.margin_pct) || 0,
      scope_label: row.object,
    };
  }, [profitability, effectiveProfitFilter, perStoreBreakdown]);

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

  // პორტფელის ჯამი — ამ მომწოდებლის წილისთვის. useMemo უნდა დარჩეს early-return-ის
  // წინ, რომ React Hook Rules-ის წესი არ დაირღვეს (ყოველ render-ზე იმავე რიგში
  // იწვევოდეს, supplier=null შემთხვევაშიც).
  const portfolioTotal = useMemo(() => {
    if (!Array.isArray(allSuppliers)) return 0;
    return allSuppliers.reduce((sum, s) => sum + (Number(s.total_effective) || 0), 0);
  }, [allSuppliers]);

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
  const localPaidForThis = taxId ? Number(localPayments?.[taxId]) || 0 : 0;
  // Live journal entries that aren't yet reflected in data.json's manual_paid
  // aggregate (pipeline regen pending). Same dedupe logic as supplierPayments.
  const livePendingJournalTotal = useMemo(() => {
    if (!taxId) return 0;
    const raw = Array.isArray(paymentLines?.[taxId]) ? paymentLines[taxId] : [];
    const seen = new Set();
    for (const p of raw) if (p?.id) seen.add(p.id);
    return liveJournalEntries
      .filter((e) => !seen.has(e.id) && !(deletedManualPaymentIds && deletedManualPaymentIds.has(e.id)))
      .reduce((acc, e) => acc + (Number(e.amount) || 0), 0);
  }, [taxId, paymentLines, liveJournalEntries, deletedManualPaymentIds]);
  const pendingPaidForThis = localPaidForThis + livePendingJournalTotal;
  const totalPaidIncludingLocal = paid + pendingPaidForThis;
  const debtAfterLocal = debt - pendingPaidForThis;
  const paymentScopeRaw =
    String(supplier.payment_scope || aging?.payment_scope || '').trim() || 'unpaid_or_unmatched';
  const paymentScopeMeta = getPaymentScopeMeta(paymentScopeRaw);
  const officialNameTruthSource = String(
    supplier.official_name_truth_source || aging?.official_name_truth_source || '',
  ).trim();
  const officialNameSourceMeta = getOfficialNameSourceMeta(officialNameTruthSource);
  const paymentRatioRaw = effective > 0 ? (totalPaidIncludingLocal / effective) * 100 : 0;
  const paymentRatio = Math.min(100, paymentRatioRaw);
  const prColor = paymentColor(paymentRatio);
  const waybillCount = Number(aging?.waybill_count ?? supplier.waybills_count ?? supplier.waybill_count) || 0;
  const avgWaybillAmount = waybillCount > 0 ? effective / waybillCount : 0;

  // პორტფელის წილი — ამ მომწოდებლის ბრუნვა / სულ ყველა მომწოდებლის ბრუნვა.
  // portfolioTotal უკვე გამოანგარიშებულია early-return-ის წინ (Hook Rules).
  const portfolioSharePct = portfolioTotal > 0 ? (effective / portfolioTotal) * 100 : 0;

  const urgency = URGENCY_BY_BUCKET[String(agingBucket)] || null;
  const overpayment = Math.max(0, totalPaidIncludingLocal - effective);
  const hasMeaningfulDebt = debtAfterLocal >= 1;
  const hasOverpayment = overpayment >= 1;

  const parseMoney = (raw) => {
    const n = parseFloat(String(raw || '').replace(/\s/g, '').replace(',', '.'));
    return Number.isNaN(n) ? 0 : Math.max(0, n);
  };

  const payVal = parseMoney(payAmount);
  const canRecord = Boolean(taxId && payVal > 0 && persistLocalPayments);

  // Cash-on-receipt flow: index payments by date for fast same-day lookup.
  const isCashOnReceiptSupplier = Boolean(taxId && CASH_ON_RECEIPT_TAX_IDS.has(taxId));
  const paymentsByDate = useMemo(() => {
    if (!isCashOnReceiptSupplier) return null;
    const m = new Map();
    for (const p of supplierPayments || []) {
      const d = String(p?.date || '').slice(0, 10);
      const amt = Number(p?.amount) || 0;
      if (!d || amt <= 0) continue;
      if (!m.has(d)) m.set(d, []);
      m.get(d).push(amt);
    }
    return m;
  }, [isCashOnReceiptSupplier, supplierPayments]);

  const waybillIsPending = (w) => {
    if (!isCashOnReceiptSupplier || !paymentsByDate) return false;
    if (w?.is_return) return false;
    if ((w?.status || '') === 'გაუქმებული') return false;
    const d = String(w?.date || '').slice(0, 10);
    const wbAmt = Number(w?.amount) || 0;
    if (!d || wbAmt <= 0) return false;
    const key = `${d}|${Math.round(wbAmt * 100)}`;
    if (autoConfirmedKeys.has(key)) return false;
    // Match: same-day payment within 5% (handles auto-backfill scaling and exact-match)
    const dayPayments = paymentsByDate.get(d) || [];
    for (const p of dayPayments) {
      if (Math.abs(p - wbAmt) / wbAmt <= 0.05) return false;
    }
    return true;
  };

  const handleConfirmWaybillPayment = async (w) => {
    if (!taxId) return;
    const d = String(w?.date || '').slice(0, 10);
    const amt = Number(w?.amount) || 0;
    if (!d || amt <= 0) return;
    const key = `${d}|${Math.round(amt * 100)}`;
    setConfirmingWaybillKey(key);
    try {
      const res = await fetch('/api/manual-payments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tax_id: taxId,
          amount: amt,
          date: d,
          comment: `ხელზე გადახდა — ზედნადები ${w?.waybill_number || ''}`.trim(),
        }),
      });
      if (res.ok) {
        setAutoConfirmedKeys((prev) => new Set([...prev, key]));
        setJournalRefreshTick((t) => t + 1);
        if (typeof onJournalChange === 'function') onJournalChange();
      } else {
        window.alert('გადახდის დაფიქსირება ვერ მოხერხდა');
      }
    } catch {
      window.alert('სერვერთან კავშირი ვერ მოხერხდა');
    } finally {
      setConfirmingWaybillKey('');
    }
  };

  const handleRecordPayment = async () => {
    if (!canRecord) return;
    let serverOk = false;
    try {
      const res = await fetch('/api/manual-payments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tax_id: taxId,
          amount: payVal,
          date: new Date().toISOString().slice(0, 10),
          comment: 'ბრაუზერიდან',
        }),
      });
      serverOk = res.ok;
    } catch {
      serverOk = false;
    }
    if (!serverOk) {
      window.alert(
        'სერვერს ვერ მივწვდი — გადახდას მხოლოდ ბრაუზერში ვინახავ. AI ვერ დაინახავს, სანამ ხელახლა არ ცადო.',
      );
      const next = { ...(localPayments || {}), [taxId]: (Number(localPayments?.[taxId]) || 0) + payVal };
      persistLocalPayments(next);
    }
    setPayAmount('');
    setRecordedFlash(true);
    setTimeout(() => setRecordedFlash(false), 1400);
    setJournalRefreshTick((t) => t + 1);
    if (typeof onJournalChange === 'function') onJournalChange();
  };

  const handleClearLocal = () => {
    if (!taxId || !persistLocalPayments) return;
    if (!window.confirm('წავშალოთ ამ მომწოდებელზე ბრაუზერში ჩაწერილი ხელის გადახდები?')) return;
    const next = { ...(localPayments || {}) };
    delete next[taxId];
    persistLocalPayments(next);
  };

  let importedStatusClass = 'badge muted';
  let importedStatusLabel = 'იტვირთება...';
  if (!importedLoading) {
    if (importedError) {
      importedStatusClass = 'badge canceled';
      importedStatusLabel = 'შეცდომა';
    } else if (importedEntry && importedDetail?.match_type === 'tax_id') {
      importedStatusClass = 'badge active';
      importedStatusLabel = 'ნაპოვნია (ID-ით)';
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
          <div className="supplier-modal-org" id="supplier-modal-title">
            {displayOrg}
            {supplierPayments.length > 0 && (
              <button
                type="button"
                onClick={() => setPaymentsExpanded((v) => !v)}
                title="გადახდების სია"
                style={{
                  marginLeft: 10, padding: '3px 10px',
                  background: paymentsExpanded ? '#3b82f6' : '#1e293b',
                  color: '#e2e8f0', border: '1px solid #334155',
                  borderRadius: 6, fontSize: 13, cursor: 'pointer',
                  verticalAlign: 'middle',
                }}
              >
                გადახდები ({supplierPayments.length}) {paymentsExpanded ? '▴' : '▾'}
              </button>
            )}
            {supplierWaybills.length > 0 && (
              <button
                type="button"
                onClick={() => setWaybillsExpanded((v) => !v)}
                title="ზედნადებების სია (გაუქმებულის გარეშე)"
                style={{
                  marginLeft: 8, padding: '3px 10px',
                  background: waybillsExpanded ? '#10b981' : '#1e293b',
                  color: '#e2e8f0', border: '1px solid #334155',
                  borderRadius: 6, fontSize: 13, cursor: 'pointer',
                  verticalAlign: 'middle',
                }}
              >
                ზედნადებები ({supplierWaybills.length}) {waybillsExpanded ? '▴' : '▾'}
              </button>
            )}
          </div>
          <div className="supplier-modal-meta-row">
            {taxId && <span className="supplier-modal-taxid">ID: {taxId}</span>}
            {waybillCount > 0 && <span className="supplier-modal-taxid">{waybillCount} ზედნადები</span>}
            <span className={`badge payment-scope-badge ${paymentScopeMeta.className}`}>
              {paymentScopeMeta.label}
            </span>
            {agingBucket && hasMeaningfulDebt && (
              <span className={`badge ${agingBadgeClass(agingBucket)}`}>
                {AGING_BUCKET_KA[String(agingBucket)] || agingBucket}
              </span>
            )}
          </div>
        </div>

        {paymentsExpanded && supplierPayments.length > 0 && (
          <div style={{
            margin: '8px 0 16px', padding: 12,
            background: '#0f172a', border: '1px solid #334155', borderRadius: 8,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13, color: '#94a3b8' }}>თვე:</span>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {(paymentsShowOlder ? paymentMonths : paymentMonths.slice(0, 6)).map((m) => {
                  const active = effectivePaymentsMonth === m;
                  return (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setPaymentsMonthFilter(m)}
                      style={{
                        background: active ? '#3b82f6' : '#1e293b',
                        color: active ? '#ffffff' : '#cbd5e1',
                        border: `1px solid ${active ? '#3b82f6' : '#334155'}`,
                        borderRadius: 6, padding: '4px 10px', fontSize: 13,
                        cursor: 'pointer', fontWeight: active ? 600 : 400,
                      }}
                    >
                      {m}
                    </button>
                  );
                })}
                {paymentMonths.length > 6 && (
                  <button
                    type="button"
                    onClick={() => setPaymentsShowOlder((v) => !v)}
                    style={{
                      background: '#1e293b', color: '#94a3b8',
                      border: '1px dashed #334155',
                      borderRadius: 6, padding: '4px 10px', fontSize: 13,
                      cursor: 'pointer',
                    }}
                  >
                    {paymentsShowOlder ? '↑ ჩაკეცე' : `ძველი თვეები (+${paymentMonths.length - 6})`}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setPaymentsMonthFilter('__all__')}
                  style={{
                    background: paymentsMonthFilter === '__all__' ? '#3b82f6' : '#1e293b',
                    color: paymentsMonthFilter === '__all__' ? '#ffffff' : '#cbd5e1',
                    border: `1px solid ${paymentsMonthFilter === '__all__' ? '#3b82f6' : '#334155'}`,
                    borderRadius: 6, padding: '4px 10px', fontSize: 13,
                    cursor: 'pointer', fontWeight: paymentsMonthFilter === '__all__' ? 600 : 400,
                  }}
                >
                  ყველა თვე
                </button>
                {undatedPaymentsCount > 0 && (
                  <button
                    type="button"
                    onClick={() => setPaymentsMonthFilter('__undated__')}
                    title="ჩანაწერები თარიღის გარეშე — ჩვეულებრივ legacy CSV-დან აღდგენილი"
                    style={{
                      background: paymentsMonthFilter === '__undated__' ? '#f59e0b' : '#1e293b',
                      color: paymentsMonthFilter === '__undated__' ? '#0f172a' : '#fcd34d',
                      border: `1px solid ${paymentsMonthFilter === '__undated__' ? '#f59e0b' : '#92400e'}`,
                      borderRadius: 6, padding: '4px 10px', fontSize: 13,
                      cursor: 'pointer', fontWeight: paymentsMonthFilter === '__undated__' ? 600 : 400,
                    }}
                  >
                    📅 თარიღის გარეშე ({undatedPaymentsCount})
                  </button>
                )}
              </div>
              <span style={{ flex: 1 }} />
              <span style={{ fontSize: 13, color: '#94a3b8' }}>
                {filteredPayments.length} გადახდა · ჯამი <strong style={{ color: '#86efac' }}>{fmt(filteredPaymentsTotal)}</strong>
              </span>
            </div>
            {paymentDeleteError && (
              <div style={{ padding: '6px 12px', color: '#fca5a5', fontSize: 12, background: '#3f1d1d', borderTop: '1px solid #1e293b' }}>
                ⚠ {paymentDeleteError}
              </div>
            )}
            <div style={{ maxHeight: 280, overflowY: 'auto', borderTop: '1px solid #1e293b' }}>
              <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                <thead style={{ position: 'sticky', top: 0, background: '#0f172a' }}>
                  <tr style={{ color: '#94a3b8', textAlign: 'left' }}>
                    <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>თარიღი</th>
                    <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155', textAlign: 'right' }}>თანხა</th>
                    <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>წყარო</th>
                    <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>დანიშნულება</th>
                    <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155', width: 36 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPayments.map((p, i) => {
                    const isManualDeletable = p.source === 'manual' && p.id;
                    const isDeleting = deletingPaymentIds.has(p.id);
                    return (
                      <tr key={p.id || `${p.date}-${i}`} style={{ borderBottom: '1px solid #1e293b' }}>
                        <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>{p.date || '—'}</td>
                        <td style={{ padding: '6px 8px', textAlign: 'right', color: '#86efac', whiteSpace: 'nowrap' }}>
                          {fmtPrecise(p.amount)}
                        </td>
                        <td style={{ padding: '6px 8px' }}>
                          <span style={{
                            fontSize: 11, padding: '2px 6px', borderRadius: 4,
                            background: p.source === 'manual' ? '#7c3aed' : '#334155',
                            color: '#e2e8f0',
                          }}>
                            {p.source === 'manual' ? 'ხელით' : p.source}
                          </span>
                        </td>
                        <td style={{ padding: '6px 8px', color: '#cbd5e1', maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {p.purpose || '—'}
                        </td>
                        <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                          {isManualDeletable && (
                            <button
                              type="button"
                              onClick={() => handleDeleteManualPayment(p.id)}
                              disabled={isDeleting}
                              title="ჩანაწერის წაშლა"
                              style={{
                                background: 'transparent',
                                border: 'none',
                                cursor: isDeleting ? 'wait' : 'pointer',
                                color: '#f87171',
                                fontSize: 14,
                                padding: 2,
                                opacity: isDeleting ? 0.5 : 1,
                              }}
                            >
                              🗑
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {filteredPayments.length === 0 && (
                    <tr>
                      <td colSpan="5" style={{ padding: 14, textAlign: 'center', color: '#94a3b8', fontStyle: 'italic' }}>
                        ამ თვეში გადახდა არ არის.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {waybillsExpanded && supplierWaybills.length > 0 && (
          <div style={{
            margin: '8px 0 16px', padding: 12,
            background: '#0f172a', border: '1px solid #334155', borderRadius: 8,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13, color: '#94a3b8' }}>თვე:</span>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {(waybillsShowOlder ? waybillMonths : waybillMonths.slice(0, 6)).map((m) => {
                  const active = effectiveWaybillsMonth === m;
                  return (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setWaybillsMonthFilter(m)}
                      style={{
                        background: active ? '#10b981' : '#1e293b',
                        color: active ? '#ffffff' : '#cbd5e1',
                        border: `1px solid ${active ? '#10b981' : '#334155'}`,
                        borderRadius: 6, padding: '4px 10px', fontSize: 13,
                        cursor: 'pointer', fontWeight: active ? 600 : 400,
                      }}
                    >
                      {m}
                    </button>
                  );
                })}
                {waybillMonths.length > 6 && (
                  <button
                    type="button"
                    onClick={() => setWaybillsShowOlder((v) => !v)}
                    style={{
                      background: '#1e293b', color: '#94a3b8',
                      border: '1px dashed #334155',
                      borderRadius: 6, padding: '4px 10px', fontSize: 13,
                      cursor: 'pointer',
                    }}
                  >
                    {waybillsShowOlder ? '↑ ჩაკეცე' : `ძველი თვეები (+${waybillMonths.length - 6})`}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setWaybillsMonthFilter('__all__')}
                  style={{
                    background: waybillsMonthFilter === '__all__' ? '#10b981' : '#1e293b',
                    color: waybillsMonthFilter === '__all__' ? '#ffffff' : '#cbd5e1',
                    border: `1px solid ${waybillsMonthFilter === '__all__' ? '#10b981' : '#334155'}`,
                    borderRadius: 6, padding: '4px 10px', fontSize: 13,
                    cursor: 'pointer', fontWeight: waybillsMonthFilter === '__all__' ? 600 : 400,
                  }}
                >
                  ყველა თვე
                </button>
              </div>
              <span style={{ flex: 1 }} />
              <span style={{ fontSize: 13, color: '#94a3b8' }}>
                {filteredWaybills.length} ზედნადები · შემოტანა <strong style={{ color: '#86efac' }}>{fmt(filteredWaybillsTotals.incoming)}</strong>
                {filteredWaybillsTotals.returns > 0 && (
                  <> · დაბრუნება <strong style={{ color: '#fca5a5' }}>{fmt(filteredWaybillsTotals.returns)}</strong></>
                )}
              </span>
            </div>
            <div style={{ maxHeight: 280, overflowY: 'auto', borderTop: '1px solid #1e293b' }}>
              <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                <thead style={{ position: 'sticky', top: 0, background: '#0f172a' }}>
                  <tr style={{ color: '#94a3b8', textAlign: 'left' }}>
                    <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>თარიღი</th>
                    <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>ზედნადების №</th>
                    <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155', textAlign: 'right' }}>თანხა</th>
                    <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>მაღაზია</th>
                    <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>ტიპი</th>
                    <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>სტატუსი</th>
                    {isCashOnReceiptSupplier && (
                      <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>ხელზე გადახდა</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {filteredWaybills.map((w, i) => (
                    <tr key={`${w.waybill_number}-${i}`} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>{w.date || '—'}</td>
                      <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontSize: 12, color: '#cbd5e1' }}>{w.waybill_number || '—'}</td>
                      <td style={{
                        padding: '6px 8px', textAlign: 'right', whiteSpace: 'nowrap',
                        color: w.is_return ? '#fca5a5' : '#86efac',
                      }}>
                        {w.is_return ? '−' : ''}{fmtPrecise(w.amount)}
                      </td>
                      <td
                        style={{ padding: '6px 8px', color: '#cbd5e1', whiteSpace: 'nowrap' }}
                        title={w.delivery_location || ''}
                      >
                        {w.store ? (
                          <span style={{
                            fontSize: 11, padding: '2px 6px', borderRadius: 4,
                            background: '#1e293b', color: '#a5b4fc', border: '1px solid #334155',
                          }}>{w.store}</span>
                        ) : <span style={{ color: '#475569', fontSize: 11 }}>—</span>}
                      </td>
                      <td style={{ padding: '6px 8px', color: '#cbd5e1' }}>
                        {w.is_return ? (
                          <span style={{
                            fontSize: 11, padding: '2px 6px', borderRadius: 4,
                            background: '#7f1d1d', color: '#fee2e2',
                          }}>დაბრუნება</span>
                        ) : (w.type || '—')}
                      </td>
                      <td style={{ padding: '6px 8px', color: '#94a3b8', fontSize: 12 }}>{w.status || '—'}</td>
                      {isCashOnReceiptSupplier && (
                        <td style={{ padding: '6px 8px' }}>
                          {(() => {
                            const d = String(w?.date || '').slice(0, 10);
                            const amt = Number(w?.amount) || 0;
                            const key = `${d}|${Math.round(amt * 100)}`;
                            if (autoConfirmedKeys.has(key)) {
                              return <span style={{ color: '#10b981', fontSize: 12 }}>✓ დადასტურდა</span>;
                            }
                            if (!waybillIsPending(w)) {
                              return <span style={{ color: '#64748b', fontSize: 11 }}>—</span>;
                            }
                            const isBusy = confirmingWaybillKey === key;
                            return (
                              <button
                                onClick={() => handleConfirmWaybillPayment(w)}
                                disabled={isBusy}
                                style={{
                                  background: isBusy ? '#475569' : '#10b981',
                                  color: '#ffffff',
                                  border: 'none',
                                  borderRadius: 4,
                                  padding: '4px 10px',
                                  fontSize: 12,
                                  cursor: isBusy ? 'wait' : 'pointer',
                                  fontWeight: 500,
                                }}
                              >
                                {isBusy ? '...' : '✅ ვეთანხმები'}
                              </button>
                            );
                          })()}
                        </td>
                      )}
                    </tr>
                  ))}
                  {filteredWaybills.length === 0 && (
                    <tr>
                      <td colSpan={isCashOnReceiptSupplier ? 7 : 6} style={{ padding: 14, textAlign: 'center', color: '#94a3b8', fontStyle: 'italic' }}>
                        ამ თვეში ზედნადები არ არის.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 3 KPI */}
        <div className="supplier-modal-kpis">
          <div className="supplier-modal-kpi">
            <div className="kpi-label">რეალური ბრუნვა</div>
            <div className="kpi-value amount-neutral">{fmt(effective)}</div>
          </div>
          <div className="supplier-modal-kpi">
            <div className="kpi-label">სულ გადახდილი</div>
            <div className="kpi-value amount-positive">{fmt(totalPaidIncludingLocal)}</div>
            {livePendingJournalTotal > 0 && (
              <div className="supplier-modal-kpi-hint">+{fmt(livePendingJournalTotal)} ხელის ჟურნალიდან</div>
            )}
            {localPaidForThis > 0 && (
              <div className="supplier-modal-kpi-hint">+{fmt(localPaidForThis)} ბრაუზერიდან</div>
            )}
          </div>
          <div className="supplier-modal-kpi">
            <div className="kpi-label">დარჩენილი ვალი</div>
            <div className="kpi-value amount-negative">{fmt(debtAfterLocal)}</div>
          </div>
        </div>

        {/* ანალიზი — გასაგები სიგნალები */}
        <div className="supplier-modal-section">
          <div className="supplier-modal-section-title">📊 ანალიზი</div>
          <div className="supplier-modal-analysis-grid">
            <div className="supplier-modal-analysis-cell">
              <div className="supplier-modal-analysis-label">საშუალო ზედნადები</div>
              <div className="supplier-modal-analysis-value">{fmt(avgWaybillAmount)}</div>
              <div className="supplier-modal-analysis-hint">{waybillCount} ზედნადებიდან</div>
            </div>
            <div className="supplier-modal-analysis-cell">
              <div className="supplier-modal-analysis-label">წილი პორტფელში</div>
              <div className="supplier-modal-analysis-value">{portfolioSharePct.toFixed(2)}%</div>
              <div className="supplier-modal-analysis-hint">სულ {fmt(portfolioTotal)}</div>
            </div>
            <div className="supplier-modal-analysis-cell">
              <div className="supplier-modal-analysis-label">გადახდის წილი</div>
              <div className="supplier-modal-analysis-value" style={{ color: prColor }}>
                {paymentRatio.toFixed(1)}%
              </div>
              <div className="ratio-gauge" style={{ marginTop: 6 }}>
                <div className="ratio-gauge-fill" style={{ width: `${paymentRatio}%`, background: prColor }} />
              </div>
            </div>
          </div>
          {/* წვრილი ცდომილება (≤1 ₾) ფაქტობრივი ვალი არ არის → არ ვიკიდოთ urgency */}
          {urgency && hasMeaningfulDebt && (
            <div className={`supplier-modal-signal supplier-modal-signal--${urgency.tone}`}>
              <span className="supplier-modal-signal-icon" aria-hidden="true">⏱</span>
              <span>{urgency.text}</span>
            </div>
          )}
          {!hasMeaningfulDebt && debt >= 1 && localPaidForThis > 0 && (
            <div className="supplier-modal-signal supplier-modal-signal--ok">
              <span className="supplier-modal-signal-icon" aria-hidden="true">✓</span>
              <span>ბრაუზერის გადახდები ფარავს ვალს — დაადასტურე ფინალურად Excel-ს</span>
            </div>
          )}
          {hasOverpayment && (
            <div className="supplier-modal-signal supplier-modal-signal--medium">
              <span className="supplier-modal-signal-icon" aria-hidden="true">⚠</span>
              <span>
                ზედმეტად გადახდილი: <strong>{fmt(overpayment)}</strong> — გადაამოწმე ბანკის ან RS-ის წყაროდან
              </span>
            </div>
          )}
        </div>

        {/* 📊 პროდუქციული მოგება — Sprint A: cost vs revenue per matched product, per store, top/bottom/dead-stock */}
        {profitability && profitability.status !== 'empty' && (
          <div className="supplier-modal-section supplier-modal-profit">
            <div className="supplier-modal-section-title">
              📊 პროდუქციული მოგება
              {importedLoading && <span className="supplier-modal-section-hint"> (იტვირთება...)</span>}
            </div>

            {/* Status badge */}
            <div
              className={`supplier-modal-profit-status supplier-modal-profit-status--${
                PROFITABILITY_STATUS_META[profitability.status]?.tone || 'muted'
              }`}
            >
              <strong>
                {PROFITABILITY_STATUS_META[profitability.status]?.label || profitability.status}
              </strong>
              {profitability.coverage?.cost_pct != null &&
                profitability.status !== 'unverified' &&
                profitability.status !== 'protected' && (
                  <span className="supplier-modal-profit-coverage">
                    {' '}— შემოტანილი ღირებულების {fmtPct(profitability.coverage.cost_pct)} დაუკავშირდა MAX-ს
                  </span>
                )}
            </div>
            {PROFITABILITY_STATUS_META[profitability.status]?.hint && (
              <div className="supplier-modal-profit-hint">
                {PROFITABILITY_STATUS_META[profitability.status].hint}
              </div>
            )}

            {/* unverified — ცარიელი KPI ვერ ვაჩვენებ (memory: maximize, never silent gap),
                მაგრამ ვაჩვენებ 3 ბაკეტს: დაკავშირებული / ალიასით გადარჩება / source აკლია.
                + ცოცხალი 10 candidate ხელით დასადასტურებლად. */}
            {profitability.status === 'unverified' && (
              <>
                {(() => {
                  const totals = profitability.totals || {};
                  const cov = profitability.coverage || {};
                  const totalCost = Number(totals.cost_imported_ge) || 0;
                  const matchedCost = Number(totals.cost_matched_ge) || 0;
                  const candidateCost = Number(cov.unmatched_with_candidate_cost_ge) || 0;
                  const candidateCount = Number(cov.unmatched_with_candidate_count) || 0;
                  const noSourceCost = Math.max(0, totalCost - matchedCost - candidateCost);
                  const noSourceCount = Math.max(
                    0,
                    Number(totals.products_unmatched) - candidateCount,
                  );
                  return (
                    <div className="supplier-modal-profit-bucket-grid">
                      <div className="supplier-modal-profit-bucket supplier-modal-profit-bucket--available">
                        <div className="supplier-modal-profit-bucket-icon">💡</div>
                        <div className="supplier-modal-profit-bucket-body">
                          <div className="supplier-modal-profit-bucket-label">ალიასით გადარჩება</div>
                          <div className="supplier-modal-profit-bucket-value">{fmt(candidateCost)}</div>
                          <div className="supplier-modal-profit-bucket-hint">
                            {fmtCount(candidateCount)} პროდუქცია · ხელით დადასტურებას სჭირდება
                          </div>
                        </div>
                      </div>
                      <div className="supplier-modal-profit-bucket supplier-modal-profit-bucket--missing">
                        <div className="supplier-modal-profit-bucket-icon">❓</div>
                        <div className="supplier-modal-profit-bucket-body">
                          <div className="supplier-modal-profit-bucket-label">MAX-ში არ არის</div>
                          <div className="supplier-modal-profit-bucket-value">{fmt(noSourceCost)}</div>
                          <div className="supplier-modal-profit-bucket-hint">
                            {fmtCount(noSourceCount)} პროდუქცია · ცალკე source სჭირდება
                          </div>
                        </div>
                      </div>
                      <div className="supplier-modal-profit-bucket supplier-modal-profit-bucket--total">
                        <div className="supplier-modal-profit-bucket-icon">📦</div>
                        <div className="supplier-modal-profit-bucket-body">
                          <div className="supplier-modal-profit-bucket-label">სულ შემოვიდა</div>
                          <div className="supplier-modal-profit-bucket-value">{fmt(totalCost)}</div>
                          <div className="supplier-modal-profit-bucket-hint">
                            {fmtCount(totals.products_imported)} პროდუქცია
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })()}
                {(profitability.unmatched_preview || []).length > 0 && (
                  <>
                    <div className="supplier-modal-section-title" style={{ marginTop: 8 }}>
                      ალიასის კანდიდატები
                      <span className="supplier-modal-section-hint">
                        {' '}· ყველაზე ფასიანი {profitability.unmatched_preview.length} პროდუქცია · 💡 = MAX-ში სახელით ემთხვევა · ✓ ღილაკი = ერთი click დადასტურება
                      </span>
                    </div>
                    <div className="supplier-modal-products">
                      {profitability.unmatched_preview.map((p, idx) => (
                        <UnmatchedProductRow
                          key={`u-${idx}`}
                          product={p}
                          onConfirm={handleConfirmAlias}
                          confirmed={confirmedAliases.has(p.imported_code)}
                          pending={pendingAliases.has(p.imported_code)}
                        />
                      ))}
                    </div>
                    <div className="supplier-modal-note">
                      💡 = pipeline იპოვა MAX-ში სახელით ემთხვევა. „✓ დადასტურდი ალიასი"
                      აფიქსირებს mapping-ს — შემდეგი pipeline run-ი ანალიზში დაამატებს.
                      {confirmedAliases.size > 0 && (
                        <span className="supplier-modal-note-confirmed">
                          {' '}· ✅ ამ session-ში დადასტურდა: {confirmedAliases.size}
                        </span>
                      )}
                    </div>
                    {aliasError && (
                      <div className="supplier-modal-note supplier-modal-note--error">
                        ⚠️ ვერ დადასტურდა ({aliasError.code}): {aliasError.message}
                      </div>
                    )}
                  </>
                )}
              </>
            )}

            {/* verified / partial / protected — full KPI + per-store + სიები */}
            {(profitability.status === 'verified' ||
              profitability.status === 'partial' ||
              profitability.status === 'protected') && (
              <>
                {profitStoreOptions.length > 1 && (
                  <div className="supplier-modal-profit-toggle" role="tablist">
                    {profitStoreOptions.map((opt) => (
                      <button
                        key={opt.key}
                        type="button"
                        role="tab"
                        aria-selected={effectiveProfitFilter === opt.key}
                        className={`supplier-modal-profit-toggle-btn ${
                          effectiveProfitFilter === opt.key ? 'is-active' : ''
                        }`}
                        onClick={() => setProfitStoreFilter(opt.key)}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}

                {profitView && (
                  <>
                    {/* Scope clarifier — KPI ცხრილში ფიგურირებს ორი სცენარი:
                        „შემოვიდა" = სულ შემოდინება (matched + unmatched), მაგრამ
                        „გავიდა / მოგება / მარჟა" = მხოლოდ matched პროდუქცია.
                        scope-ბანერი ნათლად ადგენს რა ნაწილს ეხება თითო ციფრი. */}
                    {profitability.totals && profitability.totals.products_imported > 0 && (
                      <div className="supplier-modal-profit-scope">
                        <span className="supplier-modal-profit-scope-icon" aria-hidden="true">📐</span>
                        <span>
                          ანალიზი ეფუძნება <strong>{fmtCount(profitability.totals.products_matched)}</strong> პროდუქცია{' '}
                          <strong>{fmtCount(profitability.totals.products_imported)}</strong>-დან
                          {profitability.coverage?.cost_pct != null && (
                            <>
                              {' '}({fmtPct(profitability.coverage.cost_pct)} შემოდინების ღირებულებიდან).{' '}
                            </>
                          )}
                          „შემოვიდა" = ყველა შემოდინება. „გავიდა / მოგება / მარჟა" =
                          მხოლოდ ანალიზდილი ნაწილი.
                        </span>
                      </div>
                    )}
                    <div className="supplier-modal-profit-grid">
                      <div className="supplier-modal-profit-cell">
                        <div className="supplier-modal-profit-label">შემოვიდა (სულ)</div>
                        <div className="supplier-modal-profit-value">{fmt(profitView.cost_imported_ge)}</div>
                      </div>
                      <div className="supplier-modal-profit-cell">
                        <div className="supplier-modal-profit-label">გავიდა (ანალიზდა)</div>
                        <div className="supplier-modal-profit-value">{fmt(profitView.revenue_sold_ge)}</div>
                      </div>
                      <div className="supplier-modal-profit-cell">
                        <div className="supplier-modal-profit-label">მოგება (ანალიზდა)</div>
                        <div
                          className="supplier-modal-profit-value"
                          style={{ color: marginColor(profitView.margin_pct) }}
                        >
                          {fmt(profitView.profit_ge)}
                        </div>
                      </div>
                      <div className="supplier-modal-profit-cell">
                        <div className="supplier-modal-profit-label">მარჟა (ანალიზდა)</div>
                        <div
                          className="supplier-modal-profit-value"
                          style={{ color: marginColor(profitView.margin_pct) }}
                        >
                          {profitView.revenue_sold_ge > 0 ? fmtPct(profitView.margin_pct) : '—'}
                        </div>
                      </div>
                    </div>
                  </>
                )}

                {(profitability.top_margin || []).length > 0 && (
                  <>
                    <div className="supplier-modal-section-title" style={{ marginTop: 8 }}>
                      ⭐ ყველაზე მომგებიანი (top {profitability.top_margin.length})
                      <span className="supplier-modal-section-hint">
                        {' '}· სუპლაიერის ჯამი ყველა მაღაზიაზე
                      </span>
                    </div>
                    <div className="supplier-modal-products">
                      {profitability.top_margin.map((p, idx) => (
                        <ProfitProductRow key={`top-${idx}`} product={p} accent="top" />
                      ))}
                    </div>
                  </>
                )}

                {profitability.status !== 'protected' &&
                  (profitability.bottom_margin || []).length > 0 && (
                    <>
                      <div className="supplier-modal-section-title" style={{ marginTop: 8 }}>
                        ⚠️ დაბალი მარჟით ({profitability.bottom_margin.length})
                        <span className="supplier-modal-section-hint">
                          {' '}· ფასის ან ფასდაკლების გადახედვის კანდიდატი
                        </span>
                      </div>
                      <div className="supplier-modal-products">
                        {profitability.bottom_margin.map((p, idx) => (
                          <ProfitProductRow key={`bot-${idx}`} product={p} accent="bottom" />
                        ))}
                      </div>
                    </>
                  )}

                {(profitability.dead_stock || []).length > 0 && (
                  <>
                    <div className="supplier-modal-section-title" style={{ marginTop: 8 }}>
                      🐌 დიდი ხანია არ იყიდება ({profitability.dead_stock.length})
                      <span className="supplier-modal-section-hint">
                        {' '}· 120+ დღე გაუყიდავი ან 0 გაყიდვა
                      </span>
                    </div>
                    <div className="supplier-modal-products">
                      {profitability.dead_stock.map((p, idx) => (
                        <ProfitProductRow key={`dead-${idx}`} product={p} accent="dead" />
                      ))}
                    </div>
                  </>
                )}

                {profitability.status === 'partial' &&
                  Number(profitability.totals?.products_unmatched) > 0 && (
                    <div className="supplier-modal-note">
                      📋 <strong>{fmtCount(profitability.totals.products_unmatched)}</strong>{' '}
                      პროდუქცია ({fmt(
                        (Number(profitability.totals.cost_imported_ge) || 0) -
                          (Number(profitability.totals.cost_matched_ge) || 0)
                      )}) ჯერ ვერ დაუკავშირდა — ანალიზში არ შედის.
                    </div>
                  )}

                {Number(profitability.coverage?.ambiguous_cost_pct) > 0 && (
                  <div className="supplier-modal-note supplier-modal-note--warn">
                    ⚖️ <strong>{fmtPct(profitability.coverage.ambiguous_cost_pct)}</strong>{' '}
                    ({fmt(profitability.totals?.cost_ambiguous_ge)}) — კოდი ჰქონდათ MAX-ში
                    რამდენიმე პროდუქტთან საერთო, ანალიზში არ ჩავთვალე ხელით ალიასამდე.
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ხელით გადახდის ჩაწერა — მოდალში ჩასმული */}
        {taxId && persistLocalPayments && (
          <div className={`supplier-modal-section supplier-modal-pay ${recordedFlash ? 'is-flash' : ''}`}>
            <div className="supplier-modal-section-title">💸 ხელით გადახდის ჩაწერა</div>
            <div className="supplier-modal-pay-form">
              <div className="supplier-modal-pay-input-wrap">
                <input
                  type="text"
                  inputMode="decimal"
                  className="supplier-modal-pay-input"
                  placeholder="0"
                  value={payAmount}
                  onChange={(e) => setPayAmount(e.target.value)}
                  autoComplete="off"
                  aria-label="გადახდის თანხა"
                />
                <span className="supplier-modal-pay-currency" aria-hidden="true">₾</span>
              </div>
              <button
                type="button"
                className="supplier-modal-pay-record"
                disabled={!canRecord}
                onClick={handleRecordPayment}
              >
                ✓ ჩაწერა{payVal > 0 ? ` · ${fmt(payVal)}` : ''}
              </button>
              {localPaidForThis > 0 && (
                <button
                  type="button"
                  className="supplier-modal-pay-clear"
                  onClick={handleClearLocal}
                  title="ამ მომწოდებლის ბრაუზერში ჩაწერილი გადახდების წაშლა"
                >
                  გასუფთავება
                </button>
              )}
            </div>
            <div className="supplier-modal-pay-hint">
              ჩაიწერება ბრაუზერში · ემატება „სულ გადახდილს" · იკლებს „ვალს".
              {' '}მუდმივად: მთავარი გვერდიდან <strong>CSV</strong> ჩამოტვირთვა და <code>manual_payments.csv</code>-ში ჩასმა.
            </div>
            {localPaidForThis > 0 && (
              <div className="supplier-modal-pay-history">
                <strong>ბრაუზერში ჩაწერილი ჯამი ამ მომწოდებელზე:</strong>{' '}
                <span className="amount-positive">{fmt(localPaidForThis)}</span>
              </div>
            )}
          </div>
        )}

        {/* გადახდის ჩაშლა */}
        <div className="supplier-modal-section">
          <div className="supplier-modal-section-title">🧮 გადახდის ჩაშლა</div>
          <div className="supplier-modal-split-grid">
            <div className="supplier-modal-split-card supplier-modal-split-card--strict">
              <div className="supplier-modal-split-label">ბანკით დადასტურებული</div>
              <div className="supplier-modal-split-value amount-positive">{fmt(strictBankPaid)}</div>
            </div>
            <div className="supplier-modal-split-card supplier-modal-split-card--manual">
              <div className="supplier-modal-split-label">ნაღდი / ჟურნალი</div>
              <div className="supplier-modal-split-value amount-neutral">{fmt(manualPaid + localPaidForThis)}</div>
              {localPaidForThis > 0 && (
                <div className="supplier-modal-split-hint">+{fmt(localPaidForThis)} ბრაუზერიდან</div>
              )}
            </div>
            <div className="supplier-modal-split-card supplier-modal-split-card--combined">
              <div className="supplier-modal-split-label">სულ გადახდილი</div>
              <div className="supplier-modal-split-value amount-positive">{fmt(totalPaidIncludingLocal)}</div>
            </div>
          </div>
        </div>

        {/* ვადიანობა */}
        <div className="supplier-modal-section">
          <div className="supplier-modal-section-title">
            📅 ვადიანობა{agingLoading && <span className="supplier-modal-section-hint"> (იტვირთება...)</span>}
          </div>
          <div className="supplier-modal-row">
            <span className="supplier-modal-row-label">ბოლო ზედნადები</span>
            <span>{agingLoading ? '—' : lastDate}{days > 0 ? ` (${days} დღის წინ)` : ''}</span>
          </div>
          {obj && (
            <div className="supplier-modal-row">
              <span className="supplier-modal-row-label">ობიექტი</span>
              <span className="badge" style={{
                background: `${OBJECT_COLORS[obj] || '#8899aa'}22`,
                color: OBJECT_COLORS[obj] || '#8899aa',
                border: `1px solid ${OBJECT_COLORS[obj] || '#8899aa'}55`,
              }}>{obj}</span>
            </div>
          )}
        </div>

        {/* 📋 ფაქტურები (rs.ge) — Phase 1 */}
        {taxId && (() => {
          const invoiceList = supplierInvoices[taxId] || [];
          const invoiceSummary = supplierInvoicesSummary[taxId] || null;
          if (invoiceList.length === 0 && !invoiceSummary) return null;

          const STATUS_COLORS = {
            'დადასტურებული': { bg: '#064e3b', fg: '#6ee7b7', border: '#10b981' },
            'დასადასტურებელი': { bg: '#451a03', fg: '#fcd34d', border: '#f59e0b' },
            'პირველადი': { bg: '#1e3a8a', fg: '#93c5fd', border: '#3b82f6' },
            'კორექტირებული': { bg: '#7c2d12', fg: '#fdba74', border: '#ea580c' },
            'გაუქმებული': { bg: '#7f1d1d', fg: '#fca5a5', border: '#ef4444' },
          };
          const formatGel = (v) => {
            const n = Number(v) || 0;
            return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + ' ₾';
          };
          const totalAmount = invoiceSummary?.total_amount || 0;
          const totalVat = invoiceSummary?.total_vat || 0;
          const invoiceCount = invoiceSummary?.invoice_count || invoiceList.length;
          const lastDate = invoiceSummary?.last_invoice_date || null;
          const agingTotal = Number(supplier?.total_effective || 0);
          const gap = totalAmount - agingTotal;
          const sortedInvoices = [...invoiceList].sort((a, b) => {
            const da = a.date_issued || '';
            const db = b.date_issued || '';
            return db.localeCompare(da);
          });

          return (
            <div className="supplier-modal-section">
              <div className="supplier-modal-section-title">
                📋 ფაქტურები (rs.ge)
                <button
                  type="button"
                  onClick={() => setInvoicesExpanded((v) => !v)}
                  style={{
                    marginLeft: 10, padding: '3px 10px',
                    background: invoicesExpanded ? '#3b82f6' : '#1e293b',
                    color: '#e2e8f0', border: '1px solid #334155',
                    borderRadius: 6, fontSize: 13, cursor: 'pointer',
                  }}
                >
                  სია ({invoiceCount}) {invoicesExpanded ? '▴' : '▾'}
                </button>
              </div>

              {/* Footer KPIs */}
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                gap: 10, padding: '10px 0',
              }}>
                <div>
                  <div style={{ fontSize: 12, color: '#94a3b8' }}>ფაქტურის რაოდენობა</div>
                  <div style={{ fontSize: 18, fontWeight: 600 }}>{invoiceCount}</div>
                </div>
                <div>
                  <div style={{ fontSize: 12, color: '#94a3b8' }}>ფაქტურით ჯამი</div>
                  <div style={{ fontSize: 18, fontWeight: 600 }}>{formatGel(totalAmount)}</div>
                </div>
                <div>
                  <div style={{ fontSize: 12, color: '#94a3b8' }}>დღგ ჯამი</div>
                  <div style={{ fontSize: 18, fontWeight: 600 }}>{formatGel(totalVat)}</div>
                </div>
                {agingTotal > 0 && (
                  <div>
                    <div style={{ fontSize: 12, color: '#94a3b8' }}>აგინგ-ფაქტურა სხვაობა</div>
                    <div style={{
                      fontSize: 18, fontWeight: 600,
                      color: Math.abs(gap) > 100 ? '#fbbf24' : '#10b981',
                    }}>
                      {formatGel(gap)}
                    </div>
                  </div>
                )}
                {lastDate && (
                  <div>
                    <div style={{ fontSize: 12, color: '#94a3b8' }}>ბოლო ფაქტურა</div>
                    <div style={{ fontSize: 14 }}>{lastDate.slice(0, 10)}</div>
                  </div>
                )}
              </div>

              {/* Status counts */}
              {invoiceSummary?.status_counts && Object.keys(invoiceSummary.status_counts).length > 1 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                  {Object.entries(invoiceSummary.status_counts).map(([status, count]) => {
                    const colors = STATUS_COLORS[status] || { bg: '#1e293b', fg: '#cbd5e1', border: '#334155' };
                    return (
                      <span key={status} style={{
                        padding: '3px 8px', fontSize: 12, borderRadius: 4,
                        background: colors.bg, color: colors.fg,
                        border: `1px solid ${colors.border}`,
                      }}>
                        {status}: {count}
                      </span>
                    );
                  })}
                </div>
              )}

              {/* Collapsible table */}
              {invoicesExpanded && sortedInvoices.length > 0 && (
                <div style={{
                  marginTop: 12, maxHeight: 400, overflowY: 'auto',
                  border: '1px solid #334155', borderRadius: 6,
                }}>
                  <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                    <thead style={{ position: 'sticky', top: 0, background: '#0f172a', zIndex: 1 }}>
                      <tr>
                        <th style={{ textAlign: 'left', padding: '8px 6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>ID</th>
                        <th style={{ textAlign: 'left', padding: '8px 6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>სერია</th>
                        <th style={{ textAlign: 'left', padding: '8px 6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>თარიღი</th>
                        <th style={{ textAlign: 'right', padding: '8px 6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>თანხა</th>
                        <th style={{ textAlign: 'right', padding: '8px 6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>დღგ</th>
                        <th style={{ textAlign: 'left', padding: '8px 6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>სტატუსი</th>
                        <th style={{ textAlign: 'center', padding: '8px 6px', color: '#94a3b8', borderBottom: '1px solid #334155' }}>ზედნადები</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedInvoices.map((inv, idx) => {
                        const colors = STATUS_COLORS[inv.status] || { bg: '#1e293b', fg: '#cbd5e1', border: '#334155' };
                        return (
                          <tr key={inv.id || idx} style={{ borderBottom: '1px solid #1e293b' }}>
                            <td style={{ padding: '6px', color: '#cbd5e1', fontFamily: 'monospace', fontSize: 12 }}>{inv.id}</td>
                            <td style={{ padding: '6px', color: '#cbd5e1' }}>{inv.series}</td>
                            <td style={{ padding: '6px', color: '#cbd5e1' }}>{(inv.date_issued || '').slice(0, 10)}</td>
                            <td style={{ padding: '6px', textAlign: 'right', color: '#e2e8f0' }}>{formatGel(inv.amount)}</td>
                            <td style={{ padding: '6px', textAlign: 'right', color: '#94a3b8' }}>{formatGel(inv.vat)}</td>
                            <td style={{ padding: '6px' }}>
                              <span style={{
                                padding: '2px 6px', fontSize: 11, borderRadius: 4,
                                background: colors.bg, color: colors.fg,
                                border: `1px solid ${colors.border}`,
                              }}>
                                {inv.status}
                              </span>
                            </td>
                            <td style={{ padding: '6px', textAlign: 'center', color: '#94a3b8' }}>
                              {inv.waybills?.length || 0}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })()}

        {/* წყარო (compact) */}
        <div className="supplier-modal-section">
          <div className="supplier-modal-section-title">🔍 წყარო</div>
          <div className="supplier-modal-row">
            <span className="supplier-modal-row-label">სახელი</span>
            <span className={`badge truth-source-badge ${officialNameSourceMeta.className}`}>
              {officialNameSourceMeta.label}
            </span>
          </div>
        </div>

        {/* შემოტანილი პროდუქცია (cross-check) */}
        <div className="supplier-modal-section">
          <div className="supplier-modal-section-title">
            📦 {importedSectionTitle}
            {importedLoading && <span className="supplier-modal-section-hint"> (იტვირთება...)</span>}
          </div>
          <div className="supplier-modal-row">
            <span className="supplier-modal-row-label">cross-check სტატუსი</span>
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
              მინიშნება — ეს ბლოკი მხოლოდ შემოწმებისთვისაა; ვალის ჯამში არ შედის და სრული სურათი შეიძლება არ იყოს.
            </div>
          )}
          {!importedLoading && !importedError && importedDetail?.match_type === 'name_fallback' && (
            <div className="supplier-modal-note supplier-modal-note--warn">
              ID-ით არა, მხოლოდ სახელის ნორმალიზებით დაემთხვა — გადაამოწმე ხელით.
            </div>
          )}
          {!importedLoading && !importedError && importedDetail?.ambiguous && !importedEntry && (
            <div className="supplier-modal-note supplier-modal-note--warn">
              სახელით რამდენიმე შესაძლო დამთხვევაა — ჩანაწერი არ ჩავწერე.
            </div>
          )}
          {!importedLoading && !importedError && !importedHasSource && (
            <div className="supplier-modal-note">cross-check წყარო ამ ეტაპზე ცარიელია.</div>
          )}
          {importedError && (
            <div className="supplier-modal-note supplier-modal-note--error">
              ბლოკის ჩატვირთვა ვერ მოხერხდა: {importedError}
            </div>
          )}

          {importedEntry && importedTopProducts.length > 0 && (
            <>
              <div className="supplier-modal-section-title" style={{ marginTop: 8, display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                <span>Top პროდუქტები</span>
                <span className="supplier-modal-section-hint">({importedTopProducts.length})</span>
                <span style={{ flex: 1 }} />
                <input
                  type="text"
                  placeholder="ძიება..."
                  value={productSearch}
                  onChange={(e) => setProductSearch(e.target.value)}
                  style={{
                    background: '#1e293b', color: '#e2e8f0',
                    border: '1px solid #334155', borderRadius: 6,
                    padding: '4px 8px', fontSize: 13, width: 140,
                  }}
                />
                <select
                  value={productLimit}
                  onChange={(e) => setProductLimit(Number(e.target.value))}
                  style={{
                    background: '#1e293b', color: '#e2e8f0',
                    border: '1px solid #334155', borderRadius: 6,
                    padding: '4px 8px', fontSize: 13,
                  }}
                >
                  <option value={20}>20</option>
                  <option value={30}>30</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
              <div className="supplier-modal-products">
                {filteredTopProducts.map((product, index) => (
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
                {filteredTopProducts.length === 0 && productSearch.trim() && (
                  <div className="supplier-modal-product" style={{ color: '#94a3b8', fontStyle: 'italic' }}>
                    ძიებაზე „{productSearch}" პროდუქტი ვერ მოიძებნა.
                  </div>
                )}
              </div>
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
