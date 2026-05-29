import React from 'react';
import { LongPressItem } from '@/components/ContextMenu.jsx';
import { EmptyState } from '@/components/EmptyState.jsx';
import { Icon } from '@/components/Icon.jsx';
import { PullToRefresh } from '@/components/PullToRefresh.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { SwipeRow } from '@/components/SwipeRow.jsx';
import { NOTIFICATIONS } from '@/data';

export const NotificationsSheet = ({ onClose, onOpenChat }) => {
  const [filter, setFilter] = React.useState('all'); // 'all' | 'unread'
  const [items, setItems] = React.useState(() =>
    NOTIFICATIONS.map(n => ({ ...n }))
  );

  const filtered = filter === 'unread' ? items.filter(n => n.unread) : items;
  const unreadCount = items.filter(n => n.unread).length;

  const markAllRead = () => setItems(items.map(n => ({ ...n, unread: false })));
  const markOneRead = (id) =>
    setItems(items.map(n => n.id === id ? { ...n, unread: false } : n));

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 200,
      background: 'var(--bg)', display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />

      {/* Header */}
      <div style={{
        padding: '50px 12px 8px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <button onClick={onClose} style={{
          width: 36, height: 36, borderRadius: 999, border: 0,
          background: 'var(--surface)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name="chevronLeft" size={22} color="var(--text)" strokeWidth={2.2} />
        </button>
        <span className="t-h3" style={{ fontSize: 15 }}>Уведомления</span>
        <button
          onClick={markAllRead}
          disabled={unreadCount === 0}
          style={{
            border: 0, background: 'transparent',
            color: unreadCount === 0 ? 'var(--text-3)' : 'var(--text)',
            fontSize: 13, fontWeight: 600, fontFamily: 'inherit',
            cursor: unreadCount === 0 ? 'default' : 'pointer',
            padding: '6px 10px',
          }}
        >
          Прочитать
        </button>
      </div>

      {/* Filter pills */}
      <div style={{ padding: '6px 16px 12px' }}>
        <div className="seg" style={{ width: '100%' }}>
          <button
            className={`seg-item ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
            style={{ flex: 1 }}
          >Все · {items.length}</button>
          <button
            className={`seg-item ${filter === 'unread' ? 'active' : ''}`}
            onClick={() => setFilter('unread')}
            style={{ flex: 1 }}
          >Новые{unreadCount > 0 ? ` · ${unreadCount}` : ''}</button>
        </div>
      </div>

      <PullToRefresh
        scrollPaddingTop={0}
        onRefresh={() => new Promise(r => setTimeout(r, 700))}
      >
        {filtered.length === 0 ? (
          <div style={{ padding: '4px 16px' }}>
            <div className="card" style={{ padding: 0 }}>
              <EmptyState
                illustration="sparkle"
                title="Всё прочитано"
                body="Когда появятся новые уведомления — увидишь их тут."
              />
            </div>
          </div>
        ) : (
          <div className="stack-2 stagger" style={{ padding: '4px 16px 24px' }}>
            {filtered.map(n => (
              <SwipeRow
                key={n.id}
                actionLabel="Удалить"
                actionIcon="trash"
                revealPx={100}
                onAction={() => setItems(its => its.filter(x => x.id !== n.id))}
              >
                <LongPressItem
                  className="press card"
                  style={{
                    cursor: 'pointer', textAlign: 'left',
                    display: 'block', width: '100%',
                    border: n.unread ? '0.5px solid var(--border-strong)' : '0.5px solid var(--border)',
                    background: n.unread ? 'var(--surface)' : 'var(--surface-2)',
                    color: 'var(--text)',
                    overflow: 'hidden',
                  }}
                  onClick={() => {
                    markOneRead(n.id);
                    if (n.kind === 'message' && onOpenChat) onOpenChat();
                  }}
                  items={[
                    { label: n.unread ? 'Отметить прочитанным' : 'Отметить непрочитанным',
                      icon: 'check',
                      onClick: () => setItems(its => its.map(x => x.id === n.id ? { ...x, unread: !x.unread } : x)) },
                    { label: 'Удалить', icon: 'trash', danger: true,
                      onClick: () => setItems(its => its.filter(x => x.id !== n.id)) },
                  ]}
                >
                  <NotifRowInner n={n} />
                </LongPressItem>
              </SwipeRow>
            ))}

            {/* Settings shortcut */}
            <div className="t-mini" style={{
              color: 'var(--text-3)', textAlign: 'center', padding: '14px 0 0',
            }}>
              Управлять уведомлениями можно в Профиле
            </div>
          </div>
        )}
      </PullToRefresh>
    </div>
  );
};

function NotifRowInner({ n }) {
  const palette = {
    promo:    { bg: 'var(--accent-soft)', fg: 'var(--accent-deep)', icon: 'tag' },
    schedule: { bg: 'var(--warn-soft)',   fg: '#a36a16',            icon: 'clock' },
    message:  { bg: '#fef3c7',            fg: '#a36a16',            icon: 'chat' },
    info:     { bg: 'var(--surface-2)',   fg: 'var(--text-2)',      icon: 'info' },
  }[n.kind] || { bg: 'var(--surface-2)', fg: 'var(--text-2)', icon: 'info' };

  return (
    <div
      style={{
        padding: '14px 16px', display: 'flex', gap: 12,
      }}
    >
      <div style={{
        width: 38, height: 38, borderRadius: 10,
        background: palette.bg,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon name={palette.icon} size={20} color={palette.fg} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="row-between" style={{ alignItems: 'flex-start', gap: 6 }}>
          <div className="t-h3" style={{ fontSize: 15 }}>{n.title}</div>
          {n.unread && <span className="dot" style={{ marginTop: 7, flexShrink: 0 }} />}
        </div>
        <div className="t-small" style={{ marginTop: 2, color: 'var(--text-2)' }}>{n.body}</div>
        <div className="t-mini" style={{
          marginTop: 6, fontWeight: 500, letterSpacing: 0.2,
          color: 'var(--text-3)', textTransform: 'none',
        }}>{n.time}</div>
      </div>
    </div>
  );
}

