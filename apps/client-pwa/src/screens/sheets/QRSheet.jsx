import React from 'react';
import { Icon } from '@/components/Icon.jsx';
import { QRPattern } from '@/components/QRPattern.jsx';

export const QRSheet = ({ onClose, userName }) => {
  // 'idle' = QR shown, 'scanning' = animation, 'success' = entered
  const [phase, setPhase] = React.useState('idle');

  React.useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  // Auto-trigger scan after a few seconds while idle
  React.useEffect(() => {
    if (phase !== 'idle') return;
    const t = setTimeout(() => setPhase('scanning'), 4500);
    return () => clearTimeout(t);
  }, [phase]);

  React.useEffect(() => {
    if (phase !== 'scanning') return;
    const t = setTimeout(() => setPhase('success'), 1100);
    return () => clearTimeout(t);
  }, [phase]);

  // Auto-close after success
  React.useEffect(() => {
    if (phase !== 'success') return;
    const t = setTimeout(() => onClose && onClose(), 3200);
    return () => clearTimeout(t);
  }, [phase]);

  if (phase === 'success') {
    return <QRSuccess onClose={onClose} userName={userName} />;
  }

  return (
    <div className="sheet qr-sheet">
      {/* Status bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 28px 10px', height: 44, fontSize: 15, fontWeight: 600,
        color: 'var(--text)',
      }}>
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>9:41</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <svg width="17" height="11" viewBox="0 0 17 11"><rect x="0" y="7" width="3" height="4" rx="0.5" fill="currentColor"/><rect x="4.5" y="5" width="3" height="6" rx="0.5" fill="currentColor"/><rect x="9" y="2.5" width="3" height="8.5" rx="0.5" fill="currentColor"/><rect x="13.5" y="0" width="3" height="11" rx="0.5" fill="currentColor"/></svg>
          <svg width="24" height="11" viewBox="0 0 24 11"><rect x="0.5" y="0.5" width="20" height="10" rx="3" stroke="currentColor" strokeOpacity="0.4" fill="none"/><rect x="2" y="2" width="17" height="7" rx="1.5" fill="currentColor"/></svg>
        </div>
      </div>

      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px 0' }}>
        <button onClick={onClose} aria-label="Закрыть QR" style={{
          width: 36, height: 36, borderRadius: 999, border: 0,
          background: 'var(--surface-2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
        }}>
          <Icon name="close" size={20} color="var(--text)" strokeWidth={2.2} />
        </button>
        <div style={{ fontSize: 13, color: 'var(--text-3)', fontWeight: 600, letterSpacing: 0.4, textTransform: 'uppercase' }}>
          Яркость на максимум
        </div>
        <div style={{ width: 36 }} />
      </div>

      {/* QR content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0 24px' }}>
        <div className="t-mini" style={{ marginBottom: 20 }}>
          Пропуск в зал
        </div>
        <div style={{
          padding: 24, background: '#fff', borderRadius: 'var(--r-xl)',
          boxShadow: '0 30px 80px rgba(0,0,0,0.4), 0 4px 16px rgba(0,0,0,0.2)',
          position: 'relative', overflow: 'hidden',
        }}>
          <QRPattern size={260} color="#0a0a0a" />
          {phase === 'scanning' && (
            <>
              <div className="qr-scan-line" />
              <div className="qr-scan-veil" />
            </>
          )}
        </div>
        <div style={{ marginTop: 28, textAlign: 'center' }}>
          <div className="t-h1" style={{ fontSize: 28 }}>{userName || 'Саша'}</div>
          <div className="t-small" style={{ marginTop: 6, fontVariantNumeric: 'tabular-nums' }}>
            Клиент №&thinsp;4821 · до 7 мая
          </div>
        </div>
      </div>

      <div style={{ padding: '16px 24px 36px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
        {phase === 'scanning' ? (
          <>
            <div style={{
              width: 8, height: 8, borderRadius: 999, background: 'var(--warn)',
              animation: 'qr-pulse-fast 0.8s ease-in-out infinite',
            }} />
            <div className="t-small" style={{ color: 'var(--text-2)', fontWeight: 500 }}>
              Сканирование…
            </div>
          </>
        ) : (
          <>
            <div style={{
              width: 8, height: 8, borderRadius: 999, background: 'var(--accent)',
              boxShadow: '0 0 0 3px var(--accent-soft)', animation: 'qr-pulse 1.6s ease-in-out infinite',
            }} />
            <div className="t-small" style={{ color: 'var(--text-2)', fontWeight: 500 }}>
              Готов к сканированию
            </div>
          </>
        )}
      </div>

      <style>{`
        @keyframes qr-pulse {
          0%, 100% { box-shadow: 0 0 0 3px var(--accent-soft); }
          50% { box-shadow: 0 0 0 10px transparent; }
        }
        @keyframes qr-pulse-fast {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.4); opacity: 0.6; }
        }
        .qr-scan-line {
          position: absolute; left: 0; right: 0; height: 3px;
          background: linear-gradient(90deg, transparent, var(--accent), transparent);
          box-shadow: 0 0 18px 4px color-mix(in oklab, var(--accent) 70%, transparent);
          animation: qr-scan 1.1s cubic-bezier(0.4, 0, 0.6, 1) both;
          top: 0;
        }
        @keyframes qr-scan {
          0%   { top: 0%; opacity: 0; }
          10%  { opacity: 1; }
          90%  { opacity: 1; }
          100% { top: calc(100% - 3px); opacity: 0; }
        }
        .qr-scan-veil {
          position: absolute; inset: 0; pointer-events: none;
          background: color-mix(in oklab, var(--accent) 12%, transparent);
          animation: qr-veil 1.1s ease-out both;
        }
        @keyframes qr-veil {
          0% { opacity: 0; }
          50% { opacity: 1; }
          100% { opacity: 0; }
        }
      `}</style>
    </div>
  );
};

// ─── Success state — full-screen confirmation ─────────────────────
export function QRSuccess({ onClose, userName }) {
  return (
    <div className="sheet" style={{
      background: 'linear-gradient(180deg, var(--accent-soft) 0%, var(--bg) 60%)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 28px 10px', height: 44, fontSize: 15, fontWeight: 600,
        color: 'var(--text)',
      }}>
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>9:41</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <svg width="17" height="11" viewBox="0 0 17 11"><rect x="0" y="7" width="3" height="4" rx="0.5" fill="currentColor"/><rect x="4.5" y="5" width="3" height="6" rx="0.5" fill="currentColor"/><rect x="9" y="2.5" width="3" height="8.5" rx="0.5" fill="currentColor"/><rect x="13.5" y="0" width="3" height="11" rx="0.5" fill="currentColor"/></svg>
          <svg width="24" height="11" viewBox="0 0 24 11"><rect x="0.5" y="0.5" width="20" height="10" rx="3" stroke="currentColor" strokeOpacity="0.4" fill="none"/><rect x="2" y="2" width="17" height="7" rx="1.5" fill="currentColor"/></svg>
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0 28px', textAlign: 'center' }}>
        {/* Big check */}
        <div className="qr-check-burst">
          <div className="qr-check-ring" />
          <div className="qr-check-core">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none"
                 stroke="#06120c" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12.5l4.5 4.5L19 7" />
            </svg>
          </div>
        </div>

        <div className="t-mini scale-in" style={{ marginTop: 30, color: 'var(--accent-deep)', fontWeight: 700, letterSpacing: 1.2 }}>
          Вход зафиксирован
        </div>
        <div className="t-display fade-up" style={{ marginTop: 8, letterSpacing: -1, fontSize: 36 }}>
          Привет, {userName || 'Саша'}!
        </div>
        <div className="t-body fade-up" style={{ marginTop: 12, color: 'var(--text-2)', maxWidth: 320 }}>
          Хорошей тренировки. Зал работает до 23:00.
        </div>

        {/* Visit summary card */}
        <div className="card fade-up" style={{
          marginTop: 28, padding: 16, width: '100%', maxWidth: 360,
          display: 'flex', alignItems: 'center', gap: 14, animationDelay: '0.18s',
        }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: 'var(--surface-2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon name="qr" size={22} color="var(--text)" strokeWidth={1.6} />
          </div>
          <div style={{ flex: 1, textAlign: 'left' }}>
            <div className="t-mini" style={{ color: 'var(--text-3)' }}>Сегодня · 9:41</div>
            <div className="t-h3" style={{ marginTop: 2, fontSize: 15 }}>
              Турникет А · 14-й визит
            </div>
          </div>
        </div>
      </div>

      <div style={{ padding: '16px 24px 36px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button onClick={onClose} className="btn btn-accent" style={{ width: '100%', height: 54 }}>
          Готово
        </button>
        <div className="t-small" style={{ textAlign: 'center', color: 'var(--text-3)' }}>
          Закроется автоматически
        </div>
      </div>

      <style>{`
        .qr-check-burst {
          position: relative;
          width: 140px; height: 140px;
          display: flex; align-items: center; justify-content: center;
        }
        .qr-check-ring {
          position: absolute; inset: 0; border-radius: 999px;
          border: 2px solid var(--accent);
          animation: ring-burst 0.9s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .qr-check-ring::before, .qr-check-ring::after {
          content: ""; position: absolute; inset: -8px; border-radius: 999px;
          border: 2px solid var(--accent);
          opacity: 0;
          animation: ripple 1.4s ease-out infinite;
        }
        .qr-check-ring::after { animation-delay: 0.5s; }
        @keyframes ring-burst {
          0% { transform: scale(0.4); opacity: 0; }
          60% { transform: scale(1.05); opacity: 1; }
          100% { transform: scale(1); opacity: 1; }
        }
        @keyframes ripple {
          0% { transform: scale(0.9); opacity: 0.45; }
          100% { transform: scale(1.8); opacity: 0; }
        }
        .qr-check-core {
          width: 92px; height: 92px; border-radius: 999px;
          background: var(--accent);
          display: flex; align-items: center; justify-content: center;
          box-shadow: 0 16px 40px color-mix(in oklab, var(--accent) 50%, transparent);
          animation: core-pop 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both;
        }
        @keyframes core-pop {
          0% { transform: scale(0); opacity: 0; }
          70% { transform: scale(1.08); opacity: 1; }
          100% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

