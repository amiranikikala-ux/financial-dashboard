const GEL = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  maximumFractionDigits: 0,
});

const TRUST_CLASS_BY_LABEL = {
  audited: 'trust-banner--audited',
  'classified-bank': 'trust-banner--classified',
  derived: 'trust-banner--derived',
  forecast: 'trust-banner--forecast',
  'plan-vs-actual': 'trust-banner--budget',
  'management-summary': 'trust-banner--executive',
  'reference-only': 'trust-banner--reference',
};

const PAYMENT_SPLIT_CARD_CONFIG = [
  {
    key: 'strict',
    label: 'Strict ბანკი',
    amountKey: 'strict_bank_only_total',
    countKey: 'strict_supplier_count',
    className: 'trust-banner-split-card--strict',
  },
  {
    key: 'manual',
    label: 'Manual / off-bank',
    amountKey: 'manual_journal_total',
    countKey: 'manual_supplier_count',
    className: 'trust-banner-split-card--manual',
  },
  {
    key: 'combined',
    label: 'Supplier total_paid',
    amountKey: 'combined_supplier_paid_total',
    countKey: 'combined_supplier_count',
    className: 'trust-banner-split-card--combined',
  },
];

function formatMoney(value) {
  return GEL.format(Number(value) || 0);
}

function buildPaymentSplitCards(summary) {
  return PAYMENT_SPLIT_CARD_CONFIG.map((card) => ({
    ...card,
    amount: Number(summary?.[card.amountKey]) || 0,
    supplierCount: Number(summary?.[card.countKey]) || 0,
  }));
}

function buildPaymentScopeBadges(summary) {
  return [
    {
      key: 'strict-only',
      label: `strict-only ${Number(summary?.strict_only_supplier_count) || 0}`,
      className: 'payment-scope-badge--strict',
    },
    {
      key: 'manual-only',
      label: `manual-only ${Number(summary?.manual_only_supplier_count) || 0}`,
      className: 'payment-scope-badge--manual',
    },
    {
      key: 'overlap',
      label: `strict + manual ${Number(summary?.strict_and_manual_overlap_count) || 0}`,
      className: 'payment-scope-badge--split',
    },
  ];
}

function buildTruthBoundaryBadges(summary) {
  const registryPrimary = Number(summary?.registry_primary_supplier_count) || 0;
  const rsBackstop = Number(summary?.rs_backstop_supplier_count) || 0;
  const legacyAssist = Number(summary?.legacy_truth_assist_supplier_count) || 0;
  return [
    {
      key: 'registry',
      className: 'truth-source-badge--registry',
      label: `registry primary ${registryPrimary}`,
    },
    {
      key: 'rs',
      className: 'truth-source-badge--rs',
      label: `RS backstop ${rsBackstop}`,
    },
    {
      key: 'legacy',
      className: 'truth-source-badge--legacy',
      label: `legacy audit-only ${legacyAssist}`,
    },
  ];
}

export default function TrustBanner({
  responseMeta,
  waybillsSummary,
  paymentScopeSummary,
  truthBoundarySummary,
  suppliersOnlyJournalOrBank,
}) {
  if (!responseMeta) return null;

  const notes = Array.isArray(responseMeta.notes_ka) ? responseMeta.notes_ka : [];
  const scopeNotes = Array.isArray(paymentScopeSummary?.scope_notes)
    ? paymentScopeSummary.scope_notes.filter(Boolean)
    : [];
  const partialReason = responseMeta.partial_reason || '';
  const trustClass = TRUST_CLASS_BY_LABEL[responseMeta.trust_label] || 'trust-banner--derived';
  const showPaymentScope =
    responseMeta.tab === 'suppliers' || responseMeta.tab === 'working_capital';
  const paymentSplitCards = buildPaymentSplitCards(paymentScopeSummary);
  const paymentScopeBadges = buildPaymentScopeBadges(paymentScopeSummary);
  const showWaybillPartial = responseMeta.tab === 'waybills' && Boolean(waybillsSummary?.has_more);
  const truthBoundaryBadges = buildTruthBoundaryBadges(truthBoundarySummary);
  const truthBoundarySummaryText = String(truthBoundarySummary?.summary_ka || '').trim();

  return (
    <div className={`trust-banner ${trustClass}`} role="note">
      <div className="trust-banner-main">
        <span className="badge muted">{responseMeta.trust_badge_ka || 'Derived'}</span>
        <div className="trust-banner-main-copy">
          <span>{responseMeta.scope_ka || 'დამხმარე ანალიტიკური ხედვა.'}</span>
          {showPaymentScope ? (
            <span className="trust-banner-main-hint">
              supplier paid ახლა strict bank-ს და manual/off-bank ჟურნალს ცალ-ცალკე ხსნის.
            </span>
          ) : null}
        </div>
      </div>

      {showPaymentScope ? (
        <div className="trust-banner-split-grid">
          {paymentSplitCards.map((card) => (
            <div key={card.key} className={`trust-banner-split-card ${card.className}`}>
              <div className="trust-banner-split-label">{card.label}</div>
              <div className="trust-banner-split-value">{formatMoney(card.amount)}</div>
              <div className="trust-banner-split-sub">{card.supplierCount} მომწოდებელი</div>
            </div>
          ))}
        </div>
      ) : null}

      {showPaymentScope && suppliersOnlyJournalOrBank > 0 ? (
        <div className="trust-banner-sub trust-banner-sub--warn">
          RS-ის გარეშე supplier row: {suppliersOnlyJournalOrBank}
        </div>
      ) : null}

      {showPaymentScope ? (
        <div className="trust-banner-context-grid">
          <div className="trust-banner-context-card">
            <div className="trust-banner-context-title">Supplier payment scope</div>
            <div className="trust-banner-badges">
              {paymentScopeBadges.map((item) => (
                <span
                  key={item.key}
                  className={`badge payment-scope-badge ${item.className}`}
                >
                  {item.label}
                </span>
              ))}
            </div>
            {scopeNotes.length > 0 ? (
              <div className="trust-banner-notes">{scopeNotes.join(' ')}</div>
            ) : null}
          </div>
          <div className="trust-banner-context-card">
            <div className="trust-banner-context-title">Truth boundary</div>
            <div className="trust-banner-badges">
              {truthBoundaryBadges.map((item) => (
                <span
                  key={item.key}
                  className={`badge truth-source-badge ${item.className}`}
                >
                  {item.label}
                </span>
              ))}
            </div>
            {truthBoundarySummaryText ? (
              <div className="trust-banner-notes">{truthBoundarySummaryText}</div>
            ) : null}
          </div>
        </div>
      ) : null}

      {showWaybillPartial ? (
        <div className="trust-banner-sub trust-banner-sub--warn">
          ეკრანზე ჩანს მხოლოდ {waybillsSummary.returned_count || 0} ჩანაწერი {waybillsSummary.total_count || 0}-დან.
        </div>
      ) : null}

      {responseMeta.partial ? (
        <div className="trust-banner-sub trust-banner-sub--warn">
          Partial view: {partialReason || 'ეს tab არასრულ view-ს აჩვენებს.'}
        </div>
      ) : null}

      {notes.length > 0 ? (
        <div className="trust-banner-notes">{notes.join(' · ')}</div>
      ) : null}
    </div>
  );
}
