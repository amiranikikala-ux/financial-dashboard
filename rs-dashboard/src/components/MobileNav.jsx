import { useState } from 'react';
import { TAB_GROUPS } from '../tabConfig.js';

const QUICK_TABS = [
  { id: 'suppliers', icon: '🏢', label: 'მომწოდ.' },
  { id: 'waybills', icon: '📄', label: 'ზედნად.' },
  { id: 'cashflow', icon: '💳', label: 'ბანკი' },
  { id: 'executive', icon: '👔', label: 'Exec' },
];

const ALL_TABS = TAB_GROUPS.flatMap((g) => g.items);

export default function MobileNav({ activeTab, onTabChange }) {
  const [showAll, setShowAll] = useState(false);

  const handleTabClick = (id) => {
    onTabChange(id);
    setShowAll(false);
  };

  return (
    <>
      {showAll && (
        <div className="mobile-nav-overlay" onClick={() => setShowAll(false)}>
          <div className="mobile-nav-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="mobile-nav-sheet-title">ტაბები</div>
            <div className="mobile-nav-grid">
              {ALL_TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`mobile-nav-grid-btn ${activeTab === t.id ? 'active' : ''}`}
                  onClick={() => handleTabClick(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
      <nav className="mobile-bottom-nav">
        {QUICK_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`mobile-nav-btn ${activeTab === t.id ? 'active' : ''}`}
            onClick={() => handleTabClick(t.id)}
          >
            <span className="mobile-nav-icon">{t.icon}</span>
            <span className="mobile-nav-label">{t.label}</span>
          </button>
        ))}
        <button
          type="button"
          className={`mobile-nav-btn ${showAll ? 'active' : ''}`}
          onClick={() => setShowAll((v) => !v)}
        >
          <span className="mobile-nav-icon">⋯</span>
          <span className="mobile-nav-label">სხვა</span>
        </button>
      </nav>
    </>
  );
}
