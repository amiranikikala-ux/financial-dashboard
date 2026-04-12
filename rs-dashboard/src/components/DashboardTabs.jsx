import { TAB_GROUPS } from '../tabConfig.js';

export default function DashboardTabs({ activeTab, onTabChange }) {
  return (
    <nav className="tabs-nav">
      {TAB_GROUPS.map((group, index) => (
        <div key={group.id} className={`tabs ${index === 0 ? 'tabs-row-1' : 'tabs-row-2'}`}>
          <span className="tabs-group-label">{group.label}</span>
          {group.items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`tab-btn ${activeTab === item.id ? 'active' : ''}`}
              onClick={() => onTabChange(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      ))}
    </nav>
  );
}
