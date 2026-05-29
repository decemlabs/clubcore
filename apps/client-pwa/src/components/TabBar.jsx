import { Icon } from './Icon.jsx';

// Bottom navigation. App.jsx wires `active`/`onChange` to React Router.
export function TabBar({ active, onChange, unreadChat }) {
  const tabs = [
    { id: 'home',    label: 'Главная', icon: 'home' },
    { id: 'book',    label: 'Запись',  icon: 'calendar' },
    { id: 'chat',    label: 'Чат',     icon: 'chat', badge: unreadChat },
    { id: 'profile', label: 'Профиль', icon: 'user' },
  ];
  return (
    <div className="tabbar" role="tablist" aria-label="Основная навигация">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          aria-controls={`panel-${t.id}`}
          aria-label={t.badge ? `${t.label} · ${t.badge} непрочитанных` : t.label}
          className={`tabbar-item ${active === t.id ? 'active' : ''}`}
          onClick={() => onChange(t.id)}
        >
          <div style={{ position: 'relative' }}>
            <Icon name={t.icon} size={24} strokeWidth={active === t.id ? 2 : 1.7} />
            {t.badge ? (
              <span aria-hidden="true" style={{
                position: 'absolute', top: -3, right: -7,
                minWidth: 16, height: 16, padding: '0 4px',
                borderRadius: 999, background: 'var(--accent)',
                color: '#06120c', fontSize: 10, fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: '1.5px solid var(--surface)',
              }}>{t.badge}</span>
            ) : null}
          </div>
          <span>{t.label}</span>
        </button>
      ))}
    </div>
  );
}
