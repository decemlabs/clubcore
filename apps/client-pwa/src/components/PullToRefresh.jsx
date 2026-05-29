import { useRef, useState } from 'react';

// ─── Pull-to-refresh wrapper ────────────────────────────────────
// Wraps a scroller; when at scrollTop=0 and pulled down, shows
// a custom indicator. Releases trigger onRefresh().
export function PullToRefresh({ children, onRefresh, scrollPaddingTop = 54 }) {
  const ref = useRef(null);
  const [pull, setPull] = useState(0); // px
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef(null);
  const TRIGGER = 70;
  const MAX = 110;

  const onTouchStart = (e) => {
    if (refreshing) return;
    if (ref.current && ref.current.scrollTop <= 0) {
      startY.current = e.touches[0].clientY;
    } else {
      startY.current = null;
    }
  };
  const onTouchMove = (e) => {
    if (startY.current == null) return;
    const dy = e.touches[0].clientY - startY.current;
    if (dy <= 0) { setPull(0); return; }
    // rubber-band easing
    const eased = Math.min(MAX, dy * 0.55);
    setPull(eased);
  };
  const onTouchEnd = () => {
    if (startY.current == null) return;
    startY.current = null;
    if (pull >= TRIGGER) {
      setRefreshing(true);
      setPull(56); // hold position
      Promise.resolve(onRefresh && onRefresh()).then(() => {
        setTimeout(() => {
          setRefreshing(false);
          setPull(0);
        }, 700);
      });
    } else {
      setPull(0);
    }
  };

  // Mouse fallback so the prototype works without touch
  const onMouseDown = (e) => {
    if (refreshing) return;
    if (ref.current && ref.current.scrollTop <= 0) {
      startY.current = e.clientY;
      const move = (ev) => {
        const dy = ev.clientY - startY.current;
        if (dy <= 0) { setPull(0); return; }
        setPull(Math.min(MAX, dy * 0.55));
      };
      const up = () => {
        document.removeEventListener('mousemove', move);
        document.removeEventListener('mouseup', up);
        onTouchEnd();
      };
      document.addEventListener('mousemove', move);
      document.addEventListener('mouseup', up);
    }
  };

  const ratio = Math.min(1, pull / TRIGGER);
  const ready = pull >= TRIGGER;

  return (
    <div style={{ position: 'relative', flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Indicator */}
      <div
        className="ptr-indicator"
        style={{
          position: 'absolute', top: 8, left: '50%',
          transform: `translate(-50%, ${pull > 12 ? 0 : -40}px)`,
          opacity: pull > 4 ? 1 : 0,
          transition: refreshing ? 'transform 0.2s ease' : 'opacity 0.15s',
          zIndex: 5,
        }}
      >
        <div style={{
          width: 36, height: 36, borderRadius: 999,
          background: 'var(--surface)', border: '0.5px solid var(--border-strong)',
          boxShadow: '0 4px 14px rgba(0,0,0,0.08)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {refreshing ? (
            <div className="ptr-spin" />
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                 stroke={ready ? 'var(--accent-deep)' : 'var(--text-2)'}
                 strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"
                 style={{ transform: `rotate(${ratio * 360}deg)`, transition: 'stroke 0.15s' }}>
              <path d="M21 12a9 9 0 1 1-3-6.7" />
              <path d="M21 4v5h-5" />
            </svg>
          )}
        </div>
      </div>

      {/* Scrollable content with pull offset */}
      <div
        ref={ref}
        className="scroller"
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        onMouseDown={onMouseDown}
        style={{
          paddingTop: scrollPaddingTop,
          transform: `translateY(${pull}px)`,
          transition: pull === 0 || refreshing ? 'transform 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)' : 'none',
          flex: 1,
          minHeight: 0,
          WebkitOverflowScrolling: 'touch',
        }}
      >
        {children}
      </div>
    </div>
  );
}
