const pendingRequests = new Map();
const API_KEY = import.meta.env.VITE_API_KEY || '';

function withAuthHeaders(init) {
  if (!API_KEY) return init || {};
  const headers = new Headers(init?.headers);
  headers.set('X-API-Key', API_KEY);
  return { ...init, headers };
}

window.__apiMetrics = {
  requests: {},
  totalRequests: 0,
  errors: 0,
};

function trackApiRequest(path, error = false) {
  const endpoint = path.split('?')[0];
  window.__apiMetrics.totalRequests++;
  if (error) window.__apiMetrics.errors++;
  
  if (!window.__apiMetrics.requests[endpoint]) {
    window.__apiMetrics.requests[endpoint] = 0;
  }
  window.__apiMetrics.requests[endpoint]++;
}

export async function fetchApiJson(path, init) {
  const method = init?.method || 'GET';
  
  if (method === 'GET') {
    const cacheKey = path;
    if (pendingRequests.has(cacheKey)) {
      return pendingRequests.get(cacheKey);
    }

    const promise = fetch(path, withAuthHeaders(init))
      .then(async (res) => {
        if (!res.ok) {
          trackApiRequest(path, true);
          throw new Error(`API: HTTP ${res.status} — გაუშვი: python server.py`);
        }
        trackApiRequest(path, false);
        return res.json();
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          trackApiRequest(path, true);
        }
        throw err;
      })
      .finally(() => {
        pendingRequests.delete(cacheKey);
      });

    pendingRequests.set(cacheKey, promise);
    return promise;
  }

  try {
    const res = await fetch(path, withAuthHeaders(init));
    if (!res.ok) {
      trackApiRequest(path, true);
      throw new Error(`API: HTTP ${res.status} — გაუშვი: python server.py`);
    }
    trackApiRequest(path, false);
    return res.json();
  } catch (err) {
    if (err.name !== 'AbortError') {
      trackApiRequest(path, true);
    }
    throw err;
  }
}
