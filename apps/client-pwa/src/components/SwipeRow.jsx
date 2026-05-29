import { useEffect, useRef, useState } from 'react';
import { Icon } from './Icon.jsx';

// ─── Swipe-to-reveal row ─────────────────────────────────────────
export function SwipeRow({ children, onAction, actionLabel = 'Отменить', actionIcon = 'close', revealPx = 110, threshold = 60 }) {
  const [x, setX] = useState(0);
  const [dragging, setDragging] = useState(false);
  const startX = useRef(0);
  const startY = useRef(0);
  const lockedAxis = useRef(null);

  const onTouchStart = (e) => {
    const t = e.touches[0];
    startX.current = t.clientX; startY.current = t.clientY;
    lockedAxis.current = null; setDragging(true);
  };
  const onTouchMove = (e) => {
    const t = e.touches[0];
    const dx = t.clientX - startX.current;
    const dy = t.clientY - startY.current;
    if (lockedAxis.current === null && (Math.abs(dx) > 8 || Math.abs(dy) > 8)) {
      lockedAxis.current = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
    }
    if (lockedAxis.current === 'x') {
      let next = Math.min(0, dx);
      if (next < -revealPx) next = -revealPx + (next + revealPx) * 0.25;
      setX(next);
    }
  };
  const onTouchEnd = () => {
    setDragging(false);
    setX(x < -threshold ? -revealPx : 0);
  };

  const mouseDown = useRef(false);
  const onMouseDown = (e) => {
    mouseDown.current = true;
    startX.current = e.clientX; startY.current = e.clientY;
    lockedAxis.current = null; setDragging(true);
  };
  useEffect(() => {
    const onMove = (e) => {
      if (!mouseDown.current) return;
      const dx = e.clientX - startX.current;
      const dy = e.clientY - startY.current;
      if (lockedAxis.current === null && (Math.abs(dx) > 8 || Math.abs(dy) > 8)) {
        lockedAxis.current = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
      }
      if (lockedAxis.current === 'x') {
        let next = Math.min(0, dx);
        if (next < -revealPx) next = -revealPx + (next + revealPx) * 0.25;
        setX(next);
      }
    };
    const onUp = () => {
      if (!mouseDown.current) return;
      mouseDown.current = false; setDragging(false);
      setX(x < -threshold ? -revealPx : 0);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [x, revealPx, threshold]);

  const exposed = x <= -threshold;
  return (
    <div className="swipe-row">
      <div className="swipe-row-bg" onClick={() => exposed && onAction?.()}>
        <Icon name={actionIcon} size={18} color="#fff" />
        <span>{actionLabel}</span>
      </div>
      <div
        className={`swipe-row-fg ${dragging ? 'dragging' : ''}`}
        style={{ transform: `translateX(${x}px)` }}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        onMouseDown={onMouseDown}
      >
        {children}
      </div>
    </div>
  );
}
