import { useState, useEffect, useCallback } from 'react';

const STATUS_POLL_MS = 15_000;

export default function useDataStatus() {
  const [status, setStatus] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/status');
      if (res.ok) {
        const json = await res.json();
        setStatus(json);
        if (json.pipeline?.state !== 'running') {
          setRefreshing(false);
        }
      }
    } catch {
      /* silent — status is best-effort */
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, STATUS_POLL_MS);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const triggerRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await fetch('/api/refresh', { method: 'POST' });
      if (!res.ok) {
        setRefreshing(false);
      }
    } catch {
      setRefreshing(false);
    }
  }, []);

  return { status, refreshing, triggerRefresh };
}
