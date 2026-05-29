// Material-style ripple — appends a transient .ripple-dot at the pointer.
// Returns a click handler factory; spread onto an element with `onMouseDown={useRipple()}`.
export function useRipple() {
  return (e) => {
    const host = e.currentTarget;
    if (!host) return;
    const r = host.getBoundingClientRect();
    const dot = document.createElement('span');
    dot.className = 'ripple-dot';
    dot.style.left = (e.clientX - r.left) + 'px';
    dot.style.top  = (e.clientY - r.top)  + 'px';
    host.appendChild(dot);
    setTimeout(() => dot.remove(), 600);
  };
}
