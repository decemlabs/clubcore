import { useEffect, useRef, useState } from 'react';
import { SheetSkeleton } from './skeletons.jsx';

// SheetGate — briefly shows a sheet skeleton when a sub-sheet mounts,
// then swaps to real content. `keyFor` returns a stable identifier so
// reopening the SAME sheet skips the loader.
export function SheetGate({ open, variant = 'list', delay = 380, keyFor, children }) {
  const [stage, setStage] = useState('closed');
  const lastKey = useRef(null);

  useEffect(() => {
    if (!open) {
      setStage('closed');
      lastKey.current = null;
      return;
    }
    const k = keyFor ?? 'open';
    if (lastKey.current === k && stage === 'ready') return;
    lastKey.current = k;
    setStage('loading');
    const id = setTimeout(() => setStage('ready'), delay);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, keyFor]);

  if (stage === 'closed') return null;
  if (stage === 'loading') return <SheetSkeleton variant={variant} />;
  return children;
}
