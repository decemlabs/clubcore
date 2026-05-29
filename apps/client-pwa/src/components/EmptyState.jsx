// Reusable empty-state placeholder.

export function EmptyState({
  illustration = 'sparkle',
  title,
  body,
  cta,
  onCta,
  compact = false,
}) {
  return (
    <div
      className="fade-up"
      style={{
        padding: compact ? '28px 22px' : '40px 24px',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        textAlign: 'center', gap: compact ? 10 : 14,
      }}
    >
      <EmptyIllustration kind={illustration} />
      <div style={{ marginTop: 4 }}>
        <div className="t-h3" style={{ fontSize: compact ? 15 : 16 }}>{title}</div>
        {body && (
          <div
            className="t-small"
            style={{ marginTop: 6, color: 'var(--text-2)', maxWidth: 260, textWrap: 'pretty' }}
          >
            {body}
          </div>
        )}
      </div>
      {cta && (
        <button
          onClick={onCta}
          className="btn btn-accent btn-sm"
          style={{ marginTop: 4 }}
        >
          {cta}
        </button>
      )}
    </div>
  );
}

// ─── Tiny illustrative glyph (single-color line art on a soft circle) ───
export function EmptyIllustration({ kind }) {
  const size = 88;
  return (
    <div style={{
      width: size, height: size, borderRadius: 999,
      background: 'var(--surface-2)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', inset: 0, borderRadius: 999,
        background: 'radial-gradient(circle at 30% 25%, var(--accent-soft), transparent 60%)',
        opacity: 0.7,
      }} />
      <svg width={44} height={44} viewBox="0 0 24 24" fill="none"
           stroke="var(--text-2)" strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round"
           style={{ position: 'relative' }}>
        {kind === 'calendar' && (
          <>
            <rect x="3" y="5" width="18" height="16" rx="2.5" />
            <path d="M3 10h18M8 3v4M16 3v4" />
            <circle cx="12" cy="15.5" r="0.6" fill="var(--text-2)" stroke="none" />
          </>
        )}
        {kind === 'chat' && (
          <>
            <path d="M4 6c0-1.1.9-2 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H9l-4 4v-4H6a2 2 0 0 1-2-2V6Z" />
            <circle cx="9" cy="10" r="0.6" fill="var(--text-2)" stroke="none" />
            <circle cx="12" cy="10" r="0.6" fill="var(--text-2)" stroke="none" />
            <circle cx="15" cy="10" r="0.6" fill="var(--text-2)" stroke="none" />
          </>
        )}
        {kind === 'visits' && (
          <path d="M5 12h4l2-7 3 14 2-7h3" />
        )}
        {kind === 'card' && (
          <>
            <rect x="3" y="6" width="18" height="13" rx="2.5" />
            <path d="M3 10h18M7 15h4" />
          </>
        )}
        {kind === 'dumbbell' && (
          <path d="M6 9v6M9 7v10M15 7v10M18 9v6M9 12h6" />
        )}
        {kind === 'sparkle' && (
          <path d="M12 4v4M12 16v4M4 12h4M16 12h4M6.3 6.3l2.5 2.5M15.2 15.2l2.5 2.5M6.3 17.7l2.5-2.5M15.2 8.8l2.5-2.5" />
        )}
      </svg>
    </div>
  );
}
