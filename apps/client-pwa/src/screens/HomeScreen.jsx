import React from 'react';
import { Avatar } from '@/components/Avatar.jsx';
import { EmptyState } from '@/components/EmptyState.jsx';
import { Icon } from '@/components/Icon.jsx';
import { PullToRefresh } from '@/components/PullToRefresh.jsx';
import { QRPattern } from '@/components/QRPattern.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { SwipeRow } from '@/components/SwipeRow.jsx';
import { GYM_INFO, NOTIFICATIONS, TRAINER_CANCEL, UPCOMING_BOOKING } from '@/data';
import { formatCountdown, useCountdown } from '@/hooks/useCountdown.js';
import { getSubInfo } from '@/utils/subInfo.js';

// Open/closed status chip — shown in home header, opens GymInfoSheet
export function GymStatusPill({ onClick }) {
  const g = (typeof GYM_INFO !== 'undefined') ? GYM_INFO : null;
  if (!g) return null;
  const open = g.status.open;
  const label = open ? `Открыто до ${g.status.until}` : `Закрыто · откроемся в ${g.hours[(g.todayIdx + 1) % 7].open}`;
  return (
    <button
      onClick={onClick}
      className="press"
      style={{
        height: 30, padding: '0 12px 0 10px',
        border: '0.5px solid var(--border)',
        background: 'var(--surface)', borderRadius: 999,
        display: 'inline-flex', alignItems: 'center', gap: 7,
        cursor: 'pointer',
        flexShrink: 0,
      }}
    >
      <span style={{
        width: 7, height: 7, borderRadius: 999,
        background: open ? '#10b981' : 'var(--text-3)',
        boxShadow: open ? '0 0 0 3px rgba(16,185,129,0.18)' : 'none',
        animation: open ? 'pulse-soft 2.4s ease-in-out infinite' : 'none',
        flexShrink: 0,
      }} />
      <span style={{
        fontSize: 12, fontWeight: 600, letterSpacing: -0.1,
        color: 'var(--text-2)', whiteSpace: 'nowrap',
        overflow: 'hidden', textOverflow: 'ellipsis',
      }}>
        {label}
      </span>
      <Icon name="chevronRight" size={12} color="var(--text-3)" strokeWidth={2.2} />
    </button>
  );
}

export const HomeScreen = ({ tweaks, onOpenQR, onOpenPlans, onOpenManage, onOpenReferral, onOpenGymInfo, onOpenNotifications, onTab, setTweak }) => {
  const sub = getSubInfo(tweaks.subState);
  const variant = tweaks.homeVariant || 'classic';
  const userName = tweaks.userName || 'Саша';
  const isEmpty = tweaks.dataMode === 'empty';
  const trainerCancelled = tweaks.gymEvent === 'trainer-cancelled';
  const unread = isEmpty ? 0 : NOTIFICATIONS.filter(n => n.unread).length;
  const [showToast, setShowToast] = React.useState(false);

  const greeting = (() => {
    const h = 9; // demo time
    if (h < 5) return 'Доброй ночи';
    if (h < 12) return 'Доброе утро';
    if (h < 18) return 'Привет';
    return 'Добрый вечер';
  })();

  const subTone = sub.tone === 'ok' ? 'chip-accent' : sub.tone === 'warn' ? 'chip-warn' : 'chip-danger';
  const fillTone = sub.tone === 'ok' ? '' : sub.tone === 'warn' ? 'warn' : 'danger';
  const pct = Math.max(2, Math.min(100, (sub.daysLeft / sub.total) * 100));

  return (
    <div className="page" style={{ background: 'var(--bg)' }}>
      <StatusBar />
      <PullToRefresh
        scrollPaddingTop={54}
        onRefresh={() => {
          setShowToast(true);
          setTimeout(() => setShowToast(false), 2400);
          return new Promise(r => setTimeout(r, 700));
        }}
      >
        {showToast && <div className="ptr-toast">Обновлено · сейчас</div>}
        {/* Header */}
        <div style={{
          padding: '4px 16px 18px',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="t-small" style={{
              color: 'var(--text-3)', fontWeight: 500, fontSize: 12,
            }}>{greeting}</div>
            <div className="t-h2" style={{
              marginTop: 1, fontSize: 22, letterSpacing: -0.3,
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}>{userName}</div>
          </div>

          <GymStatusPill onClick={onOpenGymInfo} />
        </div>

        {variant === 'classic' && <HomeClassic isEmpty={isEmpty} trainerCancelled={trainerCancelled} sub={sub} subTone={subTone} fillTone={fillTone} pct={pct} onOpenQR={onOpenQR} onOpenPlans={onOpenPlans} onOpenManage={onOpenManage} onOpenNotifications={onOpenNotifications} onTab={onTab} unread={unread} subCardStyle={tweaks.subCardStyle || 'eyebrow'} />}
        {variant === 'qr-hero' && <HomeQrHero isEmpty={isEmpty} trainerCancelled={trainerCancelled} sub={sub} subTone={subTone} fillTone={fillTone} pct={pct} onOpenQR={onOpenQR} onOpenPlans={onOpenPlans} onOpenManage={onOpenManage} onOpenNotifications={onOpenNotifications} onTab={onTab} unread={unread} />}
        {variant === 'minimal' && <HomeMinimal isEmpty={isEmpty} trainerCancelled={trainerCancelled} sub={sub} subTone={subTone} fillTone={fillTone} pct={pct} onOpenQR={onOpenQR} onOpenPlans={onOpenPlans} onOpenManage={onOpenManage} onOpenNotifications={onOpenNotifications} onTab={onTab} unread={unread} />}

        <div style={{ height: 24 }} />
      </PullToRefresh>
    </div>
  );

  function HomePullToRefreshScroller({ children }) {
    return (
      <PullToRefresh
        scrollPaddingTop={54}
        onRefresh={() => {
          setShowToast(true);
          setTimeout(() => setShowToast(false), 2400);
          return new Promise(r => setTimeout(r, 700));
        }}
      >
        {children}
      </PullToRefresh>
    );
  }
};

// Variant A: Classic — subscription card + QR button + actions + feed
export function HomeClassic({ isEmpty, sub, subTone, fillTone, pct, onOpenQR, onOpenPlans, onOpenManage, onOpenNotifications, onTab, unread, trainerCancelled, subCardStyle }) {
  return (
    <>
      {/* Trainer cancelled — strong alert */}
      {trainerCancelled && (
        <div style={{ padding: '0 16px 12px' }}>
          <TrainerCancelCard onTab={onTab} />
        </div>
      )}

      {/* Expired sub — strong banner */}
      {sub.tone === 'danger' && (
        <div style={{ padding: '0 16px 12px' }}>
          <ExpiredAlert sub={sub} onOpenPlans={onOpenPlans} />
        </div>
      )}

      {/* Subscription card */}
      <div style={{ padding: '0 16px 12px' }}>
        <div className="card fade-up" style={{
          padding: 18,
          position: 'relative', overflow: 'hidden',
          ...(subCardStyle === 'stripe' ? {
            borderLeft: '4px solid ' + (sub.tone === 'ok' ? 'var(--accent)' : sub.tone === 'warn' ? 'var(--warn)' : 'var(--danger)'),
          } : {}),
        }}>
          {subCardStyle === 'eyebrow' && (
            <div className="row-between" style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                <div className="t-mini" style={{ color: 'var(--text-3)' }}>Абонемент</div>
                <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                  <SubDot tone={sub.tone} />
                  <span className="t-h3" style={{ fontSize: 17 }}>{sub.label}</span>
                </div>
              </div>
              <Icon name="card" size={20} color="var(--text-3)" />
            </div>
          )}
          {subCardStyle === 'split' && (
            <div className="row-between" style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                <div className="t-mini" style={{ color: 'var(--text-3)' }}>Абонемент</div>
                <span className="t-h2" style={{ fontSize: 19 }}>{sub.label}</span>
              </div>
              <div className="row" style={{ gap: 6, alignItems: 'center' }}>
                <SubDot tone={sub.tone} />
                <span className="t-small" style={{
                  fontWeight: 600,
                  color: sub.tone === 'ok' ? 'var(--accent-deep)' : sub.tone === 'warn' ? '#a36a16' : 'var(--danger)',
                }}>
                  {sub.tone === 'ok' ? 'активен' : sub.tone === 'warn' ? 'истекает' : 'истёк'}
                </span>
              </div>
            </div>
          )}
          {subCardStyle === 'stripe' && (
            <div className="row-between" style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                <span className="t-h2" style={{ fontSize: 19 }}>{sub.label} абонемент</span>
                <span className="t-small" style={{
                  fontWeight: 500,
                  color: sub.tone === 'ok' ? 'var(--accent-deep)' : sub.tone === 'warn' ? '#a36a16' : 'var(--danger)',
                }}>
                  {sub.tone === 'ok' ? 'активен · в строю' : sub.tone === 'warn' ? 'истекает скоро' : 'истёк'}
                </span>
              </div>
              <Icon name="card" size={20} color="var(--text-3)" />
            </div>
          )}
          <div className="row" style={{ alignItems: 'baseline', gap: 6 }}>
            <span className="t-display t-num">{sub.daysLeft}</span>
            <span className="t-h3" style={{ color: 'var(--text-2)', fontWeight: 500 }}>
              {sub.daysLeft === 0 ? 'дней — истёк' : sub.daysLeft === 1 ? 'день' : sub.daysLeft < 5 ? 'дня' : 'дней'}
            </span>
          </div>
          <div className="t-small" style={{ marginTop: 2 }}>
            {sub.tone === 'danger' ? `Истёк ${sub.until}` : `до ${sub.until}`}
          </div>
          <div className="progress-track" style={{ marginTop: 14 }}>
            <div className={`progress-fill ${fillTone}`} style={{ width: `${pct}%` }} />
          </div>
          {sub.tone !== 'ok' && (
            <button onClick={onOpenPlans} className="btn btn-accent" style={{ width: '100%', marginTop: 14 }}>
              Продлить{sub.tone === 'warn' ? ' со скидкой 15%' : ''}
            </button>
          )}
        </div>
      </div>

      {/* Upcoming booking — tappable to manage */}
      {!isEmpty ? (
        <UpcomingCard onClick={onOpenManage} onCancel={onOpenManage} />
      ) : (
        <div style={{ padding: '0 16px 12px' }}>
          <button
            onClick={() => onTab('book')}
            className="card press"
            style={{
              width: '100%', appearance: 'none', cursor: 'pointer', textAlign: 'left',
              padding: 16, display: 'flex', alignItems: 'center', gap: 12,
              border: '0.5px dashed var(--border-strong)', background: 'transparent',
              color: 'var(--text)',
            }}
          >
            <div style={{
              width: 48, height: 48, borderRadius: 12,
              background: 'var(--accent-soft)', color: 'var(--accent-deep)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              <Icon name="calendar" size={22} color="currentColor" strokeWidth={1.8} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="t-mini" style={{ color: 'var(--text-3)' }}>Записей пока нет</div>
              <div className="t-h3" style={{ marginTop: 2, fontSize: 15 }}>
                Запишись на первую тренировку
              </div>
              <div className="t-small" style={{ marginTop: 1 }}>
                В первый раз — со скидкой 30%
              </div>
            </div>
            <Icon name="chevronRight" size={16} color="var(--text-3)" />
          </button>
        </div>
      )}

      {/* QR pass — big primary action */}
      <div style={{ padding: '4px 16px 12px' }}>
        <button onClick={onOpenQR} className="press" style={{
          width: '100%', border: 0, background: 'var(--text)', color: 'var(--bg)',
          borderRadius: 'var(--r-xl)', padding: '20px 22px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
          cursor: 'pointer', textAlign: 'left',
        }}>
          <div>
            <div className="t-mini" style={{ color: 'var(--text-3)', opacity: 0.8 }}>Пропуск в зал</div>
            <div className="t-h2" style={{ color: 'var(--bg)', marginTop: 4 }}>Открыть QR-код</div>
            <div className="t-small" style={{ color: 'var(--text-3)', marginTop: 4 }}>Покажи на турникете</div>
          </div>
          <div style={{
            width: 64, height: 64, borderRadius: 16,
            background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon name="qr" size={36} color="#0a0a0a" strokeWidth={1.6} />
          </div>
        </button>
      </div>

      {/* Quick actions */}
      <div style={{ padding: '0 16px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <QuickTile icon="calendar" title="Записаться" sub="к тренеру" onClick={() => onTab('book')} />
        <QuickTile icon="chat" title="Чат" sub="админ + тренер" onClick={() => onTab('chat')} badge={2} />
      </div>

      {/* Feed */}
      <FeedSection unread={unread} isEmpty={isEmpty} onOpenNotifications={onOpenNotifications} />
    </>
  );
}

// Reusable live status dot for sub card variants
export function SubDot({ tone }) {
  const color = tone === 'ok' ? 'var(--accent)' : tone === 'warn' ? 'var(--warn)' : 'var(--danger)';
  const ring = tone === 'ok'
    ? '0 0 0 3px color-mix(in oklab, var(--accent) 22%, transparent)'
    : tone === 'warn'
    ? '0 0 0 3px color-mix(in oklab, var(--warn) 22%, transparent)'
    : '0 0 0 3px color-mix(in oklab, var(--danger) 22%, transparent)';
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: 999,
      background: color, boxShadow: ring,
      animation: tone === 'ok' ? 'pulse-soft 2.4s ease-in-out infinite' : 'none',
      flexShrink: 0,
    }} />
  );
}

// Variant B: QR-hero — QR is huge at top
export function HomeQrHero({ isEmpty, sub, subTone, fillTone, pct, onOpenQR, onOpenPlans, onOpenManage, onOpenNotifications, onTab, unread, trainerCancelled }) {
  return (
    <>
      {trainerCancelled && (
        <div style={{ padding: '0 16px 12px' }}>
          <TrainerCancelCard onTab={onTab} />
        </div>
      )}
      {sub.tone === 'danger' && (
        <div style={{ padding: '0 16px 12px' }}>
          <ExpiredAlert sub={sub} onOpenPlans={onOpenPlans} />
        </div>
      )}
      {/* QR hero */}
      <div style={{ padding: '0 16px 14px' }}>
        <button onClick={onOpenQR} className="press" style={{
          width: '100%', border: 0, background: 'var(--surface)',
          borderRadius: 'var(--r-xl)', padding: '24px 20px 20px',
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          cursor: 'pointer', boxShadow: 'var(--sh-2)', borderTop: '1px solid var(--border)',
        }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', alignSelf: 'flex-start' }}>
            Пропуск · #4821
          </div>
          <div style={{ marginTop: 10, padding: 14, background: '#fff', borderRadius: 16 }}>
            <QRPattern size={180} color="#0a0a0a" />
          </div>
          <div style={{ marginTop: 14, color: 'var(--text-2)', fontSize: 13, fontWeight: 500 }}>
            Тапни, чтобы увеличить
          </div>
        </button>
      </div>

      {/* Subscription compact */}
      <div style={{ padding: '0 16px 12px' }}>
        <div className="card" style={{ padding: 14 }}>
          <div className="row-between">
            <div>
              <div className="row" style={{ gap: 8 }}>
                <span className="t-h3" style={{ fontWeight: 600 }}>{sub.daysLeft} {sub.daysLeft === 1 ? 'день' : sub.daysLeft < 5 ? 'дня' : 'дней'}</span>
                <span className={`chip ${subTone}`} style={{ height: 22, padding: '0 9px', fontSize: 11.5 }}>{sub.label}</span>
              </div>
              <div className="t-small" style={{ marginTop: 2 }}>до {sub.until}</div>
            </div>
            {sub.tone !== 'ok' && (
              <button onClick={onOpenPlans} className="btn btn-accent btn-sm">Продлить</button>
            )}
          </div>
          <div className="progress-track" style={{ marginTop: 12 }}>
            <div className={`progress-fill ${fillTone}`} style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>

      {!isEmpty && <UpcomingCard onClick={onOpenManage} onCancel={onOpenManage} compact />}

      <div style={{ padding: '4px 16px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <QuickTile icon="calendar" title="Записаться" sub="к тренеру" onClick={() => onTab('book')} />
        <QuickTile icon="chat" title="Чат" sub="админ + тренер" onClick={() => onTab('chat')} badge={isEmpty ? 0 : 2} />
      </div>

      <FeedSection unread={unread} isEmpty={isEmpty} onOpenNotifications={onOpenNotifications} />
    </>
  );
}

// Variant C: Minimal — single big "next thing" hero
export function HomeMinimal({ isEmpty, sub, subTone, fillTone, pct, onOpenQR, onOpenPlans, onOpenManage, onOpenNotifications, onTab, unread, trainerCancelled }) {
  const ms = useCountdown(4 * 3600 * 1000 + 12 * 60 * 1000);
  const cd = formatCountdown(ms);
  const banner = (
    <>
      {trainerCancelled && (
        <div style={{ padding: '0 16px 12px' }}>
          <TrainerCancelCard onTab={onTab} />
        </div>
      )}
      {sub.tone === 'danger' && (
        <div style={{ padding: '0 16px 12px' }}>
          <ExpiredAlert sub={sub} onOpenPlans={onOpenPlans} />
        </div>
      )}
    </>
  );
  if (isEmpty) {
    return (
      <>
        {banner}
        <div style={{ padding: '0 20px 8px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Добро пожаловать</div>
          <div className="t-display" style={{ marginTop: 4, marginBottom: 6, letterSpacing: -1 }}>
            Начни<br/>с первого визита
          </div>
          <div className="t-body" style={{ color: 'var(--text-2)' }}>
            Открой QR на турникете или запишись к тренеру.
          </div>
        </div>

        <div style={{ padding: '14px 16px 8px', display: 'flex', gap: 10 }}>
          <button onClick={onOpenQR} className="btn btn-accent" style={{ flex: 1, height: 56 }}>
            <Icon name="qr" size={20} color="#06120c" strokeWidth={2} />
            Пройти в зал
          </button>
        </div>

        <div style={{ padding: '4px 16px 14px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <button onClick={() => onTab('book')} className="btn btn-ghost" style={{ height: 44 }}>
            Записаться
          </button>
          <button onClick={() => onTab('chat')} className="btn btn-ghost" style={{ height: 44 }}>
            Написать
          </button>
        </div>

        <FeedSection unread={0} isEmpty onOpenNotifications={onOpenNotifications} />
      </>
    );
  }
  return (
    <>
      {banner}
      <div style={{ padding: '0 20px 8px' }}>
        <div className="t-mini" style={{ color: 'var(--text-3)', fontVariantNumeric: 'tabular-nums' }}>
          Сегодня в {UPCOMING_BOOKING.time} · через {cd.primary}
        </div>
        <div className="t-display" style={{ marginTop: 4, marginBottom: 6, letterSpacing: -1 }}>
          Тренировка<br/>с {UPCOMING_BOOKING.trainerInstr}
        </div>
        <div className="t-body" style={{ color: 'var(--text-2)' }}>
          Зал на Тверской · {UPCOMING_BOOKING.focus}
        </div>
      </div>

      <div style={{ padding: '14px 16px 8px', display: 'flex', gap: 10 }}>
        <button onClick={onOpenQR} className="btn btn-accent" style={{ flex: 1, height: 56 }}>
          <Icon name="qr" size={20} color="#06120c" strokeWidth={2} />
          Пройти в зал
        </button>
      </div>

      <div style={{ padding: '4px 16px 14px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <button onClick={onOpenManage} className="btn btn-ghost" style={{ height: 44 }}>
          Перенести
        </button>
        <button onClick={() => onTab('chat')} className="btn btn-ghost" style={{ height: 44 }}>
          Написать
        </button>
      </div>

      {/* Sub strip */}
      <div style={{ padding: '0 16px 14px' }}>
        <button onClick={() => onTab('profile')} style={{
          width: '100%', border: 0, background: 'transparent', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px',
          borderRadius: 'var(--r-lg)', background: 'var(--surface)',
          textAlign: 'left',
        }}>
          <div className="dot" style={{
            background: sub.tone === 'ok' ? 'var(--accent)' : sub.tone === 'warn' ? 'var(--warn)' : 'var(--danger)',
            width: 10, height: 10,
          }} />
          <div style={{ flex: 1 }}>
            <div className="t-h3">{sub.label}</div>
            <div className="t-small">{sub.daysLeft === 0 ? `истёк ${sub.until}` : `${sub.daysLeft} ${sub.daysLeft === 1 ? 'день' : 'дней'} до ${sub.until}`}</div>
          </div>
          {sub.tone !== 'ok' ? (
            <span onClick={(e) => { e.stopPropagation(); onOpenPlans(); }}
                  className="chip chip-accent"
                  style={{ background: 'var(--text)', color: 'var(--bg)' }}>Продлить</span>
          ) : (
            <Icon name="chevronRight" size={18} color="var(--text-3)" />
          )}
        </button>
      </div>

      <FeedSection unread={unread} isEmpty={isEmpty} onOpenNotifications={onOpenNotifications} />
    </>
  );
}

// ─── Upcoming booking card (used on classic + qr-hero) ─────────
export function UpcomingCard({ onClick, compact, onCancel }) {
  const b = UPCOMING_BOOKING;
  // 4h 12m from "now" — ticks down each second
  const ms = useCountdown(4 * 3600 * 1000 + 12 * 60 * 1000);
  const cd = formatCountdown(ms);
  const cardInner = (
    <button
      onClick={onClick}
      className="press card"
      style={{
        appearance: 'none', cursor: 'pointer', textAlign: 'left', width: '100%',
        padding: compact ? 14 : '16px',
        display: 'flex', alignItems: 'center', gap: 12,
        color: 'var(--text)', borderRadius: 'var(--r-lg)',
      }}
    >
      <div style={{
        width: 48, height: 48, borderRadius: 12,
        background: b.trainerBg, color: b.trainerColor,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <span className="t-mini" style={{
          fontSize: 9, letterSpacing: 0.6, color: b.trainerColor, fontWeight: 700,
          opacity: 0.85,
        }}>{b.dow.toUpperCase()}</span>
        <span style={{
          fontSize: 18, fontWeight: 700, lineHeight: 1, color: b.trainerColor,
          fontVariantNumeric: 'tabular-nums',
        }}>{b.dayNum}</span>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="row-between" style={{ gap: 8 }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', whiteSpace: 'nowrap' }}>Ближайшая запись</div>
          <div className="t-mini t-num" style={{ color: 'var(--accent-deep)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
            через {cd.primary}
          </div>
        </div>
        <div className="t-h3" style={{ marginTop: 2, fontSize: 15 }}>
          {b.time} · {b.focus}
        </div>
        <div className="row-between" style={{ marginTop: 1, gap: 8 }}>
          <div className="t-small">с {b.trainer}</div>
          <span style={{
            color: 'var(--accent-deep)', fontSize: 12.5, fontWeight: 600,
            display: 'inline-flex', alignItems: 'center', gap: 2,
            whiteSpace: 'nowrap', flexShrink: 0,
          }}>
            Управлять
            <Icon name="chevronRight" size={11} color="currentColor" strokeWidth={2.4} />
          </span>
        </div>
      </div>
    </button>
  );
  return (
    <div style={{ padding: '0 16px 12px' }}>
      <SwipeRow onAction={() => onCancel?.()} actionLabel="Отменить" actionIcon="close">
        {cardInner}
      </SwipeRow>
    </div>
  );
}

export function QuickTile({ icon, title, sub, onClick, badge }) {
  return (
    <button onClick={onClick} className="press" style={{
      background: 'var(--surface)', borderRadius: 'var(--r-lg)',
      padding: '16px', textAlign: 'left', cursor: 'pointer',
      border: '0.5px solid var(--border)', position: 'relative',
      color: 'var(--text)', fontFamily: 'inherit',
    }}>
      <div className="row-between" style={{ marginBottom: 12 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10, background: 'var(--surface-2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name={icon} size={20} color="var(--text)" />
        </div>
        {badge ? <span className="badge">{badge}</span> : null}
      </div>
      <div className="t-h3">{title}</div>
      <div className="t-small">{sub}</div>
    </button>
  );
}

// ─── Expired subscription banner ─────────────────────────────────
export function ExpiredAlert({ sub, onOpenPlans }) {
  return (
    <div className="card fade-up" style={{
      padding: 16, background: 'var(--danger-soft, #fef2f2)',
      border: '0.5px solid color-mix(in oklab, var(--danger) 35%, transparent)',
      display: 'flex', flexDirection: 'column', gap: 12,
    }}>
      <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
        <div style={{
          width: 40, height: 40, borderRadius: 12, flexShrink: 0,
          background: 'var(--danger)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          animation: 'pulse-soft 2s ease-in-out infinite',
        }}>
          <Icon name="alert" size={22} color="currentColor" strokeWidth={2.2} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="t-h3" style={{ fontSize: 15, color: 'var(--danger)' }}>
            Абонемент закончился {sub.until}
          </div>
          <div className="t-small" style={{ marginTop: 4, color: 'var(--text-2)', lineHeight: 1.45 }}>
            QR не сработает на турникете. Продли сегодня — сохраним твою серию посещений и скидку на тренера.
          </div>
        </div>
      </div>
      <button onClick={onOpenPlans} className="btn" style={{
        width: '100%', height: 46, background: 'var(--danger)', color: '#fff',
        border: 0, fontWeight: 600,
      }}>
        Выбрать тариф
        <Icon name="arrowRight" size={16} color="currentColor" strokeWidth={2} />
      </button>
      <style>{`
        @keyframes pulse-soft {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.05); }
        }
      `}</style>
    </div>
  );
}

// ─── Trainer cancellation card ───────────────────────────────────
export function TrainerCancelCard({ onTab }) {
  const c = TRAINER_CANCEL;
  return (
    <div className="card fade-up" style={{
      padding: 0, overflow: 'hidden',
      border: '0.5px solid color-mix(in oklab, var(--danger) 35%, transparent)',
    }}>
      <div style={{
        background: 'var(--danger)', color: '#fff', padding: '10px 16px',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <Icon name="alert" size={14} color="currentColor" strokeWidth={2.4} />
        <span className="t-mini" style={{ color: '#fff', letterSpacing: 0.6, fontWeight: 700 }}>
          Тренировка отменена
        </span>
      </div>
      <div style={{ padding: 16 }}>
        <div className="row" style={{ gap: 12, alignItems: 'center' }}>
          <Avatar initials={c.initials} bg={c.bg} color={c.color} size={42} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="t-h3" style={{ fontSize: 15 }}>{c.trainer}</div>
            <div className="t-small" style={{ marginTop: 2 }}>{c.date} · {c.reason}</div>
          </div>
        </div>
        <div className="t-small" style={{ marginTop: 12, color: 'var(--text-2)', lineHeight: 1.5 }}>
          {c.reasonFull} Вернули <b style={{ color: 'var(--text)', fontVariantNumeric: 'tabular-nums' }}>{c.refund.toLocaleString('ru')} ₽</b> на карту.
        </div>
        <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <button onClick={() => onTab('book')} className="btn btn-accent" style={{ height: 44 }}>
            Перенести
          </button>
          <button onClick={() => onTab('chat')} className="btn btn-ghost" style={{ height: 44 }}>
            Написать
          </button>
        </div>
      </div>
    </div>
  );
}

export function FeedSection({ unread, isEmpty, onOpenNotifications }) {
  if (isEmpty) {
    return (
      <div style={{ padding: '8px 4px 0' }}>
        <div style={{ padding: '4px 20px 4px' }}>
          <div className="t-h2">Уведомления</div>
          <div className="t-small" style={{ color: 'var(--text-3)', marginTop: 2 }}>
            история анонсов и пушей зала
          </div>
        </div>
        <div style={{ padding: '0 16px' }}>
          <div className="card" style={{ padding: 0 }}>
            <EmptyState
              illustration="sparkle"
              title="Тут будут новости"
              body="Пиши на ресепшен — расскажем про расписание, события и акции."
              compact
            />
          </div>
        </div>
      </div>
    );
  }
  const visible = NOTIFICATIONS.slice(0, 3);
  const hasMore = NOTIFICATIONS.length > visible.length;
  return (
    <div style={{ padding: '8px 4px 0' }}>
      <button
        onClick={onOpenNotifications}
        className="press"
        style={{
          appearance: 'none', border: 0, background: 'transparent',
          width: '100%', cursor: onOpenNotifications ? 'pointer' : 'default',
          padding: '4px 20px 10px', display: 'flex',
          alignItems: 'center', justifyContent: 'space-between',
          fontFamily: 'inherit', color: 'var(--text)', textAlign: 'left',
        }}>
        <div className="row" style={{ gap: 8 }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="row" style={{ gap: 8, alignItems: 'center' }}>
              <span className="t-h2">Уведомления</span>
              {unread > 0 && (
                <span style={{
                  minWidth: 20, height: 20, padding: '0 6px',
                  borderRadius: 999, background: 'var(--accent)', color: '#06120c',
                  fontSize: 11, fontWeight: 700,
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  fontVariantNumeric: 'tabular-nums',
                }}>{unread}</span>
              )}
            </div>
            <div className="t-small" style={{ color: 'var(--text-3)', marginTop: 2, fontWeight: 400 }}>
              история анонсов и пушей зала
            </div>
          </div>
        </div>
        {onOpenNotifications && (
          <span className="t-small" style={{
            color: 'var(--text-2)', fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 2,
          }}>
            Все
            <Icon name="chevronRight" size={14} color="var(--text-3)" strokeWidth={2.2} />
          </span>
        )}
      </button>
      <div className="stack-2" style={{ padding: '0 16px' }}>
        {visible.map(n => (
          <div key={n.id} className="card press" style={{
            padding: '14px 16px', display: 'flex', gap: 12,
            border: n.unread ? '0.5px solid var(--border-strong)' : '0.5px solid var(--border)',
          }}>
            <div style={{
              width: 38, height: 38, borderRadius: 10,
              background: n.kind === 'promo' ? 'var(--accent-soft)' :
                          n.kind === 'schedule' ? 'var(--warn-soft)' :
                          n.kind === 'message' ? '#fef3c7' : 'var(--surface-2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}>
              <Icon
                name={n.kind === 'promo' ? 'tag' : n.kind === 'schedule' ? 'clock' : n.kind === 'message' ? 'chat' : 'info'}
                size={20}
                color={n.kind === 'promo' ? 'var(--accent-deep)' :
                       n.kind === 'schedule' ? '#a36a16' :
                       n.kind === 'message' ? '#a36a16' : 'var(--text-2)'}
              />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="row-between" style={{ alignItems: 'flex-start' }}>
                <div className="t-h3" style={{ fontSize: 15 }}>{n.title}</div>
                {n.unread && <span className="dot" style={{ marginTop: 7 }} />}
              </div>
              <div className="t-small" style={{ marginTop: 2, color: 'var(--text-2)' }}>{n.body}</div>
              <div className="t-mini" style={{ marginTop: 6, fontWeight: 500, letterSpacing: 0.2, color: 'var(--text-3)', textTransform: 'none' }}>{n.time}</div>
            </div>
          </div>
        ))}
        {hasMore && onOpenNotifications && (
          <button onClick={onOpenNotifications} className="press" style={{
            appearance: 'none', border: '0.5px dashed var(--border-strong)',
            background: 'transparent', borderRadius: 'var(--r-lg)',
            padding: '12px 16px', cursor: 'pointer',
            color: 'var(--text-2)', fontFamily: 'inherit',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            fontSize: 13, fontWeight: 600,
          }}>
            Ещё {NOTIFICATIONS.length - visible.length}
            <Icon name="chevronRight" size={14} color="var(--text-3)" strokeWidth={2.2} />
          </button>
        )}
      </div>
    </div>
  );
}

