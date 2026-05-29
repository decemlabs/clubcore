import { useState, useEffect, useMemo } from 'react';

// Counts down from `targetMs` (relative offset in ms) and re-renders every second.
// Returns remaining ms; consumers format with formatCountdown().
export function useCountdown(targetMs) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const start = useMemo(() => Date.now(), []); // baseline at mount
  const elapsed = now - start;
  return Math.max(0, targetMs - elapsed);
}

export function formatCountdown(ms) {
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return {
    h, m, s,
    hh: String(h).padStart(2, '0'),
    mm: String(m).padStart(2, '0'),
    ss: String(s).padStart(2, '0'),
  };
}
