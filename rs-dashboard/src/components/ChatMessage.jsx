import { useCallback, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Matches a fenced code block declared with "text" / "txt" / "plain" / unlabeled
// whose first non-empty content line starts with `ფაილი:` and also contains
// `ხაზი:` + `გასწორება:` somewhere in the block.
// This matches the investigator prompt's Cascade-brief contract and is narrow
// enough to avoid false positives on ordinary chat-mode code fences.
const CASCADE_BLOCK_RE = /```(?:text|txt|plain)?\s*\n([\s\S]*?)```/g;

function extractCascadeBrief(markdown) {
  if (typeof markdown !== 'string' || !markdown) return null;
  CASCADE_BLOCK_RE.lastIndex = 0;
  let match;
  while ((match = CASCADE_BLOCK_RE.exec(markdown)) !== null) {
    const body = (match[1] || '').replace(/^\s*\n/, '').replace(/\s+$/, '');
    if (!body) continue;
    const firstLine = body.split('\n').find((line) => line.trim().length > 0) || '';
    if (
      firstLine.trim().startsWith('ფაილი:') &&
      body.includes('ხაზი:') &&
      body.includes('გასწორება:')
    ) {
      return body;
    }
  }
  return null;
}

async function copyToClipboard(text) {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      /* fall through to legacy path */
    }
  }
  if (typeof document === 'undefined') return false;
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'absolute';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

function CascadeBriefBlock({ brief }) {
  const [open, setOpen] = useState(true);
  const [copied, setCopied] = useState(false);

  const onCopy = useCallback(async () => {
    const ok = await copyToClipboard(brief);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    }
  }, [brief]);

  return (
    <div className="chat-msg__cascade" data-testid="chat-msg-cascade">
      <div className="chat-msg__cascade-header">
        <button
          type="button"
          className="chat-msg__cascade-toggle"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <span className="chat-msg__cascade-icon" aria-hidden="true">
            {open ? '▾' : '▸'}
          </span>
          📋 Cascade-ისთვის (copy-paste)
        </button>
        <button
          type="button"
          className={`chat-msg__cascade-copy${copied ? ' chat-msg__cascade-copy--ok' : ''}`}
          onClick={onCopy}
          data-testid="chat-msg-cascade-copy"
          aria-label="Cascade ბრიფის კოპირება"
        >
          {copied ? '✓ კოპირდა' : 'კოპირება'}
        </button>
      </div>
      {open && (
        <pre className="chat-msg__cascade-body" data-testid="chat-msg-cascade-body">
          {brief}
        </pre>
      )}
    </div>
  );
}

function SourceAttribution({ sources }) {
  const [open, setOpen] = useState(false);
  if (!Array.isArray(sources) || sources.length === 0) return null;

  return (
    <div className="chat-msg__sources">
      <button
        type="button"
        className="chat-msg__sources-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="chat-msg__sources-icon" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
        წყაროები ({sources.length})
      </button>
      {open && (
        <ol className="chat-msg__sources-list">
          {sources.map((entry, idx) => {
            const summary = entry?.result_summary || {};
            const ok = summary.ok !== false;
            const args = entry?.arguments || {};
            const section = summary.section || args.section || '—';
            const src = summary.source || (section !== '—' ? `data.json:${section}` : 'n/a');
            const rowCount = summary.row_count;
            const totalCount = summary.total_count;
            const truncated = summary.truncated === true;
            return (
              <li key={idx} className={`chat-msg__source ${ok ? '' : 'chat-msg__source--error'}`}>
                <code>{src}</code>
                {ok && rowCount != null && (
                  <span className="chat-msg__source-meta">
                    {' '}· {rowCount}
                    {totalCount != null && totalCount !== rowCount ? ` / ${totalCount}` : ''}
                    {truncated ? ' (ჩამოჭრილი)' : ''}
                  </span>
                )}
                {!ok && summary.error && (
                  <span className="chat-msg__source-meta"> · {summary.error}</span>
                )}
                {Object.keys(args).length > 0 && (
                  <div className="chat-msg__source-args">
                    {Object.entries(args)
                      .filter(([key]) => key !== 'section')
                      .map(([key, value]) => (
                        <span key={key} className="chat-msg__source-arg">
                          <strong>{key}:</strong>{' '}
                          {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        </span>
                      ))}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

function UsageBadge({ usage }) {
  if (!usage) return null;
  const input = usage.input_tokens;
  const output = usage.output_tokens;
  const cacheRead = usage.cache_read_input_tokens;
  const cacheWrite = usage.cache_creation_input_tokens;
  if (input == null && output == null) return null;
  const parts = [];
  if (input != null) parts.push(`${input}in`);
  if (output != null) parts.push(`${output}out`);
  const cacheParts = [];
  if (cacheRead != null && cacheRead > 0) cacheParts.push(`read ${cacheRead}`);
  if (cacheWrite != null && cacheWrite > 0) cacheParts.push(`write ${cacheWrite}`);
  const cacheTitle = cacheParts.length
    ? ` · cache: ${cacheParts.join(' + ')}`
    : '';
  return (
    <span
      className="chat-msg__usage"
      title={`model: ${usage.model || '—'} · stop: ${usage.stop_reason || '—'}${cacheTitle}`}
    >
      {parts.join(' / ')} tok
      {cacheRead != null && cacheRead > 0 && (
        <span className="chat-msg__usage-cache" title="cached prefix tokens re-used from Anthropic">
          {' '}· ⚡ {cacheRead} cached
        </span>
      )}
    </span>
  );
}

export default function ChatMessage({ entry }) {
  if (!entry) return null;
  const isUser = entry.role === 'user';
  const className = `chat-msg chat-msg--${isUser ? 'user' : 'assistant'}${entry.error ? ' chat-msg--error' : ''}`;

  // Cascade copy-paste block is gated on investigate mode (prevents false
  // positives on any chat-mode assistant response that happens to contain a
  // similarly-shaped code block) AND on the heuristic match below.
  const entryMode = entry?.usage?.mode || entry?.mode || null;
  const cascadeBrief =
    !isUser && !entry.pending && !entry.error && entryMode === 'investigate'
      ? extractCascadeBrief(entry.text || '')
      : null;

  return (
    <div
      className={className}
      data-testid={`chat-msg-${entry.role}`}
      data-mode={entryMode || undefined}
    >
      <div className="chat-msg__bubble">
        {isUser ? (
          <p className="chat-msg__text">{entry.text}</p>
        ) : entry.pending ? (
          <div className="chat-msg__typing" aria-live="polite">
            <span className="chat-msg__typing-dot" />
            <span className="chat-msg__typing-dot" />
            <span className="chat-msg__typing-dot" />
          </div>
        ) : entry.error ? (
          <div className="chat-msg__error-body" role="alert">
            <strong>⚠️ შეცდომა:</strong> {entry.error}
          </div>
        ) : (
          <div className="chat-msg__markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.text || ''}</ReactMarkdown>
          </div>
        )}
      </div>
      {cascadeBrief && <CascadeBriefBlock brief={cascadeBrief} />}
      {!isUser && !entry.pending && !entry.error && (
        <div className="chat-msg__meta">
          <SourceAttribution sources={entry.sources} />
          <UsageBadge usage={entry.usage} />
        </div>
      )}
    </div>
  );
}
