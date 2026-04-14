import { useState, useEffect } from 'react';

const TIME_FMT = new Intl.DateTimeFormat('ka-GE', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

const DATE_FMT = new Intl.DateTimeFormat('ka-GE', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
});

export default function LiveClock({ lastUpdated }) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const lastUpdatedLabel = lastUpdated
    ? `${DATE_FMT.format(new Date(lastUpdated))} ${TIME_FMT.format(new Date(lastUpdated))}`
    : null;

  return (
    <div className="live-clock">
      <div className="live-clock-time">
        <span className="live-clock-dot" />
        {TIME_FMT.format(now)}
      </div>
      <div className="live-clock-date">{DATE_FMT.format(now)}</div>
      {lastUpdatedLabel && (
        <div className="live-clock-updated" title="ბოლო მონაცემების განახლება">
          განახლდა: {lastUpdatedLabel}
        </div>
      )}
    </div>
  );
}
