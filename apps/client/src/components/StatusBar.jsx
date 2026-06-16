// Top safe-area spacer. The faux iOS status bar (fake "9:41" + signal/battery)
// was prototype chrome and has been removed. On a real device (viewport-fit=cover)
// this reserves the OS status-bar / notch inset so content isn't drawn under it;
// on desktop / non-notch the inset is 0 and it renders nothing visible.
// Kept as a named export so existing call sites need no changes.
export function StatusBar() {
  return (
    <div
      aria-hidden="true"
      style={{ height: 'env(safe-area-inset-top, 0px)', flexShrink: 0 }}
    />
  );
}
