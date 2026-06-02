// iOS-style status bar (lightweight, theme-aware).
export function StatusBar({ time = '9:41' }) {
  return (
    <div aria-hidden="true" style={{
      position: 'absolute', top: 0, left: 0, right: 0, zIndex: 30,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '14px 28px 10px', height: 44, color: 'var(--text)',
      fontSize: 15, fontWeight: 600, pointerEvents: 'none',
    }}>
      <span style={{ fontVariantNumeric: 'tabular-nums' }}>{time}</span>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <svg width="17" height="11" viewBox="0 0 17 11"><rect x="0" y="7" width="3" height="4" rx="0.5" fill="currentColor"/><rect x="4.5" y="5" width="3" height="6" rx="0.5" fill="currentColor"/><rect x="9" y="2.5" width="3" height="8.5" rx="0.5" fill="currentColor"/><rect x="13.5" y="0" width="3" height="11" rx="0.5" fill="currentColor"/></svg>
        <svg width="24" height="11" viewBox="0 0 24 11"><rect x="0.5" y="0.5" width="20" height="10" rx="3" stroke="currentColor" strokeOpacity="0.4" fill="none"/><rect x="2" y="2" width="17" height="7" rx="1.5" fill="currentColor"/><rect x="21" y="3.5" width="1.5" height="4" rx="0.5" fill="currentColor" fillOpacity="0.4"/></svg>
      </div>
    </div>
  );
}
