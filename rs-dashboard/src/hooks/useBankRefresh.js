import { useCallback, useEffect, useRef, useState } from 'react';

const POLL_MS = 2000;

const EMPTY_BANKS = { bog: null, rsge: null, tbc: null };

export default function useBankRefresh({ onComplete } = {}) {
  const [state, setState] = useState('idle');
  const [perBank, setPerBank] = useState(EMPTY_BANKS);
  const [pipelineState, setPipelineState] = useState(null);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);
  const completeFiredRef = useRef(false);
  const onCompleteRef = useRef(onComplete);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const pollOnce = useCallback(async () => {
    try {
      const res = await fetch('/api/status');
      if (!res.ok) return;
      const json = await res.json();
      const br = json.bank_refresh || {};
      const pl = json.pipeline || {};
      setPipelineState(pl.state || null);
      if (br.last_result) {
        setPerBank({
          bog: br.last_result.bog || null,
          rsge: br.last_result.rsge || null,
          tbc: br.last_result.tbc || null,
        });
      }
      if (br.state === 'running') return;

      if (br.state === 'error') {
        stopPolling();
        setError(br.last_error || 'უცნობი შეცდომა ბანკის მონაცემების ჩამოტანისას');
        setState('error');
        return;
      }

      if (br.state === 'idle') {
        if (pl.state === 'running') return;
        stopPolling();
        setState('done');
        if (!completeFiredRef.current) {
          completeFiredRef.current = true;
          onCompleteRef.current?.();
        }
      }
    } catch {
      // silent — next tick will retry
    }
  }, [stopPolling]);

  const start = useCallback(
    async (nonce) => {
      stopPolling();
      completeFiredRef.current = false;
      setState('starting');
      setError(null);
      setPerBank(EMPTY_BANKS);
      setPipelineState(null);
      try {
        const res = await fetch('/api/banks/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ nonce }),
        });
        if (!res.ok) {
          let detail = `HTTP ${res.status}`;
          try {
            const j = await res.json();
            detail = j.detail || detail;
          } catch {
            /* ignore — keep HTTP code */
          }
          setError(detail);
          setState('error');
          return;
        }
        setState('running');
        pollRef.current = setInterval(pollOnce, POLL_MS);
        pollOnce();
      } catch (e) {
        setError(e?.message || 'მოთხოვნა ვერ შესრულდა');
        setState('error');
      }
    },
    [pollOnce, stopPolling],
  );

  const reset = useCallback(() => {
    stopPolling();
    completeFiredRef.current = false;
    setState('idle');
    setError(null);
    setPerBank(EMPTY_BANKS);
    setPipelineState(null);
  }, [stopPolling]);

  return { state, perBank, pipelineState, error, start, reset };
}
