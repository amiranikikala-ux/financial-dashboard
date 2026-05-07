export const TAB_GROUPS = [
  {
    id: 'daily',
    label: 'ყოველდღიური',
    items: [
      { id: 'suppliers', label: '🏢 მომწოდებლები' },
      { id: 'waybills', label: '📄 ზედნადებები' },
      { id: 'waybill_reconciliation', label: '🔍 ზედნადებების შემოწმება' },
      { id: 'cashflow', label: '💳 ბანკი' },
      { id: 'analytics', label: '📊 ანალიტიკა' },
    ],
  },
  {
    id: 'sales',
    label: 'გაყიდვები',
    items: [
      { id: 'retail_sales', label: '🛒 გაყიდვები' },
      { id: 'imported_products', label: '📦 პროდუქცია' },
      { id: 'orphan_products', label: '⚠️ შეუსაბამო პროდუქცია' },
      { id: 'duplicate_products', label: '👥 დუბლიკატები' },
      { id: 'store_compare', label: '🏬 მაღაზიები' },
      { id: 'category_anomalies', label: '🚨 კატეგორიები' },
      { id: 'dead_stock', label: '💀 Dead Stock' },
    ],
  },
  {
    id: 'finance',
    label: 'ფინანსები',
    items: [
      { id: 'pnl', label: '📈 P&L' },
      { id: 'working_capital', label: '💰 კაპიტალი' },
      { id: 'ratios', label: '📐 კოეფ.' },
      { id: 'debt_plan', label: '📋 ვალების გეგმა' },
      { id: 'foodmart_360', label: '🎯 ფუდმარტი 360°' },
    ],
  },
  {
    id: 'strategy',
    label: 'სტრატეგია',
    items: [
      { id: 'forecast', label: '🔮 პროგნოზი' },
      { id: 'budget', label: '📋 ბიუჯეტი' },
      { id: 'valuation', label: '🏆 შეფასება' },
      { id: 'executive', label: '👔 Executive' },
      { id: 'insights', label: '🧠 ინსაითები' },
      { id: 'vat_audit', label: '🧾 VAT & აუდიტი' },
    ],
  },
];

export const VALID_TABS = TAB_GROUPS.flatMap((group) => group.items.map((item) => item.id));

export function isValidTab(tab) {
  return VALID_TABS.includes(tab);
}
