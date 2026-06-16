/**
 * LoadError — data-load failure state (ported from the provided Error.html mockup).
 *
 * Two variants:
 *  - variant="screen" (default): full-screen state with StatusBar, optional back
 *    button, a stacked-cards illustration, title/subtitle, a "Повторить" CTA and
 *    an optional "Сообщить о проблеме" ghost button. Renders its own .page shell.
 *  - variant="inline": compact card for embedding inside a tab/list area (smaller
 *    illustration, title + retry button only).
 *
 * onRetry may return a promise (e.g. a react-query refetch); while it is pending
 * the button shows a spinner + "Подключаемся…".
 *
 * The device frame / dynamic island / home indicator are owned by the App shell.
 */
import React, { useState } from 'react';
import { StatusBar } from '@/components/StatusBar.jsx';

function ErrorIllustration({ compact = false }) {
  const scale = compact ? 0.72 : 1;
  return (
    <div
      className="le-illus"
      aria-hidden="true"
      style={{ transform: `scale(${scale})`, marginBottom: compact ? 10 : 32 }}
    >
      <div className="le-card back" />
      <div className="le-card mid" />
      <div className="le-card front">
        <div className="le-skeleton w2" />
        <div className="le-skeleton w1" />
        <div className="le-skeleton w3" />
      </div>
      <div className="le-badge">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M6 6l12 12" />
          <path d="M18 6L6 18" />
        </svg>
      </div>
    </div>
  );
}

function RetryButton({ onRetry, label = 'Повторить' }) {
  const [retrying, setRetrying] = useState(false);

  async function handleClick() {
    if (retrying || !onRetry) return;
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setRetrying(false);
    }
  }

  return (
    <button className="le-btn le-btn-accent" type="button" onClick={handleClick} disabled={retrying}>
      {retrying ? (
        <>
          <span className="le-spin" />
          <span>Подключаемся…</span>
        </>
      ) : (
        <>
          <svg className="le-retry-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 1 0 3-6.7" />
            <path d="M3 4v5h5" />
          </svg>
          <span>{label}</span>
        </>
      )}
    </button>
  );
}

const STYLE = `
  .le-illus { position: relative; width: 200px; height: 132px; transform-origin: center; }
  .le-card {
    position: absolute; left: 50%; width: 168px; height: 96px; border-radius: 18px;
    background: var(--surface); border: 0.5px solid var(--border); box-shadow: var(--sh-2);
    transform-origin: center;
  }
  .le-card.back { top: 4px; transform: translateX(-50%) rotate(-7deg) translateX(-14px); opacity: 0.55; }
  .le-card.mid { top: 12px; transform: translateX(-50%) rotate(4deg) translateX(8px); opacity: 0.8; }
  .le-card.front {
    top: 22px; transform: translateX(-50%); padding: 16px 18px;
    display: flex; flex-direction: column; gap: 10px; overflow: hidden;
  }
  .le-skeleton { height: 8px; border-radius: 999px; background: var(--border); }
  .le-skeleton.w1 { width: 60%; }
  .le-skeleton.w2 { width: 90%; }
  .le-skeleton.w3 { width: 45%; background: var(--border-strong); position: relative; }
  .le-skeleton.w3::after {
    content: ""; position: absolute; left: -6px; right: -6px; top: 50%; height: 1.5px;
    background: var(--danger); transform: rotate(-8deg); transform-origin: center;
  }
  .le-badge {
    position: absolute; right: 14px; bottom: 0; width: 38px; height: 38px; border-radius: 999px;
    background: var(--danger); color: #fff; border: 3px solid var(--bg);
    display: inline-flex; align-items: center; justify-content: center;
    box-shadow: 0 6px 16px rgba(220, 38, 38, 0.35);
  }
  .le-title {
    font-size: 22px; font-weight: 700; letter-spacing: -0.4px; line-height: 1.25;
    color: var(--text); max-width: 280px;
  }
  .le-subtitle {
    margin-top: 10px; font-size: 14.5px; line-height: 1.5; color: var(--text-2); max-width: 300px;
  }
  .le-btn {
    appearance: none; border: 0; background: var(--text); color: var(--bg);
    height: 52px; padding: 0 22px; border-radius: var(--r-pill);
    font-size: 16px; font-weight: 600; letter-spacing: -0.2px; cursor: pointer;
    display: inline-flex; align-items: center; justify-content: center; gap: 10px;
    font-family: inherit; width: 100%;
    transition: transform 0.12s ease, opacity 0.15s ease, background 0.15s;
  }
  .le-btn:active:not(:disabled) { transform: scale(0.98); }
  .le-btn:disabled { opacity: 0.6; cursor: not-allowed; }
  .le-btn-accent { background: var(--accent); color: #06120c; }
  .le-btn-ghost { background: transparent; color: var(--text-2); height: 44px; font-weight: 500; font-size: 14px; }
  .le-btn-ghost:active { background: var(--surface-2); }
  .le-retry-icon { transition: transform 0.4s cubic-bezier(0.32, 0.72, 0.2, 1); }
  .le-btn:active .le-retry-icon { transform: rotate(-180deg); }
  .le-spin {
    width: 18px; height: 18px; border-radius: 999px;
    border: 2px solid rgba(6, 18, 12, 0.25); border-top-color: #06120c;
    animation: le-spin 0.7s linear infinite;
  }
  @keyframes le-spin { to { transform: rotate(360deg); } }
`;

export function LoadError({
  title = 'Не удалось загрузить данные',
  subtitle = 'Проверьте подключение к интернету и попробуйте ещё раз.',
  onRetry,
  onBack,
  onReport,
  variant = 'screen',
}) {
  if (variant === 'inline') {
    return (
      <div style={{ padding: '12px 16px' }}>
        <div
          className="card fade-up"
          style={{
            padding: '24px 18px',
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            textAlign: 'center', gap: 6,
          }}
        >
          <ErrorIllustration compact />
          <div className="t-h3" style={{ fontSize: 15 }}>{title}</div>
          {subtitle && (
            <div className="t-small" style={{ color: 'var(--text-2)', maxWidth: 240, marginBottom: 6 }}>
              {subtitle}
            </div>
          )}
          {onRetry && (
            <div style={{ width: '100%', maxWidth: 220 }}>
              <RetryButton onRetry={onRetry} />
            </div>
          )}
          <style>{STYLE}</style>
        </div>
      </div>
    );
  }

  return (
    <div className="page" style={{ background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      <StatusBar />

      <div style={{ height: 44 }} />
      <div
        style={{
          height: 52, padding: '0 14px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0,
        }}
      >
        {onBack ? (
          <button
            type="button"
            aria-label="Назад"
            onClick={onBack}
            style={{
              width: 38, height: 38, borderRadius: 999,
              border: '0.5px solid var(--border)', background: 'var(--surface)',
              boxShadow: 'var(--sh-1)', display: 'inline-flex', alignItems: 'center',
              justifyContent: 'center', color: 'var(--text)', cursor: 'pointer', padding: 0,
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
          </button>
        ) : (
          <div style={{ width: 38 }} />
        )}
        <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: '-0.2px' }}>Ошибка</div>
        <div style={{ width: 38 }} />
      </div>

      <div
        style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          justifyContent: 'center', alignItems: 'center', padding: '0 32px', textAlign: 'center',
        }}
      >
        <ErrorIllustration />
        <div className="le-title">{title}</div>
        {subtitle && <div className="le-subtitle">{subtitle}</div>}
      </div>

      <div style={{ padding: '0 28px 28px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {onRetry && <RetryButton onRetry={onRetry} />}
        {onReport && (
          <button className="le-btn le-btn-ghost" type="button" onClick={onReport}>
            Сообщить о проблеме
          </button>
        )}
      </div>

      <style>{STYLE}</style>
    </div>
  );
}

export default LoadError;
