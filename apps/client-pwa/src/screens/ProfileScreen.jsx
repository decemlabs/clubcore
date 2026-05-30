import React from 'react';
import { Avatar } from '@/components/Avatar.jsx';
import { EmptyState } from '@/components/EmptyState.jsx';
import { LoadError } from '@/components/LoadError.jsx';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import {
  useClientHome,
  useClientVisitHistory,
  useClientPtHistory,
  useClientPaymentHistory,
} from '@/data';
import { getSubInfo } from '@/utils/subInfo.js';
import { useAuth } from '@/context/AuthContext.jsx';

// ─── In-file adapter: API membership shape → subInfo render shape ─────────
// Mirrors the adapter in HomeScreen.jsx
function toSubInfo(membership) {
  if (!membership) {
    return { daysLeft: 0, total: 90, until: '—', label: 'Нет абонемента', tone: 'danger' };
  }
  const daysLeft = Math.max(0, membership.days_until_end ?? 0);
  const tone = membership.expiring_soon
    ? (daysLeft === 0 ? 'danger' : 'warn')
    : 'ok';
  return {
    daysLeft,
    total: 90,
    until: membership.end_date ?? '—',
    label: membership.plan_name_snapshot ?? 'Абонемент',
    tone,
  };
}

export const ProfileScreen = ({ tweaks, setTweak, onOpenPlans, onOpenReferral, onOpenGymInfo, onOpenPersonalData, onOpenCard, onOpenFAQ, onOpenVisitHistory, onOpenTrainingHistory }) => {
  const [tab, setTab] = React.useState('visits');

  const { data: homeData } = useClientHome();

  // Use real API sub data when available; fall back to tweaks for demo mode.
  const sub = homeData?.membership
    ? toSubInfo(homeData.membership)
    : getSubInfo(tweaks.subState);

  const isEmpty = tweaks.dataMode === 'empty';
  const userName = tweaks.userName || 'Саша';
  const subTone = sub.tone === 'ok' ? 'chip-accent' : sub.tone === 'warn' ? 'chip-warn' : 'chip-danger';

  return (
    <div className="page">
      <StatusBar />
      <div className="scroller" style={{ paddingTop: 54 }}>
        <div style={{ padding: '8px 20px 16px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)' }}>Профиль</div>
        </div>

        {/* Profile card */}
        <div style={{ padding: '0 16px 16px' }}>
          <div className="card" style={{ padding: 18 }}>
            <div className="row" style={{ gap: 14 }}>
              <Avatar initials={userName.slice(0, 1).toUpperCase()} bg="var(--avatar-bg)" color="var(--avatar-fg)" size={64} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="t-h1" style={{ fontSize: 22 }}>{userName} Морозов</div>
                <div className="t-small" style={{ marginTop: 2 }}>+7 (916) 482-09-14</div>
                <div className="t-small">sasha@example.com</div>
              </div>
            </div>

            <div style={{ marginTop: 18, padding: 14, background: 'var(--surface-2)', borderRadius: 14 }}>
              <div className="row-between" style={{ alignItems: 'center' }}>
                <span className={`chip ${subTone}`} style={{ height: 22, padding: '0 9px', fontSize: 11.5 }}>
                  {sub.label}
                </span>
                <span className="t-mini" style={{ color: 'var(--text-3)', letterSpacing: 0.3 }}>
                  С НАМИ 2 ГОДА
                </span>
              </div>

              <div className="row" style={{ alignItems: 'baseline', gap: 6, marginTop: 10 }}>
                <span className="t-h1 t-num" style={{ fontSize: 32, lineHeight: 1 }}>{sub.daysLeft}</span>
                <span className="t-small" style={{ color: 'var(--text-2)' }}>
                  {sub.daysLeft === 0
                    ? `истёк ${sub.until}`
                    : `${sub.daysLeft === 1 ? 'день' : sub.daysLeft < 5 ? 'дня' : 'дней'} до ${sub.until}`}
                </span>
              </div>

              {/* Progress bar — days used vs total */}
              <div style={{
                marginTop: 10, height: 4, borderRadius: 999,
                background: 'var(--border)', overflow: 'hidden',
              }}>
                <div style={{
                  height: '100%',
                  width: `${Math.max(4, Math.min(100, (sub.daysLeft / sub.total) * 100))}%`,
                  background: sub.tone === 'ok' ? 'var(--accent)'
                            : sub.tone === 'warn' ? 'var(--warn)'
                            : 'var(--danger)',
                  borderRadius: 999, transition: 'width 0.4s ease',
                }} />
              </div>

              {/* Renewal / status line */}
              <div className="row-between" style={{ marginTop: 10, alignItems: 'center', gap: 8 }}>
                <div className="t-small" style={{ color: 'var(--text-3)' }}>
                  {sub.tone === 'ok'
                    ? <>Автопродление <span style={{ color: 'var(--text-2)', fontWeight: 600 }}>{sub.until} · 42 000 ₽</span></>
                    : sub.tone === 'warn'
                    ? <>Спишем <span style={{ color: 'var(--text-2)', fontWeight: 600 }}>{sub.until} · 4 900 ₽</span></>
                    : <>Карта •••• 4821</>}
                </div>
              </div>

              {/* Actions — split into freeze + change */}
              <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
                {sub.tone === 'ok' && (
                  <button
                    onClick={() => window.__openSubManage?.('freeze')}
                    className="press" style={{
                      flex: 1, height: 38, borderRadius: 999, cursor: 'pointer',
                      background: 'transparent', color: 'var(--text-2)',
                      border: '0.5px solid var(--border-strong)',
                      fontFamily: 'inherit', fontSize: 13.5, fontWeight: 600,
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                    }}>
                    <Icon name="sparkle" size={14} color="currentColor" strokeWidth={2} />
                    Заморозить
                  </button>
                )}
                <button
                  onClick={onOpenPlans}
                  className="press" style={{
                    flex: 1, height: 38, borderRadius: 999, cursor: 'pointer',
                    background: sub.tone === 'ok' ? 'var(--text)' : 'var(--accent)',
                    color: sub.tone === 'ok' ? 'var(--bg)' : '#06120c',
                    border: 0, fontFamily: 'inherit', fontSize: 13.5, fontWeight: 600,
                  }}>
                  {sub.tone === 'ok' ? 'Сменить тариф' : 'Продлить'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Quick actions — pulled out of Settings so they don't get buried */}
        <div style={{
          padding: '0 16px 16px',
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10,
        }}>
          <button onClick={onOpenReferral} className="press" style={{
            appearance: 'none', border: 0, cursor: 'pointer',
            background: 'var(--accent)',
            borderRadius: 'var(--r-lg)', padding: '14px 14px',
            textAlign: 'left', fontFamily: 'inherit',
            color: '#06120c',
            display: 'flex', flexDirection: 'column', gap: 6,
            position: 'relative', overflow: 'hidden',
          }}>
            <div style={{
              position: 'absolute', right: -10, top: -10,
              width: 64, height: 64, borderRadius: '50%',
              background: 'rgba(255,255,255,0.22)',
              pointerEvents: 'none',
            }} />
            <div style={{
              width: 32, height: 32, borderRadius: 10,
              background: 'rgba(6,18,12,0.12)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              position: 'relative',
            }}>
              <Icon name="users" size={18} color="#06120c" strokeWidth={2} />
            </div>
            <div className="t-h3" style={{ fontSize: 14, color: '#06120c', position: 'relative' }}>
              Приведи друга
            </div>
            <div className="t-small" style={{ color: '#06120c', opacity: 0.75, fontSize: 12, position: 'relative' }}>
              −1 000 ₽ вам обоим
            </div>
          </button>

          <button onClick={onOpenGymInfo} className="press" style={{
            appearance: 'none', cursor: 'pointer',
            background: 'var(--surface)',
            border: '0.5px solid var(--border)',
            borderRadius: 'var(--r-lg)', padding: '14px 14px',
            textAlign: 'left', fontFamily: 'inherit',
            color: 'var(--text)',
            display: 'flex', flexDirection: 'column', gap: 6,
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 10,
              background: 'var(--surface-2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon name="mapPin" size={18} color="var(--text)" strokeWidth={2} />
            </div>
            <div className="t-h3" style={{ fontSize: 14 }}>
              О зале
            </div>
            <div className="t-small" style={{ fontSize: 12 }}>
              Адрес, часы, правила
            </div>
          </button>
        </div>

        {/* History tabs — underline style, handles long Russian labels */}
        <div className="profile-tabs">
          {[
            { id: 'visits', label: 'Визиты' },
            { id: 'trainings', label: 'Тренировки' },
            { id: 'purchases', label: 'Покупки' },
            { id: 'settings', label: 'Настройки' },
          ].map(t => (
            <button
              key={t.id}
              className={`profile-tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'visits' && <VisitsList isEmpty={isEmpty} onOpenAll={onOpenVisitHistory} />}
        {tab === 'trainings' && <TrainingsList isEmpty={isEmpty} onOpenAll={onOpenTrainingHistory} />}
        {tab === 'purchases' && <PurchasesList onOpenPlans={onOpenPlans} isEmpty={isEmpty} />}
        {tab === 'settings' && <SettingsList tweaks={tweaks} setTweak={setTweak} onOpenPlans={onOpenPlans} onOpenReferral={onOpenReferral} onOpenGymInfo={onOpenGymInfo} onOpenPersonalData={onOpenPersonalData} onOpenCard={onOpenCard} onOpenFAQ={onOpenFAQ} />}

        <div style={{ height: 24 }} />
      </div>
    </div>
  );
};

// ─── Visit history tab — real data from useClientVisitHistory ─────────────
function VisitsList({ isEmpty, onOpenAll }) {
  const { data, isLoading, isError, refetch } = useClientVisitHistory(1);

  if (isEmpty) {
    return (
      <div style={{ padding: '8px 16px' }}>
        <div className="card" style={{ padding: 0 }}>
          <EmptyState
            illustration="visits"
            title="Ещё не было визитов"
            body="Покажем дату и продолжительность каждого посещения после первого входа по QR."
          />
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '24px' }}>
        <div className="ptr-spin" style={{ width: 24, height: 24, borderWidth: 2 }} />
      </div>
    );
  }

  if (isError) {
    return (
      <LoadError variant="inline" title="Не удалось загрузить визиты" onRetry={() => refetch()} />
    );
  }

  const items = data?.items ?? [];

  if (items.length === 0) {
    return (
      <div style={{ padding: '8px 16px' }}>
        <div className="card" style={{ padding: 0 }}>
          <EmptyState
            illustration="visits"
            title="Ещё не было визитов"
            body="Покажем дату и продолжительность каждого посещения после первого входа по QR."
          />
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '8px 16px' }}>
      <div className="row-between" style={{ padding: '4px 4px 12px' }}>
        <div className="t-mini" style={{ color: 'var(--text-3)' }}>Последние визиты</div>
        <div className="t-small"><b style={{ color: 'var(--text)' }}>{data?.total ?? items.length}</b> посещений</div>
      </div>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {items.slice(0, 4).map((v, i) => (
          <React.Fragment key={String(v.id)}>
            {i > 0 && <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 56 }} />}
            <div style={{ padding: '12px 14px', display: 'flex', gap: 12, alignItems: 'center' }}>
              <div style={{
                width: 32, height: 32, borderRadius: 999,
                background: 'var(--surface-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon name="check" size={16} color="var(--text-2)" strokeWidth={2.2} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="t-h3" style={{ fontSize: 15 }}>
                  {v.gym_date
                    ? new Date(v.gym_date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', timeZone: 'Europe/Moscow' })
                    : '—'}
                </div>
                <div className="t-small" style={{ marginTop: 1 }}>
                  вход в {v.checked_in_at
                    ? new Date(v.checked_in_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' })
                    : '—'}
                </div>
              </div>
            </div>
          </React.Fragment>
        ))}
      </div>
      {onOpenAll && (
        <button onClick={onOpenAll} className="press" style={{
          width: '100%', marginTop: 10, border: 0,
          background: 'transparent', color: 'var(--accent-deep)',
          fontSize: 14, fontWeight: 600, fontFamily: 'inherit',
          padding: '10px', cursor: 'pointer', display: 'flex',
          alignItems: 'center', justifyContent: 'center', gap: 6,
        }}>
          Все посещения · {data?.total ?? items.length}
          <Icon name="arrowRight" size={14} color="var(--accent-deep)" strokeWidth={2} />
        </button>
      )}
    </div>
  );
}

// ─── Training history tab — real data from useClientPtHistory ──────────────
function TrainingsList({ isEmpty, onOpenAll }) {
  const { data, isLoading, isError, refetch } = useClientPtHistory(1);

  if (isEmpty) {
    return (
      <div style={{ padding: '8px 16px' }}>
        <div className="card" style={{ padding: 0 }}>
          <EmptyState
            illustration="dumbbell"
            title="История тренировок пуста"
            body="Запишись к тренеру — здесь будут заметки после занятий."
          />
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '24px' }}>
        <div className="ptr-spin" style={{ width: 24, height: 24, borderWidth: 2 }} />
      </div>
    );
  }

  if (isError) {
    return (
      <LoadError variant="inline" title="Не удалось загрузить тренировки" onRetry={() => refetch()} />
    );
  }

  const items = data?.items ?? [];

  if (items.length === 0) {
    return (
      <div style={{ padding: '8px 16px' }}>
        <div className="card" style={{ padding: 0 }}>
          <EmptyState
            illustration="dumbbell"
            title="История тренировок пуста"
            body="Запишись к тренеру — здесь будут заметки после занятий."
          />
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '8px 16px' }}>
      <div className="row-between" style={{ padding: '4px 4px 12px' }}>
        <div className="t-mini" style={{ color: 'var(--text-3)' }}>Всего тренировок</div>
        <div className="t-small"><b style={{ color: 'var(--text)' }}>{data?.total ?? items.length}</b> с тренерами</div>
      </div>
      <div className="stack-2">
        {items.slice(0, 3).map(t => (
          <div key={String(t.id)} className="card" style={{ padding: 14, display: 'flex', gap: 12 }}>
            <Avatar initials="Т" bg="var(--surface-2)" color="var(--text-2)" size={40} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="row-between">
                <div className="t-h3" style={{ fontSize: 15 }}>{t.trainer_name_snapshot ?? 'Тренер'}</div>
                <div className="t-small" style={{ color: 'var(--text-3)' }}>
                  {t.performed_at
                    ? new Date(t.performed_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', timeZone: 'Europe/Moscow' })
                    : '—'}
                </div>
              </div>
              {t.cancelled_at && (
                <div className="t-small" style={{ marginTop: 2, color: 'var(--danger)' }}>Отменена</div>
              )}
            </div>
          </div>
        ))}
      </div>
      {onOpenAll && (data?.total ?? items.length) > 3 && (
        <button onClick={onOpenAll} className="press" style={{
          width: '100%', marginTop: 10, border: 0,
          background: 'transparent', color: 'var(--accent-deep)',
          fontSize: 14, fontWeight: 600, fontFamily: 'inherit',
          padding: '10px', cursor: 'pointer', display: 'flex',
          alignItems: 'center', justifyContent: 'center', gap: 6,
        }}>
          Все тренировки · {data?.total ?? items.length}
          <Icon name="arrowRight" size={14} color="var(--accent-deep)" strokeWidth={2} />
        </button>
      )}
    </div>
  );
}

function SettingsList({ tweaks, setTweak, onOpenPlans, onOpenReferral, onOpenGymInfo, onOpenPersonalData, onOpenCard, onOpenFAQ }) {
  const { logout } = useAuth();
  const [notif, setNotif] = React.useState({ promo: true, schedule: true, trainer: true, sound: false });
  return (
    <div style={{ padding: '8px 16px' }}>
      <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>Внешний вид</div>
      <div className="card" style={{ padding: 4 }}>
        <div style={{ padding: '14px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ flex: 1 }} className="t-h3">Тема</div>
          <div className="seg" style={{ padding: 3 }}>
            <button
              className={`seg-item ${(tweaks.theme || 'light') === 'light' ? 'active' : ''}`}
              onClick={() => setTweak('theme', 'light')}
              style={{ padding: '0 14px' }}
            >
              Светлая
            </button>
            <button
              className={`seg-item ${tweaks.theme === 'dark' ? 'active' : ''}`}
              onClick={() => setTweak('theme', 'dark')}
              style={{ padding: '0 14px' }}
            >
              Тёмная
            </button>
          </div>
        </div>
      </div>

      <div className="t-mini" style={{ color: 'var(--text-3)', padding: '20px 4px 8px' }}>Уведомления</div>
      <div className="card" style={{ padding: 4 }}>
        <SettingRow label="Акции и скидки" value={notif.promo} onChange={v => setNotif(n => ({ ...n, promo: v }))} />
        <Divider2 />
        <SettingRow label="Изменения расписания" value={notif.schedule} onChange={v => setNotif(n => ({ ...n, schedule: v }))} />
        <Divider2 />
        <SettingRow label="Сообщения от тренера" value={notif.trainer} onChange={v => setNotif(n => ({ ...n, trainer: v }))} />
        <Divider2 />
        <SettingRow label="Звук уведомлений" value={notif.sound} onChange={v => setNotif(n => ({ ...n, sound: v }))} />
      </div>

      <div className="t-mini" style={{ color: 'var(--text-3)', padding: '20px 4px 8px' }}>Аккаунт</div>
      <div className="card" style={{ padding: 4 }}>
        <NavRow label="Тариф и подписка" value="Изменить" onClick={onOpenPlans} />
        <Divider2 />
        <NavRow label="Привязанная карта" value="•••• 4821" onClick={onOpenCard} />
        <Divider2 />
        <NavRow label="Личные данные" onClick={onOpenPersonalData} />
        <Divider2 />
        <NavRow label="Помощь и FAQ" onClick={onOpenFAQ} />
      </div>

      <div style={{ marginTop: 20 }}>
        <button
          className="btn"
          onClick={() => { void logout() }}
          style={{
            width: '100%', height: 50, background: 'transparent',
            color: 'var(--danger)', border: '0.5px solid var(--border-strong)',
          }}
        >
          <Icon name="logout" size={18} color="var(--danger)" strokeWidth={2} />
          Выйти из аккаунта
        </button>
      </div>

      <div className="t-small" style={{ textAlign: 'center', color: 'var(--text-3)', marginTop: 16 }}>
        Версия 2.4.1 · Мой зал
      </div>
    </div>
  );
}

function SettingRow({ label, value, onChange }) {
  return (
    <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ flex: 1 }} className="t-h3">{label}</div>
      <button onClick={() => onChange(!value)} style={{
        width: 44, height: 26, borderRadius: 999, border: 0, padding: 0,
        background: value ? 'var(--accent)' : 'var(--border-strong)',
        cursor: 'pointer', position: 'relative',
        transition: 'background 0.15s',
      }}>
        <span style={{
          position: 'absolute', top: 2, left: value ? 20 : 2,
          width: 22, height: 22, borderRadius: 999, background: '#fff',
          boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
          transition: 'left 0.18s ease',
        }} />
      </button>
    </div>
  );
}

function NavRow({ label, value, onClick }) {
  return (
    <div onClick={onClick} style={{ padding: '14px 14px', display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
      <div style={{ flex: 1 }} className="t-h3">{label}</div>
      {value && <div className="t-small" style={{ color: 'var(--text-2)' }}>{value}</div>}
      <Icon name="chevronRight" size={16} color="var(--text-3)" />
    </div>
  );
}

function Divider2() {
  return <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 14 }} />;
}

// ─── Purchases tab — real data from useClientPaymentHistory ───────────────
function PurchasesList({ onOpenPlans, isEmpty }) {
  const { data, isLoading, isError, refetch } = useClientPaymentHistory(1);

  if (isEmpty) {
    return (
      <div style={{ padding: '8px 16px' }}>
        <div className="card" style={{ padding: 0 }}>
          <EmptyState
            illustration="card"
            title="Покупок пока нет"
            body="Здесь появятся оплаты — абонемент, тренер, магазин."
            cta="Посмотреть тарифы"
            onCta={onOpenPlans}
          />
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '24px' }}>
        <div className="ptr-spin" style={{ width: 24, height: 24, borderWidth: 2 }} />
      </div>
    );
  }

  if (isError) {
    return (
      <LoadError variant="inline" title="Не удалось загрузить покупки" onRetry={() => refetch()} />
    );
  }

  const items = data?.items ?? [];

  if (items.length === 0) {
    return (
      <div style={{ padding: '8px 16px' }}>
        <div className="card" style={{ padding: 0 }}>
          <EmptyState
            illustration="card"
            title="Покупок пока нет"
            body="Здесь появятся оплаты — абонемент, тренер, магазин."
            cta="Посмотреть тарифы"
            onCta={onOpenPlans}
          />
        </div>
      </div>
    );
  }

  // total in kopecks (sum of positive amounts only)
  const totalKopecks = items
    .filter(p => p.amount_kopecks > 0)
    .reduce((s, p) => s + p.amount_kopecks, 0);

  const total = totalKopecks / 100;

  return (
    <div style={{ padding: '8px 16px' }}>
      {/* Summary card */}
      <div className="card" style={{ padding: 18, marginBottom: 12 }}>
        <div className="row-between" style={{ alignItems: 'flex-start' }}>
          <div>
            <div className="t-mini" style={{ color: 'var(--text-3)' }}>Потрачено всего</div>
            <div className="t-display t-num" style={{
              marginTop: 6, fontSize: 30, letterSpacing: -0.6, lineHeight: 1,
            }}>
              {total.toLocaleString('ru-RU')} ₽
            </div>
          </div>
          <button onClick={onOpenPlans} style={{
            appearance: 'none', background: 'transparent', border: 0,
            color: 'var(--accent-deep)', fontFamily: 'inherit',
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 2,
            padding: '6px 0', marginTop: 2,
          }}>
            Тарифы
            <Icon name="chevronRight" size={14} color="var(--accent-deep)" strokeWidth={2.2} />
          </button>
        </div>
      </div>

      {/* Payment list */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {items.slice(0, 10).map((p, i) => (
          <React.Fragment key={String(p.id)}>
            {i > 0 && <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 56 }} />}
            <PurchaseRow p={p} />
          </React.Fragment>
        ))}
      </div>

      {(data?.total ?? items.length) > items.length && (
        <div className="t-small" style={{ textAlign: 'center', color: 'var(--text-3)', marginTop: 10 }}>
          Показано {items.length} из {data?.total ?? items.length}
        </div>
      )}
    </div>
  );
}

// ─── Single payment row — adapts API ClientPaymentItem shape ──────────────
// API: { id, subject_kind, amount_kopecks (signed), method, received_at }
function PurchaseRow({ p }) {
  const isRefund = p.amount_kopecks < 0;
  const amountRub = Math.abs(p.amount_kopecks) / 100;
  const iconName = p.subject_kind === 'membership' ? 'card'
    : p.subject_kind === 'pt_package' ? 'user'
    : isRefund ? 'tag'
    : 'card';
  const title = p.subject_kind === 'membership' ? 'Абонемент'
    : p.subject_kind === 'pt_package' ? 'Персональные тренировки'
    : isRefund ? 'Возврат'
    : 'Оплата';
  const dateStr = p.received_at
    ? new Date(p.received_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', timeZone: 'Europe/Moscow' })
    : '—';
  const methodLabel = p.method === 'online' ? 'онлайн' : p.method === 'cash' ? 'наличные' : p.method ?? '';

  return (
    <div style={{ padding: '12px 14px', display: 'flex', gap: 12, alignItems: 'center' }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: isRefund ? 'var(--warn-soft)' : 'var(--surface-2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon name={iconName} size={16}
              color={isRefund ? '#a36a16' : 'var(--text-2)'} strokeWidth={2} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-h3" style={{ fontSize: 14 }}>{title}</div>
        <div className="t-small" style={{ marginTop: 1, fontSize: 12, color: 'var(--text-3)' }}>
          {dateStr} · {methodLabel}
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div className="t-h3 t-num" style={{
          fontSize: 14,
          color: isRefund ? '#a36a16' : 'var(--text)',
        }}>
          {isRefund ? '+' : '−'}{amountRub.toLocaleString('ru-RU')} ₽
        </div>
        <div className="t-mini" style={{ fontSize: 9.5, color: 'var(--text-3)' }}>
          {isRefund ? 'возврат' : 'оплачено'}
        </div>
      </div>
    </div>
  );
}
