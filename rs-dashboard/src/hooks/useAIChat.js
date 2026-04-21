import { useCallback, useRef, useState } from 'react';
import { postChatStream } from '../lib/aiClient.js';

const MAX_TRANSCRIPT_ENTRIES = 50;

/**
 * Chat state hook for ChatAssistant.
 *
 * transcript — UI-facing message list:
 *   { id, role: 'user' | 'assistant', text, sources?, usage?,
 *     pending?, streaming?, toolCalls?, error? }
 *
 * backendHistory — raw Anthropic-style messages array that the API expects
 * for context continuity. Trimmed to avoid unbounded growth.
 */
export default function useAIChat() {
  const [transcript, setTranscript] = useState([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const backendHistoryRef = useRef([]);
  const abortRef = useRef(null);
  const idRef = useRef(0);

  const nextId = useCallback(() => {
    idRef.current += 1;
    return `msg-${idRef.current}`;
  }, []);

  const send = useCallback(async (rawMessage, options = {}) => {
    const message = (rawMessage || '').trim();
    if (!message || sending) return;

    // Optional mode ("chat" | "investigate"). Omitted when falsy so the
    // backend falls back to DEFAULT_MODE. The exact same resolved mode is
    // stamped onto the assistant entry so UI gating (e.g., Cascade-for-copy
    // block) can rely on entry.mode before the usage event lands.
    const requestedMode =
      typeof options?.mode === 'string' && options.mode.trim()
        ? options.mode.trim()
        : null;

    // Phase 0B.1 — Extended Thinking opt-in. Only literal `true` triggers
    // the extra body field; any other value is ignored (matches
    // aiClient.postChatStream contract). Server's upstream AI_ENABLE_THINKING
    // env flag is the authoritative gate — this hook only reports intent.
    const requestedThink = options?.think === true;

    setError(null);
    setSending(true);

    const userId = nextId();
    const assistantId = nextId();

    setTranscript((prev) => {
      const newTranscript = [
        ...prev,
        { id: userId, role: 'user', text: message },
        {
          id: assistantId,
          role: 'assistant',
          text: '',
          pending: true,
          streaming: false,
          toolCalls: [],
          mode: requestedMode,
          think: requestedThink || undefined,
        },
      ];
      // Trim transcript to prevent unbounded growth
      if (newTranscript.length > MAX_TRANSCRIPT_ENTRIES) {
        return newTranscript.slice(-MAX_TRANSCRIPT_ENTRIES);
      }
      return newTranscript;
    });

    // Abort any in-flight request (shouldn't happen since sending is gated).
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    // Local accumulators — read back into state on each event to minimize
    // stale-closure races and keep the final snapshot consistent.
    let streamedText = '';
    let finalSources = [];
    let finalUsage = null;
    let finalHistory = null;
    let finalReply = '';
    let finalStopReason = null;
    const toolCalls = [];
    let streamError = null;

    const updateAssistant = (patch) => {
      setTranscript((prev) =>
        prev.map((entry) =>
          entry.id === assistantId ? { ...entry, ...patch } : entry,
        ),
      );
    };

    try {
      await postChatStream({
        message,
        history: backendHistoryRef.current,
        mode: requestedMode || undefined,
        think: requestedThink ? true : undefined,
        signal: controller.signal,
        onEvent: ({ type, data }) => {
          if (type === 'delta') {
            const chunk = data && typeof data.text === 'string' ? data.text : '';
            if (!chunk) return;
            streamedText += chunk;
            updateAssistant({
              text: streamedText,
              pending: false,
              streaming: true,
            });
          } else if (type === 'tool_call') {
            if (data && typeof data.tool === 'string') {
              toolCalls.push({
                tool: data.tool,
                arguments: data.arguments || {},
                tool_use_id: data.tool_use_id || '',
              });
              updateAssistant({ toolCalls: [...toolCalls] });
            }
          } else if (type === 'tool_result') {
            // Informational — the final `sources` event carries the full trace.
          } else if (type === 'sources') {
            finalSources = Array.isArray(data?.sources) ? data.sources : [];
          } else if (type === 'usage') {
            finalUsage = data?.usage || null;
          } else if (type === 'history') {
            finalHistory = Array.isArray(data?.history) ? data.history : [];
          } else if (type === 'done') {
            finalReply = typeof data?.reply === 'string' ? data.reply : streamedText;
            finalStopReason = data?.stop_reason || null;
          } else if (type === 'error') {
            streamError = data?.error || 'unknown stream error';
          }
        },
      });

      if (streamError) {
        throw new Error(streamError);
      }

      if (Array.isArray(finalHistory)) {
        backendHistoryRef.current = finalHistory.slice(-MAX_TRANSCRIPT_ENTRIES);
      }

      // Use server's final reply if the deltas ended up empty (e.g. tool-only
      // turn that never surfaced assistant text); otherwise keep streamed text.
      const resolvedText = streamedText || finalReply || '';
      const resolvedUsage = finalUsage
        ? { ...finalUsage, stop_reason: finalUsage.stop_reason || finalStopReason }
        : null;
      // Prefer server's echoed usage.mode (authoritative — reflects actual
      // mode used by the backend after _extract_chat_mode validation).
      const resolvedMode =
        (resolvedUsage && typeof resolvedUsage.mode === 'string' && resolvedUsage.mode) ||
        requestedMode ||
        null;

      // Phase 0B.1 — usage.thinking is the server-authoritative echo. The
      // deployment may have AI_ENABLE_THINKING=false, in which case even
      // `think: true` requests come back as `thinking: false` — UI must
      // show the actual behavior, not the user's intent.
      const resolvedThink =
        typeof resolvedUsage?.thinking === 'boolean'
          ? resolvedUsage.thinking
          : requestedThink;

      updateAssistant({
        text: resolvedText,
        sources: finalSources,
        usage: resolvedUsage,
        mode: resolvedMode,
        think: resolvedThink || undefined,
        pending: false,
        streaming: false,
      });
    } catch (err) {
      if (err.name === 'AbortError') {
        setTranscript((prev) => prev.filter((entry) => entry.id !== assistantId));
      } else {
        const msg = err.message || 'უცნობი შეცდომა';
        setError(msg);
        updateAssistant({
          text: streamedText,
          error: msg,
          pending: false,
          streaming: false,
        });
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
      setSending(false);
    }
  }, [nextId, sending]);

  const reset = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    backendHistoryRef.current = [];
    setTranscript([]);
    setError(null);
    setSending(false);
  }, []);

  return {
    transcript,
    sending,
    error,
    send,
    reset,
  };
}
