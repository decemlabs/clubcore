// PWA service-worker registration + install prompt capture.
//
// Vite serves /sw.js straight out of public/, so this just registers it.
// We expose `triggerInstall()` so the Tweaks panel can offer an "Install" button.

let deferredInstall = null;

export function registerPwa() {
  if (typeof window === 'undefined') return;
  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    window.addEventListener('load', () => {
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
