import { Icon } from './Icon.jsx';

// ─── Shared list-row primitives (used by booking review, plans, manage) ───
export function RowItem({ icon, avatar, label, value, sub, accent }) {
  return (
    <div style={{ padding: '14px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
      {avatar ? avatar : (
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: accent ? 'var(--accent-soft)' : 'var(--surface-2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name={icon} size={20} color={accent ? 'var(--accent-deep)' : 'var(--text-2)'} />
        </div>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-mini" style={{ color: 'var(--text-3)', fontWeight: 600 }}>{label}</div>
        <div className="t-h3" style={{ marginTop: 2, fontSize: 16 }}>{value}</div>
        {sub && <div className="t-small" style={{ marginTop: 1 }}>{sub}</div>}
      </div>
    </div>
  );
}

export function Divider() {
  return <div style={{ height: 0.5, background: 'var(--border)', margin: '0 14px' }} />;
}
