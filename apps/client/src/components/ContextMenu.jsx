import { useLayoutEffect, useRef, useState } from 'react';
import { Icon } from './Icon.jsx';
import { useLongPress } from '@/hooks/useLongPress.js';

// ─── Context menu (long-press popup) ─────────────────────────────
// Positioned at the press point and clamped within the device frame.
export function ContextMenu({ point, items, onClose }) {
  const ref = useRef(null);
  const [pos, setPos] = useState({ left: 0, top: 0, ready: false });

  useLayoutEffect(() => {
    if (!ref.current) return;
    const menu = ref.current;
    const frame = menu.closest('.screen') || menu.parentElement;
    const fb = frame.getBoundingClientRect();
    const mb = menu.getBoundingClientRect();
    let left = (point.x - fb.left) - mb.width / 2;
    let top  = (point.y - fb.top) + 8;
    left = Math.max(12, Math.min(fb.width - mb.width - 12, left));
    if (top + mb.height > fb.height - 12) {
      top = (point.y - fb.top) - mb.height - 8;
    }
    top = Math.max(12, top);
    setPos({ left, top, ready: true });
  }, [point.x, point.y]);

  return (
    <>
      <div className="ctx-backdrop" onClick={onClose} />
      <div
        ref={ref}
        className="ctx-menu"
        style={{
          left: pos.left, top: pos.top,
          visibility: pos.ready ? 'visible' : 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {items.map((it, i) => (
          <button
            key={i}
            className={`ctx-item ${it.danger ? 'danger' : ''}`}
            onClick={() => { onClose(); it.onClick?.(); }}
          >
            <span>{it.label}</span>
            {it.icon && (
              <span className="ctx-item-ico">
                <Icon name={it.icon} size={18}
                      color={it.danger ? 'var(--danger)' : 'var(--text-2)'} />
              </span>
            )}
          </button>
        ))}
      </div>
    </>
  );
}

// Convenience wrapper: any child becomes long-pressable, with the
// context menu auto-rendered into the device frame portal.
export function LongPressItem({ children, items, className = '', style, onClick }) {
  const [menu, setMenu] = useState(null);
  const { held, handlers } = useLongPress((point) => setMenu(point));
  return (
    <>
      <div
        className={`${className} ${held ? 'lp-holding' : ''}`.trim()}
        style={style}
        onClick={onClick}
        {...handlers}
      >
        {children}
      </div>
      {menu && <ContextMenu point={menu} items={items} onClose={() => setMenu(null)} />}
    </>
  );
}
