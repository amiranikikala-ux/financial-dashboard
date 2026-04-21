import { useCallback, useEffect, useRef, useState } from 'react';
import useAIChat from '../hooks/useAIChat.js';
import ChatMessage from './ChatMessage.jsx';

const WELCOME_TEXT =
  'გამარჯობა! მე ვარ შენი ფინანსური ასისტენტი.\n' +
  'დამისვი კითხვა მონაცემებზე — ზედნადებები, მომწოდებლები, P&L, budget — და ვიპოვი პასუხს **data.json**-დან.';

const SAMPLE_PROMPTS = [
  'რამდენი მომწოდებელი გვყავს ჯამში?',
  'რა არის მიმდინარე current ratio და gross margin?',
  'რომელი 3 მომწოდებელი გვაქვს ყველაზე მეტი ვალით?',
];

const MODE_STORAGE_KEY = 'ai-advisor-mode';
const MODE_CHAT = 'chat';
const MODE_INVESTIGATE = 'investigate';
const INVESTIGATE_TOOLTIP =
  'Investigate: აღმოაჩინე შეუსაბამობები Excel \u2194 data.json \u2194 კოდს შორის';

// Phase 0B.1 — Extended Thinking (ღრმა ფიქრი).
const THINK_STORAGE_KEY = 'ai-advisor-think';
const THINK_TOOLTIP =
  'ღრმა ფიქრი: AI 30-60 წამი ფარულად ფიქრობს, უფრო ღრმა პასუხი (+$0.01-0.05/კითხვა)';

function readStoredMode() {
  if (typeof window === 'undefined' || !window.localStorage) return MODE_CHAT;
  try {
    const raw = window.localStorage.getItem(MODE_STORAGE_KEY);
    return raw === MODE_INVESTIGATE ? MODE_INVESTIGATE : MODE_CHAT;
  } catch {
    return MODE_CHAT;
  }
}

function readStoredThink() {
  if (typeof window === 'undefined' || !window.localStorage) return false;
  try {
    const raw = window.localStorage.getItem(THINK_STORAGE_KEY);
    return raw === 'true';
  } catch {
    return false;
  }
}

export default function ChatAssistant() {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [mode, setMode] = useState(readStoredMode);
  const [think, setThink] = useState(readStoredThink);
  const { transcript, sending, error, send, reset } = useAIChat();
  const listRef = useRef(null);
  const textareaRef = useRef(null);

  // Persist mode toggle to localStorage so investigate preference survives
  // reload / tab switch. Wrapped in try/catch for private-browsing safety.
  useEffect(() => {
    if (typeof window === 'undefined' || !window.localStorage) return;
    try {
      window.localStorage.setItem(MODE_STORAGE_KEY, mode);
    } catch {
      /* no-op — storage blocked */
    }
  }, [mode]);

  // Persist Deep Think preference — stored as "true" / "false" literal.
  useEffect(() => {
    if (typeof window === 'undefined' || !window.localStorage) return;
    try {
      window.localStorage.setItem(THINK_STORAGE_KEY, think ? 'true' : 'false');
    } catch {
      /* no-op — storage blocked */
    }
  }, [think]);

  const toggleMode = useCallback(() => {
    setMode((prev) => (prev === MODE_INVESTIGATE ? MODE_CHAT : MODE_INVESTIGATE));
  }, []);

  const toggleThink = useCallback(() => {
    setThink((prev) => !prev);
  }, []);

  // Auto-scroll to latest message.
  useEffect(() => {
    if (!open) return;
    const node = listRef.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [open, transcript]);

  // Focus textarea when panel opens.
  useEffect(() => {
    if (open && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [open]);

  // Close on Escape.
  useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  const onSubmit = useCallback(
    (e) => {
      if (e) e.preventDefault();
      const text = draft.trim();
      if (!text || sending) return;
      setDraft('');
      send(text, { mode, think });
    },
    [draft, send, sending, mode, think],
  );

  const onKeyDown = useCallback(
    (e) => {
      // Enter sends, Shift+Enter adds newline.
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        onSubmit();
      }
    },
    [onSubmit],
  );

  const onSamplePromptClick = useCallback(
    (prompt) => {
      if (sending) return;
      setDraft('');
      send(prompt, { mode, think });
    },
    [send, sending, mode, think],
  );

  const isEmpty = transcript.length === 0;

  return (
    <>
      <button
        type="button"
        className={`chat-fab${open ? ' chat-fab--open' : ''}`}
        aria-label={open ? 'AI ასისტენტის დახურვა' : 'AI ასისტენტის გახსნა'}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        data-testid="chat-fab"
      >
        {open ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        ) : (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            <path d="M8 10h.01M12 10h.01M16 10h.01" />
          </svg>
        )}
      </button>

      {open && (
        <div
          className="chat-panel"
          role="dialog"
          aria-modal="false"
          aria-label="AI ფინანსური ასისტენტი"
          data-testid="chat-panel"
        >
          <header className="chat-panel__header">
            <div className="chat-panel__title">
              <span className="chat-panel__title-dot" aria-hidden="true" />
              <strong>AI ასისტენტი</strong>
              <span className="chat-panel__subtitle">Claude Sonnet 4.6</span>
            </div>
            <div className="chat-panel__actions">
              {transcript.length > 0 && (
                <button
                  type="button"
                  className="chat-panel__btn-reset"
                  onClick={reset}
                  disabled={sending}
                  title="საუბრის გასუფთავება"
                >
                  გასუფთავება
                </button>
              )}
              <button
                type="button"
                className="chat-panel__btn-close"
                aria-label="დახურვა"
                onClick={() => setOpen(false)}
              >
                ×
              </button>
            </div>
          </header>

          <div className="chat-panel__body" ref={listRef} data-testid="chat-transcript">
            {isEmpty && (
              <div className="chat-panel__welcome">
                <div className="chat-panel__welcome-text">
                  {WELCOME_TEXT.split('\n').map((line, idx) => (
                    <p key={idx}>{line}</p>
                  ))}
                </div>
                <div className="chat-panel__samples">
                  {SAMPLE_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      className="chat-panel__sample"
                      onClick={() => onSamplePromptClick(prompt)}
                      disabled={sending}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {transcript.map((entry) => (
              <ChatMessage key={entry.id} entry={entry} />
            ))}
          </div>

          {error && !transcript.some((e) => e.error) && (
            <div className="chat-panel__global-error" role="alert">
              ⚠️ {error}
            </div>
          )}

          <form className="chat-panel__composer" onSubmit={onSubmit}>
            <button
              type="button"
              className={`chat-panel__btn-mode${mode === MODE_INVESTIGATE ? ' chat-panel__btn-mode--active' : ''}`}
              onClick={toggleMode}
              disabled={sending}
              title={INVESTIGATE_TOOLTIP}
              aria-pressed={mode === MODE_INVESTIGATE}
              aria-label={
                mode === MODE_INVESTIGATE
                  ? 'Investigate რეჟიმი ჩართულია — დააჭირე გამოსართავად'
                  : 'Investigate რეჟიმის ჩართვა'
              }
              data-testid="chat-mode-toggle"
              data-mode={mode}
            >
              <span aria-hidden="true">🔍</span>
              <span className="chat-panel__btn-mode-label">Investigate</span>
            </button>
            <button
              type="button"
              className={`chat-panel__btn-think${think ? ' chat-panel__btn-think--active' : ''}`}
              onClick={toggleThink}
              disabled={sending}
              title={THINK_TOOLTIP}
              aria-pressed={think}
              aria-label={
                think
                  ? 'ღრმა ფიქრი ჩართულია — დააჭირე გამოსართავად'
                  : 'ღრმა ფიქრის ჩართვა'
              }
              data-testid="chat-think-toggle"
              data-think={think ? 'true' : 'false'}
            >
              <span aria-hidden="true">🧠</span>
              <span className="chat-panel__btn-think-label">ღრმა ფიქრი</span>
            </button>
            <textarea
              ref={textareaRef}
              className="chat-panel__input"
              placeholder="დამისვი კითხვა…"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              maxLength={8000}
              disabled={sending}
              data-testid="chat-input"
            />
            <button
              type="submit"
              className="chat-panel__btn-send"
              disabled={sending || !draft.trim()}
              data-testid="chat-send"
              aria-label="გაგზავნა"
            >
              {sending ? (
                <span className="chat-panel__spinner" aria-hidden="true" />
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="m22 2-7 20-4-9-9-4z" />
                  <path d="M22 2 11 13" />
                </svg>
              )}
            </button>
          </form>
        </div>
      )}
    </>
  );
}
