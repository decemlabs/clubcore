// Avatar with initials.
export function Avatar({ initials, color = '#1c1917', bg = '#e7e5e4', size = 44, ring = false }) {
  return (
    <div className="avatar" style={{
      width: size, height: size, fontSize: size * 0.36,
      background: bg, color,
      boxShadow: ring ? `0 0 0 2px var(--bg), 0 0 0 3.5px ${color}` : 'none',
    }}>
      {initials}
    </div>
  );
}
