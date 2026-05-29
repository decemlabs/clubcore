export function SearchBar({ value, onChange, placeholder = 'Поиск', autoFocus }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      background: 'var(--surface)', borderRadius: 'var(--r-pill)',
      border: '0.5px solid var(--border)',
      padding: '0 14px', height: 44,
    }}>
      <svg width="18" height="18" viewBox="0 0 24 24" style={{ flexShrink: 0 }}>
        <circle cx="11" cy="11" r="7" stroke="var(--text-3)" strokeWidth="1.8" fill="none" />
        <path d="M16 16l4 4" stroke="var(--text-3)" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
      <input
        autoFocus={autoFocus}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck={false}
        name="search"
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          flex: 1, border: 0, outline: 'none', background: 'transparent',
          appearance: 'none', WebkitAppearance: 'none',
          color: 'var(--text)', fontFamily: 'inherit', fontSize: 15,
          WebkitTapHighlightColor: 'transparent',
        }}
      />
      {value && (
        <button onClick={() => onChange('')} style={{
          width: 22, height: 22, borderRadius: 999, border: 0,
          background: 'var(--surface-2)', color: 'var(--text-2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', padding: 0, flexShrink: 0,
        }}>
          <svg width="10" height="10" viewBox="0 0 24 24">
            <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          </svg>
        </button>
      )}
    </div>
  );
}
