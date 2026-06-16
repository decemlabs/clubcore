import { useEffect, useState } from 'react';
import { Icon } from './Icon.jsx';

// Demo push notification overlay — triggered via Tweaks.
export const PUSH_PRESETS = {
  message: {
    app: 'Мой зал',
    title: 'Аня Соколова',
    body: 'Привет! Не забудь взять ремни для тяги — пригодятся сегодня.',
    icon: 'chat',
    bg: '#fef3c7', fg: '#a36a16',
    time: 'сейчас',
  },
  promo: {
    app: 'Мой зал',
    title: '−15% на годовой абонемент',
    body: 'Только до 5 мая. Оформи продление и получи бонусный месяц.',
    icon: 'tag',
    bg: 'var(--accent-soft)', fg: 'var(--accent-deep)',
    time: 'сейчас',
  },
  schedule: {
    app: 'Мой зал',
    title: 'Расписание изменилось',
    body: 'Йога в четверг перенесли на 19:30. Посмотри в расписании и перезапишись, если нужно.',
    icon: 'clock',
    bg: 'var(--warn-soft)', fg: '#a36a16',
    time: 'сейчас',
  },
  cancel: {
    app: 'Мой зал',
    title: 'Тренировка отменена',
    body: 'Аня приболела и не сможет провести тренировку. Вернули 2 200 ₽ на карту.',
    icon: 'alert',
    bg: 'var(--danger-soft)', fg: 'var(--danger)',
    time: 'сейчас',
  },
};

export function PushToast({ kind, onDismiss, onTap }) {
  const [exiting, setExiting] = useState(false);
  const preset = PUSH_PRESETS[kind];

  useEffect(() => {
    if (!preset) return;
    // Auto-dismiss after 6.5s
    const id = setTimeout(() => {
      setExiting(true);
      setTimeout(() => onDismiss && onDismiss(), 280);
    }, 6500);
    return () => clearTimeout(id);
  }, [kind, preset, onDismiss]);

  if (!preset) return null;

  const handleTap = () => {
    setExiting(true);
    setTimeout(() => {
      onTap && onTap();
      onDismiss && onDismiss();
    }, 200);
  };

  return (
    <div style={{
      position: 'absolute', top: 0, left: 0, right: 0,
      zIndex: 1000, padding: '52px 10px 0',
      pointerEvents: 'none',
      animation: exiting
        ? 'push-out 0.28s cubic-bezier(0.4, 0, 1, 1) forwards'
        : 'push-in 0.4s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <button
        onClick={handleTap}
        style={{
          width: '100%', appearance: 'none', border: 0,
          background: 'color-mix(in oklab, var(--surface) 90%, transparent)',
          backdropFilter: 'blur(30px) saturate(180%)',
          WebkitBackdropFilter: 'blur(30px) saturate(180%)',
          borderRadius: 22, padding: 12,
          boxShadow: '0 12px 36px rgba(0,0,0,0.22), 0 1px 0 color-mix(in oklab, var(--text) 8%, transparent) inset',
          border: '0.5px solid color-mix(in oklab, var(--border-strong) 60%, transparent)',
          display: 'flex', gap: 12, alignItems: 'flex-start',
          cursor: 'pointer', pointerEvents: 'auto',
          fontFamily: 'inherit', textAlign: 'left',
          color: 'var(--text)',
        }}
      >
        <div style={{
          width: 38, height: 38, borderRadius: 9,
          background: preset.bg, color: preset.fg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          <Icon name={preset.icon} size={20} color="currentColor" strokeWidth={1.8} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="row-between" style={{ gap: 8 }}>
            <div className="t-mini" style={{
              fontSize: 10, color: 'var(--text-3)',
              textTransform: 'uppercase', letterSpacing: 0.4,
            }}>{preset.app}</div>
            <div className="t-mini" style={{
              fontSize: 10, color: 'var(--text-3)',
              textTransform: 'none', letterSpacing: 0,
            }}>{preset.time}</div>
          </div>
          <div className="t-h3" style={{ fontSize: 14.5, marginTop: 2 }}>
            {preset.title}
          </div>
          <div className="t-small" style={{
            marginTop: 2, color: 'var(--text-2)', lineHeight: 1.4,
          }}>
            {preset.body}
          </div>
        </div>
      </button>

      <style>{`
        @keyframes push-in {
          0%   { transform: translateY(-120%); opacity: 0; }
          60%  { transform: translateY(4px); opacity: 1; }
          100% { transform: translateY(0); opacity: 1; }
        }
        @keyframes push-out {
          from { transform: translateY(0); opacity: 1; }
          to   { transform: translateY(-120%); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
