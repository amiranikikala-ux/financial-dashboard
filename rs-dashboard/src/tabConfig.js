export const TAB_GROUPS = [
  {
    id: 'daily',
    label: 'ყოველდღიური',
    items: [
      { id: 'suppliers', label: '🏢 მომწოდებლები' },
      { id: 'waybills', label: '📄 ზედნადებები' },
      { id: 'analytics', label: '📊 ანალიტიკა' },
      { id: 'cashflow', label: '💳 ბანკი' },
    ],
  },
  {
    id: 'analytical',
    label: 'ანალიტიკური',
    items: [
      { id: 'imported_products', label: '📦 პროდუქცია' },
      { id: 'retail_sales', label: '🛒 გაყიდვები' },
      { id: 'dead_stock', label: '💀 Dead Stock' },
      { id: 'debt_plan', label: '📋 ვალების გეგმა' },
      { id: 'pnl', label: '📈 P&L' },
      { id: 'working_capital', label: '💰 კაპიტალი' },
      { id: 'ratios', label: '📐 კოეფ.' },
      { id: 'forecast', label: '🔮 პროგნოზი' },
      { id: 'budget', label: '📋 ბიუჯეტი' },
      { id: 'valuation', label: '🏆 შეფასება' },
      { id: 'executive', label: '👔 Executive' },
      { id: 'insights', label: '🧠 ინსაითები' },
      { id: 'store_compare', label: '🏬 მაღაზიები' },
      { id: 'vat_audit', label: '🧾 VAT & აუდიტი' },
    ],
  },
];

export const VALID_TABS = TAB_GROUPS.flatMap((group) => group.items.map((item) => item.id));

export function isValidTab(tab) {
  return VALID_TABS.includes(tab);
}
