import { useState, useEffect } from 'react';

const TIME_FMT = new Intl.DateTimeFormat('ka-GE', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

// ka-GE Intl.DateTimeFormat ფოლბექს ხშირად აბრუნებს ინგლისურ თვის სახელს ("Apr"),
// ამიტომ ქართული მოკლე თვეები ხელით ვადგინოთ.
const MONTH_SHORT_KA = [
  'იან', 'თებ', 'მარ', 'აპრ', 'მაი', 'ივნ',
  'ივლ', 'აგვ', 'სექ', 'ოქტ', 'ნოე', 'დეკ',
];

function formatDateKa(d) {
  return `${d.getDate()} ${MONTH_SHORT_KA[d.getMonth()]}, ${d.getFullYear()}`;
}

function formatStampKa(d) {
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${formatDateKa(d)} ${hh}:${mm}`;
}

export default function LiveClock({ lastUpdated }) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const tick = () => setNow(new Date());
    let intervalId = null;
    const msUntilNextMinute = 60_000 - (Date.now() % 60_000);
    const timeoutId = setTimeout(() => {
      tick();
      intervalId = setInterval(tick, 60_000);
    }, msUntilNextMinute);
    return () => {
      clearTimeout(timeoutId);
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  const tooltip = lastUpdated
    ? `ბოლო მონაცემების განახლება: ${formatStampKa(new Date(lastUpdated))}`
    : undefined;

  return (
    <div className="live-clock" title={tooltip}>
      <span className="live-clock-dot" aria-hidden="true" />
      <span className="live-clock-time">{TIME_FMT.format(now)}</span>
      <span className="live-clock-divider" aria-hidden="true">·</span>
      <span className="live-clock-date">{formatDateKa(now)}</span>
    </div>
  );
}
