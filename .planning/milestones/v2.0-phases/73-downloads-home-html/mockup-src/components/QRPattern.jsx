// QR code SVG (decorative — a stable pseudo-random pattern).
export function QRPattern({ size = 240, color = '#000', bg = 'transparent', seed = 7 }) {
  const N = 25;
  const cell = size / N;
  // deterministic pseudo-random
  const rng = (i, j) => {
    const v = Math.sin((i * 73 + j * 131 + seed * 17)) * 10000;
    return v - Math.floor(v);
  };
  const cells = [];
  // finder patterns at 3 corners
  const isFinder = (i, j) => (
    (i < 7 && j < 7) || (i < 7 && j >= N - 7) || (i >= N - 7 && j < 7)
  );
  const drawFinder = (cx, cy) => {
    const x = cx * cell, y = cy * cell;
    return (
      <g key={`f${cx}-${cy}`}>
        <rect x={x} y={y} width={7 * cell} height={7 * cell} rx={cell * 0.7} fill={color} />
        <rect x={x + cell} y={y + cell} width={5 * cell} height={5 * cell} rx={cell * 0.5} fill={bg === 'transparent' ? '#fff' : bg} />
        <rect x={x + 2 * cell} y={y + 2 * cell} width={3 * cell} height={3 * cell} rx={cell * 0.3} fill={color} />
      </g>
    );
  };
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      if (isFinder(i, j)) continue;
      if (rng(i, j) > 0.55) {
        cells.push(<rect key={`${i}-${j}`} x={j * cell} y={i * cell} width={cell} height={cell} rx={cell * 0.25} fill={color} />);
      }
    }
  }
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block' }}>
      {bg !== 'transparent' && <rect width={size} height={size} fill={bg} rx={size * 0.04} />}
      {cells}
      {drawFinder(0, 0)}
      {drawFinder(0, N - 7)}
      {drawFinder(N - 7, 0)}
    </svg>
  );
}
