export default function RefreshButton({ status, refreshing, onRefresh }) {
  const pipelineState = status?.pipeline?.state;
  const isRunning = pipelineState === 'running' || refreshing;
  const dataAgeSec = status?.data_age_seconds;

  let ageLabel = null;
  if (dataAgeSec != null) {
    if (dataAgeSec < 60) ageLabel = `${dataAgeSec} წმ`;
    else if (dataAgeSec < 3600) ageLabel = `${Math.floor(dataAgeSec / 60)} წთ`;
    else ageLabel = `${Math.floor(dataAgeSec / 3600)} სთ ${Math.floor((dataAgeSec % 3600) / 60)} წთ`;
  }

  const scheduleMin = status?.pipeline?.schedule_interval_min;

  return (
    <div className="refresh-status">
      <button
        type="button"
        className={`btn-refresh ${isRunning ? 'btn-refresh--running' : ''}`}
        onClick={onRefresh}
        disabled={isRunning}
        title={
          isRunning
            ? 'მონაცემები მზადდება...'
            : 'მონაცემების ხელახლა გენერაცია'
        }
      >
        <svg
          className={`refresh-icon ${isRunning ? 'refresh-icon--spin' : ''}`}
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
        </svg>
        {isRunning ? 'მიმდინარეობს...' : 'განახლება'}
      </button>
      {ageLabel && (
        <span className="refresh-age" title={`მონაცემები: ${ageLabel} წინ${scheduleMin ? ` · ავტო: ყოველ ${scheduleMin} წთ` : ''}`}>
          {ageLabel} წინ
        </span>
      )}
      {pipelineState === 'error' && (
        <span className="refresh-error-dot" title={status?.pipeline?.last_error || 'შეცდომა'}>!</span>
      )}
    </div>
  );
}
