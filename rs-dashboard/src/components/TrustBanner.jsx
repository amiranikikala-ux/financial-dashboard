import { useState } from 'react';

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
    label: 'ბანკით დადასტურებული',
    amountKey: 'strict_bank_only_total',
    countKey: 'strict_supplier_count',
    modifier: 'strict',
  },
  {
    key: 'manual',
    label: 'ნაღდი / ჟურნალი',
    amountKey: 'manual_journal_total',
    countKey: 'manual_supplier_count',
    modifier: 'manual',
  },
  {
    key: 'combined',
    label: 'სულ გადახდილი',
    amountKey: 'combined_supplier_paid_total',
    countKey: 'combined_supplier_count',
    modifier: 'combined',
  },
];

function formatMoney(value) {
  return GEL.format(Number(value) || 0);
}

// Frontend overrides for backend-supplied strings that still mix English with Georgian.
// Map exact source phrase → fully Georgian equivalent. Unknown strings pass through.
const KA_TEXT_OVERRIDES = {
  'RS truth + strict bank reconciliation + manual journal.':
    'RS-ის ჭეშმარიტება + ბანკის შედარება + ჟურნალი',
  'supplier debt იყენებს RS effective totals-ს.':
    'ვალი იანგარიშება RS-ის რეალური ბრუნვის მიხედვით.',
  'total_paid მოიცავს strict bank matches-ს და manual/off-bank journal-ს ცალკე breakdown-ით.':
    '„სულ გადახდილი" მოიცავს ბანკით დადასტურებულსა და ნაღდი/ჟურნალის გადახდებს ცალ-ცალკე.',
};

function toGeorgian(text) {
  const trimmed = String(text || '').trim();
  return KA_TEXT_OVERRIDES[trimmed] || text;
}

function buildPaymentSplitCards(summary, localExtraTotal = 0) {
  return PAYMENT_SPLIT_CARD_CONFIG.map((card) => {
    const baseAmount = Number(summary?.[card.amountKey]) || 0;
    const localBoost =
      card.key === 'manual' || card.key === 'combined' ? localExtraTotal : 0;
    return {
      ...card,
      amount: baseAmount + localBoost,
      localBoost,
      supplierCount: Number(summary?.[card.countKey]) || 0,
    };
  });
}

function buildPaymentScopeBadges(summary) {
  return [
    {
      key: 'strict-only',
      label: `მხოლოდ ბანკი ${Number(summary?.strict_only_supplier_count) || 0}`,
      className: 'payment-scope-badge--strict',
    },
    {
      key: 'manual-only',
      label: `მხოლოდ ნაღდი ${Number(summary?.manual_only_supplier_count) || 0}`,
      className: 'payment-scope-badge--manual',
    },
    {
      key: 'overlap',
      label: `ორივე ${Number(summary?.strict_and_manual_overlap_count) || 0}`,
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
      label: `რეგისტრიდან ${registryPrimary}`,
    },
    {
      key: 'rs',
      className: 'truth-source-badge--rs',
      label: `RS სარეზერვო ${rsBackstop}`,
    },
    {
      key: 'legacy',
      className: 'truth-source-badge--legacy',
      label: `მხოლოდ აუდიტი ${legacyAssist}`,
    },
  ];
}

export default function TrustBanner({
  responseMeta,
  waybillsSummary,
  paymentScopeSummary,
  truthBoundarySummary,
  suppliersOnlyJournalOrBank,
  localPayments,
}) {
  const [sourceExpanded, setSourceExpanded] = useState(false);

  if (!responseMeta) return null;

  const notes = Array.isArray(responseMeta.notes_ka) ? responseMeta.notes_ka : [];
  const scopeNotes = Array.isArray(paymentScopeSummary?.scope_notes)
    ? paymentScopeSummary.scope_notes.filter(Boolean)
    : [];
  const partialReason = responseMeta.partial_reason || '';
  const trustClass = TRUST_CLASS_BY_LABEL[responseMeta.trust_label] || 'trust-banner--derived';
  const showPaymentScope =
    responseMeta.tab === 'suppliers' || responseMeta.tab === 'working_capital';
  const localExtraTotal = Object.values(localPayments || {}).reduce(
    (sum, v) => sum + (Number(v) || 0),
    0,
  );
  const allPaymentSplitCards = buildPaymentSplitCards(paymentScopeSummary, localExtraTotal);
  const manualCardAmount = allPaymentSplitCards.find((c) => c.key === 'manual')?.amount || 0;
  const hasManualPayments = manualCardAmount > 0;
  const paymentSplitCards = hasManualPayments
    ? allPaymentSplitCards
    : allPaymentSplitCards.filter((c) => c.key === 'combined');
  const paymentScopeBadges = buildPaymentScopeBadges(paymentScopeSummary);
  const showWaybillPartial = responseMeta.tab === 'waybills' && Boolean(waybillsSummary?.has_more);
  const truthBoundaryBadges = buildTruthBoundaryBadges(truthBoundarySummary);
  const truthBoundarySummaryText = String(truthBoundarySummary?.summary_ka || '').trim();

  const sourceSummaryParts = [
    ...paymentScopeBadges.map((b) => b.label),
    ...truthBoundaryBadges.map((b) => b.label),
  ];

  return (
    <div className={`trust-banner ${trustClass}`} role="note">
      <div className="trust-banner-header">
        <span className="trust-banner-badge">{responseMeta.trust_badge_ka || 'Derived'}</span>
        <div className="trust-banner-headline">
          <span className="trust-banner-scope">
            {toGeorgian(responseMeta.scope_ka) || 'დამხმარე ანალიტიკური ხედვა.'}
          </span>
          {showPaymentScope && hasManualPayments ? (
            <span className="trust-banner-hint">
              ბანკი და ნაღდი ცალ-ცალკე ჩანს
            </span>
          ) : null}
        </div>
      </div>

      {showPaymentScope ? (
        <div className={`trust-banner-stats ${hasManualPayments ? '' : 'trust-banner-stats--single'}`}>
          {paymentSplitCards.map((card) => (
            <div key={card.key} className={`trust-stat trust-stat--${card.modifier}`}>
              <div className="trust-stat-head">
                <span className="trust-stat-dot" aria-hidden="true" />
                <span className="trust-stat-label">{card.label}</span>
              </div>
              <div className="trust-stat-value">{formatMoney(card.amount)}</div>
              {card.localBoost > 0 ? (
                <div className="trust-stat-local" title="ბრაუზერში ჩაწერილი გადახდები">
                  +{formatMoney(card.localBoost)} ბრაუზერიდან
                </div>
              ) : null}
              <div className="trust-stat-sub">
                {card.supplierCount} მომწოდებელი
                {!hasManualPayments && card.key === 'combined' ? ' · ბანკით 100%' : ''}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {showPaymentScope && suppliersOnlyJournalOrBank > 0 ? (
        <div className="trust-banner-warn">
          <span className="trust-banner-warn-icon" aria-hidden="true">!</span>
          <span>
            RS-ის გარეშე გადახდა: <strong>{suppliersOnlyJournalOrBank}</strong> მომწოდებელი
          </span>
        </div>
      ) : null}

      {showPaymentScope ? (
        <>
          <button
            type="button"
            className={`trust-banner-source-toggle ${sourceExpanded ? 'is-expanded' : ''}`}
            onClick={() => setSourceExpanded((v) => !v)}
            aria-expanded={sourceExpanded}
          >
            <span className="trust-banner-source-chev" aria-hidden="true">▾</span>
            <span className="trust-banner-source-label">წყარო და დაფარვა</span>
            {!sourceExpanded ? (
              <span className="trust-banner-source-summary">
                {sourceSummaryParts.join(' · ')}
              </span>
            ) : null}
          </button>

          {sourceExpanded ? (
            <div className="trust-banner-source-panels">
              <div className="trust-banner-source-panel">
                <div className="trust-banner-source-title">გადახდის წყარო</div>
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
              <div className="trust-banner-source-panel">
                <div className="trust-banner-source-title">მონაცემის საზღვარი</div>
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
        </>
      ) : null}

      {showWaybillPartial ? (
        <div className="trust-banner-warn">
          <span className="trust-banner-warn-icon" aria-hidden="true">!</span>
          <span>
            ეკრანზე ჩანს მხოლოდ {waybillsSummary.returned_count || 0} ჩანაწერი {waybillsSummary.total_count || 0}-დან.
          </span>
        </div>
      ) : null}

      {responseMeta.partial ? (
        <div className="trust-banner-warn">
          <span className="trust-banner-warn-icon" aria-hidden="true">!</span>
          <span>Partial view: {partialReason || 'ეს tab არასრულ view-ს აჩვენებს.'}</span>
        </div>
      ) : null}

      {notes.length > 0 ? (
        <div className="trust-banner-notes">{notes.map(toGeorgian).join(' · ')}</div>
      ) : null}
    </div>
  );
}
