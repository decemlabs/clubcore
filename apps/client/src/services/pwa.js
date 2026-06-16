// PWA service-worker registration + install prompt capture.
//
// Vite serves /sw.js straight out of public/, so this just registers it.
// We expose `triggerInstall()` so the Tweaks panel can offer an "Install" button.

let deferredInstall = null;

export function registerPwa() {
  if (typeof window === 'undefined') return;

  // DEV: never run the service worker. public/sw.js is cache-first for all
  // same-origin assets, which pins Vite dev modules and masks fresh code on
  // every reload (the recurring "stale SW blanks the screen" gotcha). Instead,
  // actively unregister any SW left over from a prior build/preview on this
  // origin and drop its caches, so dev always self-heals to the latest bundle.
  if (import.meta.env.DEV) {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistrations()
        .then((regs) => regs.forEach((r) => r.unregister()))
        .catch(() => {});
    }
    if (window.caches) {
      caches.keys().then((keys) => keys.forEach((k) => caches.delete(k))).catch(() => {});
    }
    return;
  }

  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    window.addEventListener('load', () => {
      // PWA-07 / T-69-07: /sw.js is network-only for /api/* (see public/sw.js).
      // Do NOT swap to the VitePWA-generated worker without porting the /api guard.
      navigator.serviceWorker.register('/sw.js')
        .then((reg) => console.info('[PWA] SW registered:', reg.scope))
        .catch((err) => console.warn('[PWA] SW failed:', err.message));
    });
  }

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstall = e;
    window.dispatchEvent(new CustomEvent('pwa:installable'));
  });
}

export async function triggerInstall() {
  if (!deferredInstall) return false;
  deferredInstall.prompt();
  const choice = await deferredInstall.userChoice;
  deferredInstall = null;
  return choice.outcome === 'accepted';
}

export function canInstall() {
  return !!deferredInstall;
}
