import { useEffect, useState } from 'react';
import { isValidTab } from '../tabConfig.js';

function readHashTab(defaultTab) {
  if (typeof window === 'undefined') return defaultTab;
  const raw = String(window.location.hash || '').replace(/^#/, '').trim();
  return isValidTab(raw) ? raw : defaultTab;
}

export default function useHashTab(defaultTab = 'suppliers') {
  const [activeTab, setActiveTab] = useState(() => readHashTab(defaultTab));

  useEffect(() => {
    const onHashChange = () => {
      setActiveTab(readHashTab(defaultTab));
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, [defaultTab]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const nextHash = `#${activeTab}`;
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, '', nextHash);
    }
  }, [activeTab]);

  return [activeTab, setActiveTab];
}
