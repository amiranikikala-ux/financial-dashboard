/**
 * AI Advisor — fetch wrappers for /api/chat (sync) and /api/chat/stream (SSE).
 * Adds X-API-Key + Content-Type headers, parses JSON, surfaces API errors.
 */

const API_KEY = import.meta.env.VITE_API_KEY || '';

function buildHeaders() {
  const headers = new Headers();
  headers.set('Content-Type', 'application/json');
  if (API_KEY) {
    headers.set('X-API-Key', API_KEY);
  }
  return headers;
}

/**
 * Send a chat turn to the backend (non-streaming).
 *
 * @param {string} message — user text
 * @param {Array} history — optional prior messages array (from last response)
 * @param {string} [mode] — optional "chat" | "investigate"; omitted from body when falsy
 * @param {boolean} [think] — Phase 0B.1 Extended Thinking opt-in; omitted when falsy
 * @param {AbortSignal} signal — optional abort signal
 * @returns {Promise<{reply: string, sources: Array, usage: object, history: Array}>}
 */
export async function postChat({ message, history = [], mode, think, signal } = {}) {
  if (typeof message !== 'string' || !message.trim()) {
    throw new Error('message must be a non-empty string');
  }

  const body = { message, history };
  if (typeof mode === 'string' && mode.trim()) {
    body.mode = mode;
  }
  if (think === true) {
    body.think = true;
  }

  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(body),
    signal,
  });

  let payload = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }

  if (!res.ok) {
    const detail = payload && typeof payload.detail === 'string' ? payload.detail : null;
    const err = new Error(detail || `AI chat failed (HTTP ${res.status})`);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }

  if (!payload || typeof payload.reply !== 'string') {
    throw new Error('AI chat returned an invalid response');
  }
  return payload;
}

// ---------------------------------------------------------------------------
// Streaming (Server-Sent Events)
// ---------------------------------------------------------------------------

/**
 * Parse one SSE event block (`event: <type>\n` + `data: <json>\n`).
 *
 * @param {string} block
 * @returns {{type: string, data: any} | null}
 */
export function parseSseEventBlock(block) {
  let eventType = null;
  const dataLines = [];
  for (const rawLine of block.split('\n')) {
    const line = rawLine.replace(/\r$/, '');
    if (line === '' || line.startsWith(':')) continue;
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      let content = line.slice(5);
      if (content.startsWith(' ')) content = content.slice(1);
      dataLines.push(content);
    }
  }
  if (!dataLines.length) return null;
  const dataStr = dataLines.join('\n');
  try {
    return { type: eventType || 'message', data: JSON.parse(dataStr) };
  } catch {
    return { type: eventType || 'message', data: dataStr };
  }
}

/**
 * Stream a chat turn from `/api/chat/stream` as Server-Sent Events.
 *
 * Backend emits these event types in order:
 *   delta        — incremental text (repeated many times)
 *   tool_call    — before each tool dispatch
 *   tool_result  — after each tool resolves
 *   sources      — final tool-call trace
 *   usage        — token counts + cache metrics
 *   history      — full backend history array for next turn
 *   done         — stream terminator with final reply + stop_reason
 *   error        — fatal error (stream ends)
 *
 * @param {object} opts
 * @param {string} opts.message
 * @param {Array} [opts.history]
 * @param {string} [opts.mode] — optional "chat" | "investigate"; omitted from body when falsy
 * @param {boolean} [opts.think] — Phase 0B.1 Extended Thinking opt-in; omitted when falsy
 * @param {AbortSignal} [opts.signal]
 * @param {(event: {type: string, data: any}) => void} opts.onEvent
 * @returns {Promise<void>} resolves when the stream completes or aborts
 */
export async function postChatStream({
  message,
  history = [],
  mode,
  think,
  signal,
  onEvent,
} = {}) {
  if (typeof message !== 'string' || !message.trim()) {
    throw new Error('message must be a non-empty string');
  }
  if (typeof onEvent !== 'function') {
    throw new Error('onEvent callback is required');
  }

  const body = { message, history };
  if (typeof mode === 'string' && mode.trim()) {
    body.mode = mode;
  }
  if (think === true) {
    body.think = true;
  }

  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    // Non-streaming error (400/503/etc.) — body is JSON, not SSE.
    let detail = null;
    try {
      const payload = await res.json();
      if (payload && typeof payload.detail === 'string') detail = payload.detail;
    } catch {
      /* ignore */
    }
    const err = new Error(detail || `AI chat stream failed (HTTP ${res.status})`);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }

  if (!res.body) {
    throw new Error('AI chat stream: response has no body');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    // Read loop — chunks may split events across reads; buffer + split.
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const parsed = parseSseEventBlock(block);
        if (parsed) onEvent(parsed);
      }
    }
    // Flush any trailing fragment.
    buffer += decoder.decode();
    if (buffer.trim()) {
      const parsed = parseSseEventBlock(buffer);
      if (parsed) onEvent(parsed);
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* no-op */
    }
  }
}
