import { Icon } from './Icon.jsx';

// Filter chips (single-select with all option).
export function FilterChips({ value, onChange, options }) {
  return (
    <div style={{
      display: 'flex', gap: 8, overflowX: 'auto', scrollbarWidth: 'none',
      padding: '2px 0 2px',
    }}>
      {options.map((o) => {
        const active = value === o.id;
        return (
          <button
            key={o.id}
            onClick={() => onChange(o.id)}
            className="press"
            style={{
              flexShrink: 0,
              padding: '7px 13px',
              fontSize: 13, fontWeight: 500,
              border: `0.5px solid ${active ? 'var(--text)' : 'var(--border-strong)'}`,
              background: active ? 'var(--text)' : 'transparent',
              color: active ? 'var(--bg)' : 'var(--text-2)',
              borderRadius: 999, cursor: 'pointer', fontFamily: 'inherit',
              display: 'flex', alignItems: 'center', gap: 6,
              transition: 'background 0.15s, color 0.15s',
            }}
          >
            {o.icon && <Icon name={o.icon} size={14} color="currentColor" strokeWidth={1.8} />}
            {o.label}
            {typeof o.count === 'number' && (
              <span style={{
                fontSize: 11, fontWeight: 600,
                background: active ? 'rgba(255,255,255,0.18)' : 'var(--surface-2)',
                color: active ? 'var(--bg)' : 'var(--text-3)',
                padding: '0 6px', height: 16,
                borderRadius: 999, lineHeight: '16px',
              }}>{o.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
