import React, { createContext, useContext, useEffect, useMemo } from 'react';
import { useTweaks } from '@/components/Tweaks/TweaksPanel.jsx';
import { deriveAccent } from '@/utils/accent.js';

// Default tweak values — single source of truth used by the host EDITMODE bridge.
export const TWEAK_DEFAULTS = {
  theme: 'light',
  accent: '#2dd4a4',
  subState: 'active',
  homeVariant: 'classic',
  userName: 'Саша',
  dataMode: 'normal',
  gymEvent: 'none',
  subCardStyle: 'split',
  pushKind: 'idle',
  paymentOutcome: 'ok',
};

const TweaksCtx = createContext(null);

export function TweaksProvider({ children }) {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // Apply theme + accent to <html>.
  useEffect(() => {
    const r = document.documentElement;
    r.setAttribute('data-theme', t.theme || 'light');
    const a = deriveAccent(t.accent);
    r.style.setProperty('--accent', t.accent);
    r.style.setProperty('--accent-deep', a.deep);
    // --accent-soft is theme-aware (mockup parity): light uses the hand-tuned
    // pale preset; dark uses an opaque surface-blended tint so accent fills
    // don't over-brighten. Inline so it tracks the active accent.
    r.style.setProperty(
      '--accent-soft',
      t.theme === 'dark'
        ? 'color-mix(in oklab, var(--accent) 22%, var(--surface))'
        : a.soft,
    );
  }, [t.theme, t.accent]);

  const value = useMemo(() => ({ t, setTweak }), [t, setTweak]);
  return <TweaksCtx.Provider value={value}>{children}</TweaksCtx.Provider>;
}

export function useTweaksCtx() {
  const v = useContext(TweaksCtx);
  if (!v) throw new Error('useTweaksCtx must be used inside <TweaksProvider>');
  return v;
}
