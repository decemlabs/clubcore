import { useRef, useState } from 'react';

// ─── Long-press detection ──────────────────────────────────────────
// Returns event handlers + state.held flag. Triggers `onLongPress(point)`
// at `delay`ms unless cancelled by movement >cancelPx or pointerup/leave.
export function useLongPress(onLongPress, { delay = 380, cancelPx = 8 } = {}) {
  const timer = useRef(null);
  const start = useRef({ x: 0, y: 0 });
  const fired = useRef(false);
  const [held, setHeld] = useState(false);

  const clear = () => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    setHeld(false);
  };

  const begin = (e) => {
    const pt = e.touches ? e.touches[0] : e;
    start.current = { x: pt.clientX, y: pt.clientY };
    fired.current = false;
    setHeld(true);
    timer.current = setTimeout(() => {
      fired.current = true;
      setHeld(false);
      if (navigator.vibrate) try { navigator.vibrate(8); } catch (_) {}
      onLongPress({ x: start.current.x, y: start.current.y });
    }, delay);
  };

  const move = (e) => {
    if (!timer.current) return;
    const pt = e.touches ? e.touches[0] : e;
    const dx = pt.clientX - start.current.x;
    const dy = pt.clientY - start.current.y;
    if (Math.sqrt(dx * dx + dy * dy) > cancelPx) clear();
  };

  const cancel = () => clear();

  const onClickCapture = (e) => {
    // Suppress click if long-press fired (otherwise tap-after-hold opens the row)
    if (fired.current) {
      e.stopPropagation();
      e.preventDefault();
      fired.current = false;
    }
  };

  return {
    held,
    handlers: {
      onTouchStart: begin, onTouchMove: move, onTouchEnd: cancel, onTouchCancel: cancel,
      onMouseDown: begin, onMouseMove: move, onMouseUp: cancel, onMouseLeave: cancel,
      onContextMenu: (e) => { e.preventDefault(); },
      onClickCapture,
    },
  };
}
