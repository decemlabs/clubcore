import React from 'react';
import { Avatar } from '@/components/Avatar.jsx';
import { Icon } from '@/components/Icon.jsx';
import { Divider } from '@/components/RowItem.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';

export const ReferralSheet = ({ onClose, userName }) => {
  const code = 'SASHA-FIT';
  const [copied, setCopied] = React.useState(false);
  const [shared, setShared] = React.useState(0); // demo "sent" count

  const onCopy = () => {
    if (navigator.clipboard) navigator.clipboard.writeText(code).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 200,
      background: 'var(--bg)', display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />

      {/* Header */}
      <div style={{
        position: 'relative', paddingTop: 50, paddingBottom: 8,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '50px 12px 8px',
      }}>
        <button onClick={onClose} style={{
          width: 36, height: 36, borderRadius: 999, border: 0,
          background: 'var(--surface)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name="chevronLeft" size={22} color="var(--text)" strokeWidth={2.2} />
        </button>
        <span className="t-h3" style={{ fontSize: 15 }}>Приведи друга</span>
        <div style={{ width: 36 }} />
      </div>

      <div className="scroller" style={{ paddingTop: 0 }}>
        {/* Hero */}
        <div style={{
          margin: '8px 16px 16px', padding: '24px 20px',
          borderRadius: 'var(--r-xl)',
          background: 'linear-gradient(135deg, var(--accent-soft), color-mix(in oklab, var(--accent-soft) 60%, var(--surface)))',
          border: '0.5px solid var(--border)',
          position: 'relative', overflow: 'hidden',
        }}>
          {/* Decorative glyph */}
          <div style={{
            position: 'absolute', right: -30, top: -30,
            width: 180, height: 180, borderRadius: 999,
            background: 'color-mix(in oklab, var(--accent) 18%, transparent)',
            filter: 'blur(8px)',
          }} />
          <div style={{ position: 'relative' }}>
            <div className="t-mini" style={{ color: 'var(--accent-deep)', fontWeight: 600 }}>
              ДВОЙНОЙ БОНУС
            </div>
            <div className="t-display" style={{ marginTop: 6, fontSize: 36, lineHeight: 1.05, letterSpacing: -0.6 }}>
              −1000 ₽ вам<br/>и другу
            </div>
            <div className="t-body" style={{ color: 'var(--text-2)', marginTop: 10, maxWidth: 280 }}>
              Друг получит 1000 ₽ на первый абонемент. Вам — 1000 ₽ на следующее продление, как только он впервые зайдёт в зал.
            </div>
          </div>
        </div>

        {/* Stats */}
        <div style={{ padding: '0 16px 14px', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
          <StatTile big={3} label="Приглашено" />
          <StatTile big={2} label="Зашли в зал" tone="ok" />
          <StatTile big="2 000 ₽" label="На балансе" tone="accent" />
        </div>

        {/* Code card */}
        <div style={{ padding: '0 16px 14px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', padding: '0 4px 8px' }}>
            Твой код
          </div>
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{
              padding: '20px 18px',
              background: 'var(--surface-2)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
              borderBottom: '0.5px solid var(--border)',
            }}>
              <div>
                <div className="t-h2" style={{
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                  letterSpacing: 1, fontSize: 22,
                }}>{code}</div>
                <div className="t-small" style={{ marginTop: 2 }}>fitclub.app/{code.toLowerCase()}</div>
              </div>
              <button onClick={onCopy} className="press" style={{
                border: 0, background: copied ? 'var(--accent)' : 'var(--text)',
                color: copied ? '#06120c' : 'var(--bg)',
                padding: '0 14px', height: 40, borderRadius: 12,
                fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                display: 'flex', alignItems: 'center', gap: 6,
                transition: 'background 0.18s, color 0.18s',
              }}>
                <Icon name={copied ? 'check' : 'copy'} size={14} color="currentColor" strokeWidth={2.2} />
                {copied ? 'Скопировано' : 'Копировать'}
              </button>
            </div>
            <div style={{ padding: 12, display: 'flex', gap: 8 }}>
              <ShareBtn icon="chat" label="WhatsApp" tint="#25d366" onClick={() => setShared(s => s + 1)} />
              <ShareBtn icon="send" label="Telegram" tint="#229ed9" onClick={() => setShared(s => s + 1)} />
              <ShareBtn icon="link" label="Ссылка" tint="var(--text)" onClick={onCopy} />
            </div>
          </div>
        </div>

        {/* How it works */}
        <div style={{ padding: '0 16px 14px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', padding: '0 4px 8px' }}>
            Как это работает
          </div>
          <div className="card" style={{ padding: 0 }}>
            <Step n={1} title="Поделись кодом" body="Скинь код или ссылку другу — кнопкой выше." />
            <Divider />
            <Step n={2} title="Друг покупает абонемент" body="Вводит код и получает 1000 ₽ на первую покупку." />
            <Divider />
            <Step n={3} title="Получаешь бонус" body="Когда друг впервые откроет QR — 1000 ₽ зачислятся вам." />
          </div>
        </div>

        {/* Friends list */}
        <div style={{ padding: '0 16px 24px' }}>
          <div className="row-between" style={{ padding: '0 4px 8px' }}>
            <div className="t-mini" style={{ color: 'var(--text-3)' }}>Друзья</div>
            <div className="t-mini" style={{ color: 'var(--text-3)' }}>{REFERRAL_FRIENDS.length}</div>
          </div>
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {REFERRAL_FRIENDS.map((f, i) => (
              <React.Fragment key={f.id}>
                {i > 0 && <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 60 }} />}
                <FriendRow f={f} />
              </React.Fragment>
            ))}
          </div>
          <div className="t-small" style={{ padding: '12px 4px 0', color: 'var(--text-3)' }}>
            Бонусы суммируются. Можно потратить на продление абонемента или персональные тренировки.
          </div>
        </div>
      </div>
    </div>
  );
};

function StatTile({ big, label, tone }) {
  const color = tone === 'accent' ? 'var(--accent-deep)' : tone === 'ok' ? 'var(--text)' : 'var(--text)';
  const bg = tone === 'accent' ? 'var(--accent-soft)' : 'var(--surface)';
  return (
    <div style={{
      borderRadius: 'var(--r-lg)', padding: '14px 12px',
      background: bg,
      border: '0.5px solid var(--border)',
    }}>
      <div className="t-h2 t-num" style={{ fontSize: 22, color }}>{big}</div>
      <div className="t-mini" style={{ color: 'var(--text-3)', marginTop: 2, textTransform: 'none', letterSpacing: 0.2, fontWeight: 500, fontSize: 11.5 }}>
        {label}
      </div>
    </div>
  );
}

function ShareBtn({ icon, label, tint, onClick }) {
  return (
    <button onClick={onClick} className="press" style={{
      flex: 1, border: 0, background: 'var(--surface-2)',
      borderRadius: 12, padding: '10px 6px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
      cursor: 'pointer', fontFamily: 'inherit',
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: 999,
        background: 'var(--surface)', border: '0.5px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: tint,
      }}>
        <Icon name={icon} size={16} color="currentColor" strokeWidth={2} />
      </div>
      <span style={{ fontSize: 11, color: 'var(--text-2)', fontWeight: 500 }}>{label}</span>
    </button>
  );
}

function Step({ n, title, body }) {
  return (
    <div style={{ padding: '14px 16px', display: 'flex', gap: 12 }}>
      <div style={{
        width: 28, height: 28, borderRadius: 999,
        background: 'var(--accent-soft)', color: 'var(--accent-deep)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontWeight: 700, fontSize: 13, fontVariantNumeric: 'tabular-nums', flexShrink: 0,
      }}>{n}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-h3" style={{ fontSize: 15 }}>{title}</div>
        <div className="t-small" style={{ marginTop: 2 }}>{body}</div>
      </div>
    </div>
  );
}

function FriendRow({ f }) {
  const tone =
    f.status === 'paid' ? { label: '+1000 ₽', cls: 'chip-accent' } :
    f.status === 'joined' ? { label: 'Зашёл в зал', cls: 'chip-accent' } :
    { label: 'Ждём', cls: '' };
  return (
    <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <Avatar initials={f.initials} bg={f.bg} color={f.color} size={36} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-h3" style={{ fontSize: 14 }}>{f.name}</div>
        <div className="t-small" style={{ marginTop: 1, fontSize: 12 }}>{f.note}</div>
      </div>
      <span className={`chip ${tone.cls}`} style={{
        height: 22, padding: '0 9px', fontSize: 11.5,
        background: f.status === 'paid' ? 'var(--accent-soft)' : f.status === 'joined' ? 'var(--surface-2)' : 'transparent',
        color: f.status === 'paid' ? 'var(--accent-deep)' : 'var(--text-2)',
        border: f.status === 'pending' ? '0.5px dashed var(--border-strong)' : 0,
      }}>{tone.label}</span>
    </div>
  );
}

const REFERRAL_FRIENDS = [
  { id: 'rf1', name: 'Никита Б.', initials: 'НБ', bg: '#dbeafe', color: '#1d4ed8', status: 'paid', note: 'Купил годовой · 12 апр' },
  { id: 'rf2', name: 'Кира Л.', initials: 'КЛ', bg: '#f3e8ff', color: '#7e22ce', status: 'paid', note: 'Купила полугодовой · 28 мар' },
  { id: 'rf3', name: 'Тимур Г.', initials: 'ТГ', bg: '#fef3c7', color: '#a36a16', status: 'joined', note: 'Первый визит сегодня' },
  { id: 'rf4', name: 'Маша С.', initials: 'МС', bg: '#fee2e2', color: '#dc2626', status: 'pending', note: 'Перешла по ссылке' },
];

