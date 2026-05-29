export function HomeIndicator() {
  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0, height: 22,
      display: 'flex', justifyContent: 'center', alignItems: 'flex-end',
      paddingBottom: 7, pointerEvents: 'none', zIndex: 50,
    }}>
      <div style={{ width: 134, height: 5, borderRadius: 999, background: 'var(--text)', opacity: 0.85 }} />
    </div>
  );
}
