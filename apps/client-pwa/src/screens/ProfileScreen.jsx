import React from 'react';
import { Avatar } from '@/components/Avatar.jsx';
import { EmptyState } from '@/components/EmptyState.jsx';
import { LoadError } from '@/components/LoadError.jsx';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import {
  useClientHome,
  useClientMe,
  useClientVisitHistory,
  useClientPtHistory,
  useClientPaymentHistory,
} from '@/data';

// ─── Deferred-feature scaffolding (BUILT, HIDDEN) ─────────────────────────
// Flip a flag to true when the corresponding backend data lands.
//
//  • weeklyActivity — activity bars card (needs workout minutes/type per day)
//  • tenureBadge    — "PREMIUM · N ЛЕТ" badge (needs tier + tenure from API)
//  • weeksStat      — third stat strip cell "N недель" (needs tenure data)
//  • linkedCard     — "Привязанная карта •••• 4821" row in Settings (needs card-on-file)
const PROFILE_FEATURE_FLAGS = {
  weeklyActivity: false,
  tenureBadge:    false,
  weeksStat:      false,
  linkedCard:     false,
};

// ─── In-file adapter: API membership shape → subInfo render shape ─────────
// Mirrors the adapter in HomeScreen.jsx
export function toSubInfo(membership) {
  if (!membership) {
    return { daysLeft: 0, total: 0, until: '—', label: 'Нет абонемента', tone: 'danger' };
  }
  const daysLeft = Math.max(0, membership.daysUntilEnd ?? 0);
  const tone = membership.expiringSoon
    ? (daysLeft === 0 ? 'danger' : 'warn')
    : 'ok';
  return {
    daysLeft,
    // WR-03: derive the real plan duration from startDate/endDate instead of
    // a hardcoded 90 so the progress bar reflects the actual membership length.
    total: subTotalDays(membership.startDate, membership.endDate),
    until: membership.endDate ?? '—',
    label: membership.planNameSnapshot ?? 'Абонемент',
    tone,
  };
}

// WR-03: whole-day span between two ISO date-only strings (YYYY-MM-DD).
// Parses as UTC midnight to avoid the DST risk of new Date(dateOnlyString)
// (CLAUDE.md domain convention). Returns 0 if either bound is missing/invalid.
function subTotalDays(startDate, endDate) {
  if (!startDate || !endDate) return 0;
  const start = Date.parse(`${startDate}T00:00:00Z`);
  const end = Date.parse(`${endDate}T00:00:00Z`);
  if (Number.isNaN(start) || Number.isNaN(end)) return 0;
  return Math.max(0, Math.round((end - start) / 86_400_000));
}

// ─── Count-up animation hook ───────────────────────────────────────────────
function useCountUp(target) {
  const [value, setValue] = React.useState(0);
  React.useEffect(() => {
    if (!target) { setValue(0); return; }
    const dur = 900;
    const startTime = performance.now();
    let raf;
    function tick(t) {
      const p = Math.min(1, (t - startTime) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(Math.round(target * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
      else setValue(target);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return value;
}

export const ProfileScreen = ({ tweaks, onOpenSettings, onOpenPlans, onOpenReferral, onOpenGymInfo, onOpenVisitHistory, onOpenTrainingHistory }) => {
  const [tab, setTab] = React.useState('visits');

  const { data: homeData } = useClientHome();
  const { data: me } = useClientMe();
  const { data: visitData } = useClientVisitHistory(1);
  const { data: ptData } = useClientPtHistory(1);

  // Real membership from /client/home; null → genuine "Нет абонемента" empty state.
  const sub = toSubInfo(homeData?.membership ?? null);

  const isEmpty = tweaks.dataMode === 'empty';
  // Real /client/me identity (graceful blanks when absent); tweaks.userName is a
  // dev-panel override only, never a hardcoded human name default.
  const fullName = `${me?.firstName ?? ''} ${me?.lastName ?? ''}`.trim();
  const displayName = me?.firstName || tweaks.userName || '';

  // Elapsed days = total − daysLeft (how many days have passed in this membership period)
  const elapsedDays = Math.max(0, sub.total - sub.daysLeft);
  // Progress bar: elapsed portion
  const progressPct = sub.total > 0 ? Math.max(4, Math.min(100, (elapsedDays / sub.total) * 100)) : 0;

  return (
    <div className="page">
      <StatusBar />
      <div className="scroller" style={{ paddingTop: 54 }}>
        <div style={{ padding: '4px 16px 16px' }}>
          {/* Identity card */}
          <div className="card fade-up" style={{ padding: 16 }}>
            <div className="row" style={{ gap: 14, alignItems: 'center' }}>
              <Avatar initials={displayName.slice(0, 1).toUpperCase()} bg="var(--avatar-bg)" color="var(--avatar-fg)" size={62} />
              <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 7 }}>
                <div style={{ fontSize: 22, fontWeight: 750, letterSpacing: '-0.5px', lineHeight: 1.05 }}>
                  {fullName || displayName || '—'}
                </div>
                {/* BUILT, HIDDEN: tenure badge — needs tier + tenure data from API */}
                {PROFILE_FEATURE_FLAGS.tenureBadge && (
                  <span style={{
                    alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center',
                    gap: 5, height: 22, padding: '0 9px 0 8px', borderRadius: 999,
                    background: 'color-mix(in oklab, var(--accent) 18%, transparent)',
                    color: 'var(--accent-deep)', fontSize: 10.5, fontWeight: 700, letterSpacing: 0.5,
                  }}>
                    <Icon name="sparkle" size={11} color="var(--accent-deep)" strokeWidth={0} />
                    PREMIUM · N ЛЕТ
                  </span>
                )}
              </div>
              {/* Gear button → /settings (D-74-01) */}
              <button
                onClick={onOpenSettings}
                aria-label="Настройки"
                className="press"
                style={{
                  flexShrink: 0, width: 38, height: 38, borderRadius: 999, padding: 0,
                  cursor: 'pointer', background: 'var(--surface-2)',
                  border: '0.5px solid var(--border-strong)',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                }}
              >
                <Icon name="settings" size={19} color="var(--text)" strokeWidth={2} />
              </button>
            </div>
          </div>
        </div>

        {/* Membership hero — pass-style contrast-flip via .membership-hero CSS class (D-74-03) */}
        {/* Shows ONLY API-backed fields: daysLeft, elapsedDays, total, until, label */}
        {/* Price/auto-renew block deliberately omitted — not in /client/membership API */}
        <div style={{ padding: '0 16px 18px' }}>
          <div className="card fade-up membership-hero" style={{ position: 'relative', overflow: 'hidden', padding: 16, isolation: 'isolate' }}>
            {/* Header row: label dot + plan name chip */}
            <div className="row-between" style={{ position: 'relative', alignItems: 'center' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
                <span style={{ width: 7, height: 7, borderRadius: 2, background: 'var(--mh-accent)' }} />
                <span className="t-mini" style={{ color: 'var(--mh-text-3)', letterSpacing: 1 }}>Абонемент</span>
              </span>
              <span style={{
                display: 'inline-flex', alignItems: 'center', height: 23, padding: '0 11px',
                borderRadius: 999, fontSize: 11, fontWeight: 700, letterSpacing: 0.3,
                background: 'var(--mh-chip-bg)', color: 'var(--mh-chip-fg)',
                border: '0.5px solid var(--mh-chip-border)',
              }}>
                {sub.label}
              </span>
            </div>

            {/* Days left — large number */}
            <div style={{ position: 'relative', marginTop: 13, display: 'flex', alignItems: 'flex-end', gap: 10 }}>
              <span className="t-num" style={{ fontSize: 46, fontWeight: 800, letterSpacing: -2.5, lineHeight: 0.8, color: 'var(--mh-text)' }}>
                {sub.daysLeft}
              </span>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--mh-text-2)', paddingBottom: 5, lineHeight: 1.2 }}>
                {sub.daysLeft === 1 ? 'день до' : sub.daysLeft < 5 && sub.daysLeft > 0 ? 'дня до' : 'дней до'}
                <br />продления
              </span>
            </div>

            {/* Progress bar (elapsed / total) + caption */}
            <div style={{ position: 'relative', marginTop: 13 }}>
              <div style={{ height: 6, borderRadius: 999, background: 'var(--mh-track)', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${progressPct}%`, borderRadius: 999,
                  background: 'var(--mh-accent)',
                  transition: 'width 0.9s cubic-bezier(0.32,0.72,0.2,1)',
                }} />
              </div>
              <div className="row-between" style={{ marginTop: 7 }}>
                <span style={{ fontSize: 11, color: 'var(--mh-text-3)' }}>
                  {sub.total > 0 ? `Пройдено ${elapsedDays} ${elapsedDays === 1 ? 'день' : elapsedDays < 5 ? 'дня' : 'дней'}` : 'Нет абонемента'}
                </span>
                <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--mh-accent)' }}>
                  {sub.total > 0 ? `До ${sub.until}` : ''}
                </span>
              </div>
            </div>

            {/* Action buttons: Freeze (active only) + Change/Extend */}
            <div style={{ position: 'relative', marginTop: 14, display: 'flex', gap: 8 }}>
              {sub.tone === 'ok' && (
                <button
                  onClick={() => window.__openSubManage?.('freeze')}
                  className="press"
                  style={{
                    flex: 1, height: 40, borderRadius: 999, cursor: 'pointer',
                    background: 'var(--mh-ghost-bg)', color: 'var(--mh-text)',
                    border: '0.5px solid var(--mh-ghost-border)',
                    fontFamily: 'inherit', fontSize: 13.5, fontWeight: 600,
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  }}
                >
                  <Icon name="sparkle" size={14} color="currentColor" strokeWidth={1.4} />
                  Заморозить
                </button>
              )}
              <button
                onClick={onOpenPlans}
                className="press"
                style={{
                  flex: 1, height: 40, borderRadius: 999, cursor: 'pointer',
                  background: 'var(--mh-cta-bg)', color: 'var(--mh-cta-fg)',
                  border: 0, fontFamily: 'inherit', fontSize: 13.5, fontWeight: 700,
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                }}
              >
                {sub.tone === 'ok' ? 'Сменить тариф' : 'Продлить'}
              </button>
            </div>
          </div>
        </div>

        {/* Stat strip — 2 API-backed cells + optional gated 3rd (D-74-04) */}
        <div style={{ padding: '0 16px 18px' }}>
          <div className="card" style={{ padding: 4, display: 'flex', overflow: 'hidden' }}>
            <StatCell label="визитов" value={visitData?.total ?? 0} />
            <div style={{ width: 0.5, alignSelf: 'stretch', margin: '11px 0', background: 'var(--border)' }} />
            <StatCell label="тренировки" value={ptData?.total ?? 0} />
            {/* BUILT, HIDDEN: third stat "N недель" — needs tenure data from API */}
            {PROFILE_FEATURE_FLAGS.weeksStat && (
              <>
                <div style={{ width: 0.5, alignSelf: 'stretch', margin: '11px 0', background: 'var(--border)' }} />
                <StatCell label="недель" value={0} />
              </>
            )}
          </div>
        </div>

        {/* BUILT, HIDDEN: weekly activity card — needs workout minutes/type per day from API */}
        {PROFILE_FEATURE_FLAGS.weeklyActivity && (
          <div style={{ padding: '0 16px 18px' }}>
            <div className="card fade-up" style={{ padding: 14 }}>
              <div className="row-between" style={{ alignItems: 'center' }}>
                <span className="t-mini" style={{ color: 'var(--text-3)' }}>Активность за неделю</span>
              </div>
              {/* Activity bars placeholder — wired when workout-minutes API lands */}
              <div style={{ height: 60, display: 'flex', alignItems: 'flex-end', gap: 7, marginTop: 12 }}>
                {['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].map(d => (
                  <div key={d} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7 }}>
                    <div style={{ width: '100%', height: 40, borderRadius: 6, background: 'var(--border-strong)' }} />
                    <span style={{ fontSize: 9.5, fontWeight: 500, color: 'var(--text-3)' }}>{d}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Quick action tiles */}
        <div style={{ padding: '0 16px 18px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {/* Referral tile — coupon style with dashed divider */}
          <button onClick={onOpenReferral} className="press" style={{
            appearance: 'none', border: 0, cursor: 'pointer',
            background: 'var(--accent)', borderRadius: 'var(--r-lg)', padding: '12px',
            textAlign: 'left', fontFamily: 'inherit', color: '#06120c',
            display: 'flex', alignItems: 'center', gap: 14,
            position: 'relative', overflow: 'hidden',
          }}>
            <span style={{ position: 'absolute', top: -7, left: 44, width: 14, height: 14, borderRadius: 999, background: 'var(--bg)', pointerEvents: 'none' }} />
            <span style={{ position: 'absolute', bottom: -7, left: 44, width: 14, height: 14, borderRadius: 999, background: 'var(--bg)', pointerEvents: 'none' }} />
            <span style={{ position: 'absolute', top: 6, bottom: 6, left: 51, width: 0, borderLeft: '2px dashed rgba(6,18,12,0.22)', pointerEvents: 'none' }} />
            <span style={{
              width: 32, height: 32, borderRadius: 10, flexShrink: 0,
              background: '#06120c',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon name="users" size={17} color="var(--accent)" strokeWidth={2} />
            </span>
            <div style={{ minWidth: 0 }}>
              <div className="t-num" style={{ fontSize: 18, fontWeight: 800, letterSpacing: -0.6, lineHeight: 1.05, color: '#06120c', whiteSpace: 'nowrap' }}>
                −1 000 ₽
              </div>
              <div style={{ fontSize: 11.5, fontWeight: 600, color: '#06120c', opacity: 0.74, marginTop: 2, whiteSpace: 'nowrap' }}>
                Приведи друга
              </div>
            </div>
          </button>

          {/* Gym info tile */}
          <button onClick={onOpenGymInfo} className="press" style={{
            appearance: 'none', cursor: 'pointer',
            background: 'var(--surface)', border: '0.5px solid var(--border)',
            borderRadius: 'var(--r-lg)', padding: '11px', textAlign: 'left',
            fontFamily: 'inherit', color: 'var(--text)',
            display: 'flex', alignItems: 'center', gap: 8,
            position: 'relative', overflow: 'hidden',
          }}>
            <span style={{
              width: 28, height: 28, borderRadius: 9, flexShrink: 0,
              background: 'var(--surface-2)', border: '0.5px solid var(--border)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon name="mapPin" size={15} color="var(--text-2)" strokeWidth={2} />
            </span>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="t-h3" style={{ fontSize: 15 }}>О зале</div>
              <div style={{ marginTop: 2, fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap' }}>
                <span style={{ color: 'var(--text-3)', fontWeight: 500 }}>Адрес, часы, правила</span>
              </div>
            </div>
          </button>
        </div>

        {/* History tabs — 3 tabs (Settings tab removed per D-74-01) */}
        <div className="profile-tabs">
          {[
            { id: 'visits',    label: 'Визиты' },
            { id: 'trainings', label: 'Тренировки' },
            { id: 'purchases', label: 'Покупки' },
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

        <div style={{ height: 24 }} />
      </div>
    </div>
  );
};

// ─── Stat cell — count-up animation on mount ──────────────────────────────
function StatCell({ label, value }) {
  const displayed = useCountUp(value);
  return (
    <button className="press" style={{
      flex: 1, minWidth: 0, padding: '9px 8px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
      border: 0, background: 'transparent', cursor: 'pointer', borderRadius: 14,
      fontFamily: 'inherit',
    }}>
      <span className="t-num" style={{ fontSize: 24, fontWeight: 750, letterSpacing: -1, lineHeight: 1, color: 'var(--text)' }}>
        {displayed}
      </span>
      <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-3)', whiteSpace: 'nowrap' }}>
        {label}
      </span>
    </button>
  );
}

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
                  {v.gymDate
                    ? new Date(v.gymDate).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', timeZone: 'Europe/Moscow' })
                    : '—'}
                </div>
                <div className="t-small" style={{ marginTop: 1 }}>
                  вход в {v.checkedInAt
                    ? new Date(v.checkedInAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' })
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
                <div className="t-h3" style={{ fontSize: 15 }}>{t.trainerNameSnapshot ?? 'Тренер'}</div>
                <div className="t-small" style={{ color: 'var(--text-3)' }}>
                  {t.performedAt
                    ? new Date(t.performedAt).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', timeZone: 'Europe/Moscow' })
                    : '—'}
                </div>
              </div>
              {t.cancelledAt && (
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
    .filter(p => p.amountKopecks > 0)
    .reduce((s, p) => s + p.amountKopecks, 0);

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
// API: { id, subjectKind, amountKopecks (signed), method, receivedAt }
function PurchaseRow({ p }) {
  const isRefund = p.amountKopecks < 0;
  const amountRub = Math.abs(p.amountKopecks) / 100;
  const iconName = p.subjectKind === 'membership' ? 'card'
    : p.subjectKind === 'pt_package' ? 'user'
    : isRefund ? 'tag'
    : 'card';
  const title = p.subjectKind === 'membership' ? 'Абонемент'
    : p.subjectKind === 'pt_package' ? 'Персональные тренировки'
    : isRefund ? 'Возврат'
    : 'Оплата';
  const dateStr = p.receivedAt
    ? new Date(p.receivedAt).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', timeZone: 'Europe/Moscow' })
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
