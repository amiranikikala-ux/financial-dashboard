import { useEffect, useState } from 'react';
import useBankRefresh from '../hooks/useBankRefresh.js';

const OTP_RE = /^\d{9}$/;

const BANKS = [
  { key: 'bog', label: 'BOG' },
  { key: 'rsge', label: 'rs.ge ზედნადები' },
  { key: 'tbc', label: 'TBC' },
];

function BankRow({ label, status, isWorking }) {
  if (!status && isWorking) {
    return (
      <div className="bank-refresh-row bank-refresh-row--running">
        <span className="bank-refresh-row__label">{label}</span>
        <span className="bank-refresh-row__status">მიმდინარეობს...</span>
      </div>
    );
  }
  if (!status) {
    return (
      <div className="bank-refresh-row bank-refresh-row--pending">
        <span className="bank-refresh-row__label">{label}</span>
        <span className="bank-refresh-row__status">—</span>
      </div>
    );
  }
  if (status.ok) {
    const added = status.added_total || 0;
    const updated = status.updated_total || 0;
    const dur = status.duration_s != null ? `${status.duration_s} წმ` : '';
    const updatedTxt = updated > 0 ? ` · შესწორდა ${updated}` : '';
    return (
      <div className="bank-refresh-row bank-refresh-row--ok">
        <span className="bank-refresh-row__label">✅ {label}</span>
        <span className="bank-refresh-row__status">
          დაემატა {added}{updatedTxt} {dur && `· ${dur}`}
        </span>
      </div>
    );
  }
  const reason = status.skipped
    ? 'არ დაიწყო — წინა ეტაპი ვერ შესრულდა (კოდი არ დაიხარჯა)'
    : status.error || 'შეცდომა';
  return (
    <div className="bank-refresh-row bank-refresh-row--err">
      <span className="bank-refresh-row__label">❌ {label}</span>
      <span className="bank-refresh-row__status">{reason}</span>
    </div>
  );
}

export default function BankRefreshModal({ open, onClose, onDataReload }) {
  const [otp, setOtp] = useState('');
  const [otpError, setOtpError] = useState('');
  const { state, perBank, pipelineState, error, start, reset } = useBankRefresh({
    onComplete: () => onDataReload?.(),
  });

  useEffect(() => {
    if (!open) {
      reset();
      setOtp('');
      setOtpError('');
    }
  }, [open, reset]);

  if (!open) return null;

  const isIdle = state === 'idle';
  const isWorking = state === 'starting' || state === 'running';
  const isFinished = state === 'done' || state === 'error';

  const handleOtpChange = (e) => {
    const digits = e.target.value.replace(/\D/g, '').slice(0, 9);
    setOtp(digits);
    if (otpError) setOtpError('');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!OTP_RE.test(otp)) {
      setOtpError('კოდი უნდა იყოს ზუსტად 9 ციფრი');
      return;
    }
    setOtpError('');
    start(otp);
  };

  const closeIfAllowed = () => {
    if (isWorking) return;
    onClose?.();
  };

  let footerNote = null;
  if (state === 'running' && pipelineState === 'running') {
    footerNote = 'ბანკი დასრულდა — გადასათვლელად ცოტა დრო მჭირდება...';
  } else if (state === 'done') {
    footerNote = 'მონაცემი განახლდა. ფანჯრის დახურვა შეგიძლია.';
  } else if (state === 'error') {
    const tbcOnly =
      perBank.bog?.ok && perBank.rsge?.ok && perBank.tbc && !perBank.tbc.ok;
    if (tbcOnly) {
      footerNote =
        'BOG და რს.გე უკვე განახლდა. TBC-ისთვის ახალი კოდით გაიმეორე.';
    }
  }

  return (
    <div className="bank-refresh-overlay" onClick={closeIfAllowed}>
      <div
        className="bank-refresh-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="bank-refresh-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="bank-refresh-header">
          <h2 id="bank-refresh-title" className="bank-refresh-title">
            ბანკიდან ახალი მონაცემის ჩამოტანა
          </h2>
          <button
            type="button"
            className="bank-refresh-close"
            onClick={closeIfAllowed}
            disabled={isWorking}
            aria-label="დახურვა"
          >
            ×
          </button>
        </div>

        {isIdle && (
          <form className="bank-refresh-form" onSubmit={handleSubmit}>
            <p className="bank-refresh-help">
              შეიყვანე DigiPass-ის 9-ციფრიანი კოდი (PIN: 0777). კოდი მხოლოდ TBC-ს სჭირდება.
            </p>
            <label className="bank-refresh-label" htmlFor="bank-refresh-otp">
              DigiPass კოდი
            </label>
            <input
              id="bank-refresh-otp"
              className="bank-refresh-input"
              type="text"
              inputMode="numeric"
              autoComplete="off"
              value={otp}
              onChange={handleOtpChange}
              maxLength={9}
              placeholder="123456789"
              autoFocus
            />
            {otpError && <div className="bank-refresh-error">{otpError}</div>}
            <div className="bank-refresh-actions">
              <button type="button" className="bank-refresh-btn-secondary" onClick={onClose}>
                გაუქმება
              </button>
              <button
                type="submit"
                className="bank-refresh-btn-primary"
                disabled={otp.length !== 9}
              >
                ჩამოტანის დაწყება
              </button>
            </div>
          </form>
        )}

        {(isWorking || isFinished) && (
          <div className="bank-refresh-progress">
            <div className="bank-refresh-rows">
              {BANKS.map((b) => (
                <BankRow
                  key={b.key}
                  label={b.label}
                  status={perBank[b.key]}
                  isWorking={isWorking}
                />
              ))}
            </div>
            {error && <div className="bank-refresh-error">{error}</div>}
            {footerNote && <div className="bank-refresh-note">{footerNote}</div>}
            <div className="bank-refresh-actions">
              <button
                type="button"
                className="bank-refresh-btn-primary"
                onClick={onClose}
                disabled={isWorking}
              >
                {isWorking ? 'მიმდინარეობს...' : 'დახურვა'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
