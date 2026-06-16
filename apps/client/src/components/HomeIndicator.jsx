// The faux iOS home-indicator pill was prototype chrome and has been removed.
// On a real device the OS draws its own home indicator; bottom safe-area spacing
// is handled by the TabBar / page padding. Kept as a named export (returns null)
// so the single call site in App.jsx needs no change.
export function HomeIndicator() {
  return null;
}
