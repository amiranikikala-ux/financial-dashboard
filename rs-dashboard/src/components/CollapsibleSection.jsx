import { useState, useRef, useEffect } from 'react';

export default function CollapsibleSection({
  title,
  subtitle,
  defaultOpen = false,
  badge,
  children,
}) {
  const [open, setOpen] = useState(defaultOpen);
  const contentRef = useRef(null);
  const [height, setHeight] = useState(defaultOpen ? 'auto' : '0px');

  useEffect(() => {
    if (!contentRef.current) return;
    if (open) {
      setHeight(`${contentRef.current.scrollHeight}px`);
      const timer = setTimeout(() => setHeight('auto'), 300);
      return () => clearTimeout(timer);
    }
    setHeight(`${contentRef.current.scrollHeight}px`);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => setHeight('0px'));
    });
  }, [open]);

  return (
    <div className={`collapsible-section ${open ? 'collapsible-section--open' : ''}`}>
      <button
        type="button"
        className="collapsible-header"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="collapsible-arrow">{open ? '▲' : '▼'}</span>
        <span className="collapsible-title">{title}</span>
        {subtitle && <span className="collapsible-subtitle">{subtitle}</span>}
        {badge && <span className="collapsible-badge">{badge}</span>}
      </button>
      <div
        className="collapsible-body"
        style={{ height, overflow: height === 'auto' ? 'visible' : 'hidden' }}
        ref={contentRef}
      >
        {children}
      </div>
    </div>
  );
}
