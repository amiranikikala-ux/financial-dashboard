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

function buildPaymentSplitCards(summary, localExtraTotal = 0, localExtraSuppliers = 0) {
  return PAYMENT_SPLIT_CARD_CONFIG.map((card) => {
    const baseAmount = Number(summary?.[card.amountKey]) || 0;
    const localBoost =
      card.key === 'manual' || card.key === 'combined' ? localExtraTotal : 0;
    const localSupplierBoost =
      card.key === 'manual' || card.key === 'combined' ? localExtraSuppliers : 0;
    const baseCount = Number(summary?.[card.countKey]) || 0;
    return {
      ...card,
      amount: baseAmount + localBoost,
      localBoost,
      // ბრაუზერიდან ჩაწერილი მომწოდებლები ბექენდის count-ში არ ფიგურირებენ,
      // ამიტომ ვამატებთ — სხვაგვარად card-ი ჩვენებს „X ₾ → 0 მომწოდებელი".
      supplierCount: baseCount + localSupplierBoost,
      localSupplierBoost,
    };
  });
}

export default function TrustBanner({
  responseMeta,
  waybillsSummary,
  paymentScopeSummary,
  suppliersOnlyJournalOrBank,
  localPayments,
}) {
  if (!responseMeta) return null;

  const notes = Array.isArray(responseMeta.notes_ka) ? responseMeta.notes_ka : [];
  const partialReason = responseMeta.partial_reason || '';
  const trustClass = TRUST_CLASS_BY_LABEL[responseMeta.trust_label] || 'trust-banner--derived';
  const showPaymentScope =
    responseMeta.tab === 'suppliers' || responseMeta.tab === 'working_capital';
  const localExtraTotal = Object.values(localPayments || {}).reduce(
    (sum, v) => sum + (Number(v) || 0),
    0,
  );
  const localExtraSuppliers = Object.values(localPayments || {}).filter(
    (v) => Number(v) > 0,
  ).length;
  const allPaymentSplitCards = buildPaymentSplitCards(
    paymentScopeSummary,
    localExtraTotal,
    localExtraSuppliers,
  );
  const manualCardAmount = allPaymentSplitCards.find((c) => c.key === 'manual')?.amount || 0;
  const hasManualPayments = manualCardAmount > 0;
  // ყოველთვის 3 ბარათი ვაჩვენოთ — ბანკი / ნაღდი / სულ — რათა owner-მა
  // ცხადად დაინახოს რომ ნაღდი ცარიელია (0 ₾) როცა ცარიელია, და ცხადად
  // დაინახოს breakdown როცა ნაღდი ფიქსირდება. ერთ-ბარათიანი ხედვა
  // (მხოლოდ „სულ გადახდილი") owner-ისთვის ცრუ ალარმს ქმნიდა — „აქ სად
  // გაქრა ჩემი ნაღდი ფული?".
  const paymentSplitCards = allPaymentSplitCards;
  const showWaybillPartial = responseMeta.tab === 'waybills' && Boolean(waybillsSummary?.has_more);

  return (
    <div className={`trust-banner ${trustClass}`} role="note">
      <div className="trust-banner-header">
        <span className="trust-banner-badge">{responseMeta.trust_badge_ka || 'Derived'}</span>
        <div className="trust-banner-headline">
          <span className="trust-banner-scope">
            {toGeorgian(responseMeta.scope_ka) || 'დამხმარე ანალიტიკური ხედვა.'}
          </span>
          {showPaymentScope ? (
            <span className="trust-banner-hint">
              ბანკი და ნაღდი ცალ-ცალკე
            </span>
          ) : null}
        </div>
      </div>

      {showPaymentScope ? (
        <div className="trust-banner-stats">
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
