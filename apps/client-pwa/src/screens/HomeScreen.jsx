import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar } from '@/components/Avatar.jsx';
import { EmptyState } from '@/components/EmptyState.jsx';
import { LoadError } from '@/components/LoadError.jsx';
import { Icon } from '@/components/Icon.jsx';
import { PullToRefresh } from '@/components/PullToRefresh.jsx';
import { QRPattern } from '@/components/QRPattern.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { SwipeRow } from '@/components/SwipeRow.jsx';
import { useClientHome, useClientMe, useClientBookings } from '@/data';
import { formatCountdown, useCountdown } from '@/hooks/useCountdown.js';

// ─── In-file adapter: API membership shape → existing subInfo render shape ───
// API: ClientMembershipResponse { id, planNameSnapshot, startDate, endDate,
//       status, daysUntilEnd, expiringSoon } | null
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

// ─── deriveOnboardingSteps — Plan 999.3-02 (D-05/D-06) ──────────────────────
// Pure helper — exported for unit tests (HomeScreen.adapters.test.jsx).
// Computes step states from live /client/me + /client/home + /client/bookings.
//
// Each step.state: 'done' | 'next' | 'pending'
//   Step 1 Аккаунт  — always 'done'
//   Step 2 Абонемент — always 'next' (the single actionable step; D-06)
//   Step 3 Профиль   — 'done' iff onboarding is complete OR goal+height+weight are set
//   Step 4 Визит     — 'done' iff client has any booking
//
// Returns { steps, doneCount, title, badge }
// doneCount = steps where state === 'done' (the 'next' step is NOT counted)
export function deriveOnboardingSteps(me, homeData, bookings) {
  // WR-01 (Phase 999.5): /client/me exposes goal/heightCm/weightKg/onboardingCompletedAt.
  // Also accepts legacy birthday+gender fields (backward-compat with adapter tests).
  const profileDone = !!(
    me?.onboardingCompletedAt ||
    (me?.goal && me?.heightCm && me?.weightKg) ||
    (me?.birthday && me?.gender)
  )
  const visitDone = !!(
    (bookings?.total ?? 0) > 0 ||
    (bookings?.items?.length ?? 0) > 0 ||
    homeData?.nextBooking != null
  )

  const steps = [
    { key: 'account', label: 'Аккаунт',      meta: 'Создан',              state: 'done'               },
    { key: 'plan',    label: 'Абонемент',     meta: 'Не выбран',           state: 'next'               },
    { key: 'profile', label: 'Профиль',       meta: 'Цель, рост, вес',     state: profileDone ? 'done' : 'pending' },
    { key: 'visit',   label: 'Первый визит',  meta: '30 мин экскурсия',    state: visitDone   ? 'done' : 'pending' },
  ]

  const doneCount = steps.filter((s) => s.state === 'done').length
  const remaining = 4 - doneCount
  const badge = `${doneCount} / 4`
  const title = `Ещё ${remaining} шага до полного старта`

  return { steps, doneCount, title, badge }
}

// ─── Static demo-only data (tweaks-driven — TRAINER_CANCEL shown only when
//     tweaks.gymEvent === 'trainer-cancelled'; never from real API) ──────────
const DEMO_TRAINER_CANCEL = {
  trainer: 'Аня Соколова',
  initials: 'АС',
  bg: '#fef3c7',
  color: '#f59e0b',
  date: 'Сегодня, 18:00',
  reason: 'заболела',
  reasonFull: 'Аня приболела и не сможет провести тренировку сегодня.',
  refund: 2200,
};

// Open/closed status chip — shown in home header, opens GymInfoSheet
export function GymStatusPill({ onClick }) {
  // Gym status is not returned by the home API; show a neutral pill as placeholder.
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
        background: 'var(--text-3)',
        flexShrink: 0,
      }} />
      <span style={{
        fontSize: 12, fontWeight: 600, letterSpacing: -0.1,
        color: 'var(--text-2)', whiteSpace: 'nowrap',
        overflow: 'hidden', textOverflow: 'ellipsis',
      }}>
        О зале
      </span>
      <Icon name="chevronRight" size={12} color="var(--text-3)" strokeWidth={2.2} />
    </button>
  );
}

export const HomeScreen = ({ tweaks, onOpenQR, onOpenPlans, onOpenManage, onOpenReferral, onOpenGymInfo, onOpenNotifications, onTab, setTweak }) => {
  const { data: homeData, isLoading, isError, refetch } = useClientHome();
  const { data: me } = useClientMe();
  // useClientBookings: needed for Step 4 live derivation in the newbie gate (D-05/D-06)
  const { data: bookings } = useClientBookings();
  const navigate = useNavigate();

  // D-04/D-05 auto-redirect gate: newbie + empty profile + !onboardingCompletedAt → /onboarding
  // Fires once (replace: true so back-button doesn't bounce back into a completed questionnaire).
  // Conditions (all must be true to redirect):
  //   1. membershipState === 'newbie' (never fires for active/lapsed members)
  //   2. me is loaded AND !me.onboardingCompletedAt (flag is server-owned; once set, never re-fires)
  //   3. profile is empty: no goal, no heightCm, no weightKg, no non-trivial firstName
  // T-999.5-15 mitigation: precise condition + replace:true prevents redirect loop.
  React.useEffect(() => {
    if (
      homeData?.membershipState === 'newbie' &&
      me && !me.onboardingCompletedAt &&
      !me.goal && !me.heightCm && !me.weightKg
    ) {
      navigate('/onboarding', { replace: true });
    }
  }, [homeData, me, navigate]);

  // Real membership from /client/home; null → genuine "Нет абонемента" empty state
  // (toSubInfo(null)), never the demo getSubInfo fallback.
  const sub = toSubInfo(homeData?.membership ?? null);

  const variant = tweaks.homeVariant || 'classic';
  // Bind the greeting to the real /client/me principal; tweaks.userName is kept
  // only as a dev-panel override, never a hardcoded human name default.
  const userName = me?.firstName || tweaks.userName || '';
  const isEmpty = tweaks.dataMode === 'empty';
  const trainerCancelled = tweaks.gymEvent === 'trainer-cancelled';
  // Notifications count: not in API — use 0 when loaded, show no badge.
  const unread = 0;
  const [showToast, setShowToast] = React.useState(false);

  const greeting = (() => {
    const h = 9; // demo time
    if (h < 5) return 'Доброй ночи';
    if (h < 12) return 'Доброе утро';
    if (h < 18) return 'Привет';
    return 'Добрый вечер';
  })();

  if (isLoading) {
    return (
      <div className="page" style={{ background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="ptr-spin" style={{ width: 28, height: 28, borderWidth: 2 }} />
      </div>
    );
  }

  if (isError) {
    return <LoadError onRetry={() => refetch()} />;
  }

  const subTone = sub.tone === 'ok' ? 'chip-accent' : sub.tone === 'warn' ? 'chip-warn' : 'chip-danger';
  const fillTone = sub.tone === 'ok' ? '' : sub.tone === 'warn' ? 'warn' : 'danger';
  const pct = sub.total > 0 ? Math.max(2, Math.min(100, (sub.daysLeft / sub.total) * 100)) : 0;

  // Real nextBooking from API (or null)
  const nextBooking = homeData?.nextBooking ?? null;

  return (
    <div className="page" style={{ background: 'var(--bg)' }}>
      <StatusBar />
      <PullToRefresh
        scrollPaddingTop={54}
        onRefresh={() => {
          setShowToast(true);
          setTimeout(() => setShowToast(false), 2400);
          return refetch().then(() => undefined);
        }}
      >
        {showToast && <div className="ptr-toast">Обновлено · сейчас</div>}

        {/* Newbie render gate (D-01/D-02): keys on membershipState === 'newbie' ONLY.
            A lapsed member also has membership===null but must NOT see newbie copy.
            HomeNewbie owns its own Header as the first stagger child. */}
        {homeData?.membershipState === 'newbie' ? (
          <HomeNewbie
            me={me}
            homeData={homeData}
            bookings={bookings}
            userName={userName}
            greeting={greeting}
            onOpenPlans={onOpenPlans}
            onOpenGymInfo={onOpenGymInfo}
            onOpenNotifications={onOpenNotifications}
            onTab={onTab}
            onOpenOnboarding={() => navigate('/onboarding')}
          />
        ) : (
          <>
            {/* Header — shared across non-newbie variants */}
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
            {variant === 'classic' && <HomeClassic isEmpty={isEmpty} trainerCancelled={trainerCancelled} sub={sub} subTone={subTone} fillTone={fillTone} pct={pct} onOpenQR={onOpenQR} onOpenPlans={onOpenPlans} onOpenManage={onOpenManage} onOpenNotifications={onOpenNotifications} onTab={onTab} unread={unread} subCardStyle={tweaks.subCardStyle || 'eyebrow'} nextBooking={nextBooking} />}
            {variant === 'qr-hero' && <HomeQrHero isEmpty={isEmpty} trainerCancelled={trainerCancelled} sub={sub} subTone={subTone} fillTone={fillTone} pct={pct} onOpenQR={onOpenQR} onOpenPlans={onOpenPlans} onOpenManage={onOpenManage} onOpenNotifications={onOpenNotifications} onTab={onTab} unread={unread} nextBooking={nextBooking} />}
            {variant === 'minimal' && <HomeMinimal isEmpty={isEmpty} trainerCancelled={trainerCancelled} sub={sub} subTone={subTone} fillTone={fillTone} pct={pct} onOpenQR={onOpenQR} onOpenPlans={onOpenPlans} onOpenManage={onOpenManage} onOpenNotifications={onOpenNotifications} onTab={onTab} unread={unread} nextBooking={nextBooking} />}
          </>
        )}

        <div style={{ height: 24 }} />
      </PullToRefresh>
    </div>
  );
};

// ─── Newbie components — Plan 999.3-02 ──────────────────────────────────────

// Premium plan-card for newbie state — v2 mockup (Plan 260601-oan)
export function HeroNewbie({ onOpenPlans }) {
  const [sel, setSel] = React.useState(1) // default «Полгода» (index 1)
  const tariffs = [
    { label: 'Месяц', pop: false },
    { label: 'Полгода', pop: true },
    { label: 'Год', pop: false },
  ]
  return (
    <div style={{
      margin: '0 16px 14px',
      borderRadius: 28,
      background: 'var(--surface)',
      border: '0.5px solid var(--border)',
      boxShadow: '0 18px 44px rgba(28,25,23,0.13), 0 2px 6px rgba(28,25,23,0.05)',
      overflow: 'hidden',
    }}>
      {/* ── Colored top panel ── */}
      <div style={{
        position: 'relative', height: 134,
        background: 'var(--accent)', color: 'var(--on-accent)',
        overflow: 'hidden',
      }}>
        {/* Dot-grid brand pattern */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: 'radial-gradient(rgba(255,255,255,0.5) 1.4px, transparent 1.6px)',
          backgroundSize: '16px 16px',
          opacity: 0.4,
          WebkitMask: 'linear-gradient(105deg, #000 30%, transparent 78%)',
          mask: 'linear-gradient(105deg, #000 30%, transparent 78%)',
          pointerEvents: 'none',
        }} />
        {/* Decorative ring r2 (dashed, larger) */}
        <div style={{
          position: 'absolute', borderRadius: '50%',
          border: '1.5px dashed rgba(255,255,255,0.55)',
          right: -70, top: -78, width: 210, height: 210, opacity: 0.4,
          pointerEvents: 'none',
        }} />
        {/* Decorative ring r1 (solid) */}
        <div style={{
          position: 'absolute', borderRadius: '50%',
          border: '1.5px solid rgba(255,255,255,0.55)',
          right: -36, top: -46, width: 150, height: 150,
          pointerEvents: 'none',
        }} />
        {/* Floating chips */}
        <span style={{
          position: 'absolute', borderRadius: 4,
          background: 'rgba(255,255,255,0.85)',
          width: 9, height: 9, left: 150, top: 22,
          transform: 'rotate(16deg)',
          animation: 'spot-float 3.6s ease-in-out infinite',
        }} />
        <span style={{
          position: 'absolute', borderRadius: '50%',
          background: 'var(--on-accent)',
          width: 7, height: 7, left: 30, bottom: 50, opacity: 0.4,
          animation: 'spot-float 3.6s ease-in-out infinite',
          animationDelay: '0.7s',
        }} />
        {/* Eyebrow */}
        <div style={{
          position: 'absolute', left: 20, top: 18,
          display: 'inline-flex', alignItems: 'center', gap: 7,
          fontSize: 11, fontWeight: 700, letterSpacing: '0.6px', textTransform: 'uppercase',
          color: 'var(--on-accent)',
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--on-accent)',
            boxShadow: '0 0 0 4px rgba(255,255,255,0.3)',
            animation: 'pulse-soft 2.4s ease-in-out infinite',
            flexShrink: 0,
          }} />
          Аккаунт создан
        </div>
        {/* Kicker */}
        <div style={{
          position: 'absolute', left: 20, bottom: 16, right: 150,
          fontSize: 19, fontWeight: 750, letterSpacing: '-0.5px', lineHeight: 1.08,
          color: 'var(--on-accent)',
        }}>
          Время<br />тренироваться
        </div>
        {/* Membership-pass illustration */}
        <div
          aria-hidden="true"
          style={{
            position: 'absolute', right: 16, top: '50%',
            transform: 'translateY(-50%) rotate(-7deg)',
            width: 118, height: 82,
            background: 'var(--surface)',
            borderRadius: 15,
            boxShadow: '0 16px 30px rgba(16,24,52,0.3)',
            padding: '11px 12px',
            display: 'flex', flexDirection: 'column', gap: 8,
            animation: 'pass-in 0.55s cubic-bezier(0.32,1.5,0.36,1) both',
          }}
        >
          {/* Star badge */}
          <div style={{
            position: 'absolute', right: -9, top: -9,
            width: 30, height: 30, borderRadius: '50%',
            background: 'var(--text)', color: 'var(--accent)',
            border: '3px solid var(--accent)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon name="star" size={15} color="currentColor" strokeWidth={0} />
          </div>
          {/* Pass header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <div style={{
              width: 22, height: 22, borderRadius: 7,
              background: 'var(--text)', color: 'var(--accent)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}>
              <Icon name="barbell" size={14} color="currentColor" strokeWidth={2} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
              <i style={{ display: 'block', height: 4, borderRadius: 999, background: 'var(--border-strong)' }} />
              <i style={{ display: 'block', height: 4, width: '60%', borderRadius: 999, background: 'var(--border)' }} />
            </div>
          </div>
          {/* Pass bars */}
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 22, marginTop: 2 }}>
            {[100, 64, 82, 100, 64, 82, 100, 64, 82, 100].map((h, i) => (
              <i key={i} style={{
                flex: 1, borderRadius: 2, height: `${h}%`,
                background: 'var(--text)',
                opacity: i % 2 === 1 ? 0.4 : (i % 3 === 2 ? 0.88 : 0.88),
              }} />
            ))}
          </div>
        </div>
      </div>

      {/* ── Body ── */}
      <div style={{ padding: '18px 20px 20px' }}>
        <div style={{ fontSize: 25, fontWeight: 750, letterSpacing: '-0.7px', lineHeight: 1.08 }}>
          Выбери свой абонемент
        </div>
        <div style={{ marginTop: 8, fontSize: 13.5, lineHeight: 1.45, color: 'var(--text-2)', maxWidth: 290 }}>
          QR-пропуск активируется сразу после оплаты. Заморозка и смена тарифа — в любой момент.
        </div>

        {/* Tariff selector — visual only, no prices (D-LIVE) */}
        <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
          {tariffs.map((t, i) => {
            const isSel = sel === i
            const isPopSel = t.pop && isSel
            return (
              <button
                key={t.label}
                type="button"
                onClick={() => { setSel(i); onOpenPlans?.() }}
                style={{
                  flex: 1, position: 'relative',
                  border: isSel
                    ? `1px solid ${isPopSel ? 'color-mix(in oklab, var(--accent) 55%, var(--border))' : 'var(--accent)'}`
                    : '1px solid var(--border)',
                  borderRadius: 15,
                  padding: '11px 11px 12px',
                  background: isSel
                    ? 'color-mix(in oklab, var(--accent-soft) 70%, var(--surface))'
                    : 'var(--surface-2)',
                  textAlign: 'left', cursor: 'pointer', fontFamily: 'inherit',
                  boxShadow: isSel ? '0 0 0 3px color-mix(in oklab, var(--accent) 20%, transparent)' : 'none',
                  transition: 'transform 0.14s ease, border-color 0.16s, background 0.16s, box-shadow 0.16s',
                }}
              >
                {t.pop && (
                  <span style={{
                    position: 'absolute', top: -8, right: 9,
                    height: 17, padding: '0 7px', borderRadius: 999,
                    background: 'var(--accent)', color: 'var(--on-accent)',
                    fontSize: 9.5, fontWeight: 700, letterSpacing: '0.2px',
                    display: 'inline-flex', alignItems: 'center',
                  }}>ХИТ</span>
                )}
                <div style={{
                  fontSize: 11, fontWeight: 600, letterSpacing: '-0.1px',
                  color: isPopSel ? 'var(--accent-deep)' : 'var(--text-3)',
                }}>{t.label}</div>
              </button>
            )
          })}
        </div>

        {/* CTA */}
        <button
          type="button"
          onClick={onOpenPlans}
          style={{
            marginTop: 16, appearance: 'none', border: 0,
            background: 'var(--text)', color: 'var(--bg)',
            width: '100%', height: 54, padding: '0 22px',
            borderRadius: 'var(--r-pill)',
            fontSize: 16, fontWeight: 600, letterSpacing: '-0.2px',
            cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 9,
            fontFamily: 'inherit',
            animation: 'cta-pulse 3s ease-in-out infinite',
          }}
        >
          Оформить абонемент
          <Icon name="arrowRight" size={18} color="currentColor" strokeWidth={2.4} />
        </button>

        {/* Footer */}
        <div style={{
          marginTop: 11, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
          fontSize: 12, fontWeight: 500, color: 'var(--text-3)',
        }}>
          <Icon name="lightning" size={13} color="var(--accent-deep)" strokeWidth={2.2} />
          Пропуск откроется за пару секунд
        </div>
      </div>
    </div>
  )
}

// Dismissible onboarding strip — v2 circular ring + step chips (Plan 260601-oan)
export function OnboardingStrip({ steps, doneCount, title, badge, onOpenPlans, onTab, onOpenOnboarding }) {
  const [dismissed, setDismissed] = React.useState(false)
  const [dismissing, setDismissing] = React.useState(false)

  if (dismissed) return null

  function handleDismiss() {
    setDismissing(true)
    setTimeout(() => setDismissed(true), 360)
  }

  function handleStepClick(step) {
    if (step.key === 'plan') onOpenPlans?.()
    // D-04: «Профиль» step re-enters the questionnaire via /onboarding (manual re-entry)
    else if (step.key === 'profile') onOpenOnboarding?.()
    else if (step.key === 'visit') onTab?.('book')
    // Step 1 (account, done) — no action
  }

  const stepIcons = { account: 'user', plan: 'card', profile: 'user', visit: 'calendar' }

  // SVG ring math: r=24, circumference = 2·π·24 ≈ 150.8
  const CIRC = 150.8
  const ringOffset = CIRC * (1 - doneCount / 4)

  return (
    <div
      className={`card onboard-card${dismissing ? ' dismissing' : ''}`}
      style={{ margin: '0 16px 12px', overflow: 'hidden' }}
    >
      {/* Header: [ring] [titles] [dismiss ×] */}
      <div style={{
        padding: '16px 16px 14px',
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        {/* Circular progress ring — doneCount live-bound from deriveOnboardingSteps */}
        <div style={{ position: 'relative', width: 56, height: 56, flexShrink: 0 }} aria-hidden="true">
          <svg viewBox="0 0 56 56" width={56} height={56} style={{ display: 'block', transform: 'rotate(-90deg)' }}>
            <circle
              cx="28" cy="28" r="24" fill="none"
              stroke="var(--border)" strokeWidth="5"
            />
            <circle
              cx="28" cy="28" r="24" fill="none"
              stroke="var(--accent)" strokeWidth="5"
              strokeLinecap="round"
              strokeDasharray={CIRC}
              strokeDashoffset={ringOffset}
              style={{ transition: 'stroke-dashoffset 0.7s cubic-bezier(0.32,0.72,0.2,1)' }}
            />
          </svg>
          {/* Fraction overlay centered over ring */}
          <div style={{
            position: 'absolute', inset: 0,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15, fontWeight: 800, letterSpacing: '-0.4px',
            fontVariantNumeric: 'tabular-nums', color: 'var(--text)',
          }}>
            {doneCount}<small style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-3)', marginLeft: 1 }}>/4</small>
          </div>
        </div>

        {/* Titles */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <div style={{
            fontSize: 11, fontWeight: 700, letterSpacing: '0.5px', textTransform: 'uppercase',
            color: 'var(--accent-deep)',
            display: 'inline-flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--accent-deep)' }} />
            Старт новичка
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: '-0.3px', lineHeight: 1.2 }}>
            {title}
          </div>
        </div>

        {/* Dismiss × */}
        <button
          onClick={handleDismiss}
          aria-label="Скрыть"
          style={{
            appearance: 'none', border: 0, width: 24, height: 24,
            borderRadius: 999, background: 'transparent', color: 'var(--text-3)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', padding: 0, alignSelf: 'flex-start',
          }}
        >
          <Icon name="close" size={14} color="currentColor" strokeWidth={2} />
        </button>
      </div>

      {/* Step chips — horizontal scroll */}
      <div style={{
        padding: '0 16px 14px',
        display: 'flex', gap: 8,
        overflowX: 'auto', overflowY: 'hidden',
        WebkitOverflowScrolling: 'touch',
        scrollbarWidth: 'none',
      }}>
        {steps.map((step) => {
          const isDone = step.state === 'done'
          const isNext = step.state === 'next'
          const clickable = step.key !== 'account'
          return (
            <button
              key={step.key}
              onClick={clickable ? () => handleStepClick(step) : undefined}
              className={`step${isDone ? ' done' : isNext ? ' next' : ''}`}
              style={!clickable ? { cursor: 'default' } : undefined}
            >
              {/* Icon ring */}
              <span style={{
                width: 26, height: 26, borderRadius: '50%',
                background: isDone ? 'var(--accent)' : isNext ? 'var(--text)' : 'var(--surface)',
                border: isDone ? '1.5px solid var(--accent)' : isNext ? '1.5px solid var(--text)' : '1.5px solid var(--border-strong)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                color: isDone ? 'var(--on-accent)' : isNext ? 'var(--bg)' : 'var(--text-2)',
                flexShrink: 0,
              }}>
                {isDone
                  ? <Icon name="check" size={14} color="currentColor" strokeWidth={2.2} />
                  : <Icon name={stepIcons[step.key] || 'user'} size={14} color="currentColor" strokeWidth={2} />}
              </span>
              {/* Label */}
              <span style={{ fontSize: 12.5, fontWeight: 600, letterSpacing: '-0.1px', lineHeight: 1.25 }}>
                {step.label}
              </span>
              {/* Meta */}
              <span style={{
                fontSize: 11, letterSpacing: '-0.05px', lineHeight: 1.3,
                color: isDone ? 'var(--accent-deep)' : isNext ? 'var(--text-2)' : 'var(--text-3)',
                fontWeight: isNext ? 500 : 400,
              }}>
                {step.meta}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

// Branded first-visit promo — v2 ticket card (Plan 260601-oan)
export function FirstVisitNudge({ onTab }) {
  return (
    <button
      type="button"
      onClick={() => onTab?.('book')}
      className="press"
      style={{
        margin: '0 16px 12px', position: 'relative', overflow: 'hidden',
        appearance: 'none',
        border: '0.5px solid var(--border)',
        borderRadius: 22,
        background: 'var(--surface)',
        padding: '15px 16px',
        display: 'flex', alignItems: 'center', gap: 14,
        width: 'calc(100% - 32px)',
        cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit',
        color: 'var(--text)',
        boxShadow: 'var(--sh-1)',
      }}
    >
      {/* Ticket illustration with 0₽ badge */}
      <span style={{ position: 'relative', flexShrink: 0 }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 56, height: 56, borderRadius: 17,
          background: 'var(--accent)', color: 'var(--on-accent)',
          boxShadow: '0 10px 22px color-mix(in oklab, var(--accent) 32%, transparent)',
        }}>
          <Icon name="ticket" size={28} color="currentColor" strokeWidth={1.9} />
        </span>
        {/* «0 ₽» free badge */}
        <span style={{
          position: 'absolute', bottom: -7, right: -7,
          height: 19, padding: '0 7px', borderRadius: 999,
          background: 'var(--text)', color: 'var(--bg)',
          fontSize: 10, fontWeight: 700, letterSpacing: '-0.1px',
          display: 'inline-flex', alignItems: 'center',
          border: '2px solid color-mix(in oklab, var(--accent-soft) 50%, var(--surface))',
        }}>
          0 ₽
        </span>
      </span>
      {/* Body */}
      <div style={{ flex: 1, minWidth: 0, position: 'relative' }}>
        <div style={{
          fontSize: 10.5, fontWeight: 700, letterSpacing: '0.5px', textTransform: 'uppercase',
          color: 'var(--accent-deep)',
        }}>
          Для новичков
        </div>
        <div style={{ marginTop: 3, fontSize: 16, fontWeight: 700, letterSpacing: '-0.3px', lineHeight: 1.2 }}>
          Первый визит — бесплатно
        </div>
        <div style={{ marginTop: 2, fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.3 }}>
          Экскурсия с тренером · 30 минут
        </div>
      </div>
      {/* Go button */}
      <span style={{
        flexShrink: 0,
        width: 32, height: 32, borderRadius: 999,
        background: 'var(--text)', color: 'var(--bg)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon name="chevronRight" size={15} color="currentColor" strokeWidth={2.4} />
      </span>
    </button>
  )
}

// Static non-interactive strip — QR pass locked until subscription paid (v2 mockup)
export function QrPlaceholder() {
  return (
    <div
      role="img"
      style={{
        margin: '0 16px 14px',
        background: 'var(--surface-2)',
        border: '0.5px solid var(--border)',
        borderRadius: 'var(--r-md)',
        padding: '10px 14px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}
    >
      <span style={{
        width: 32, height: 32, borderRadius: 9,
        background: 'var(--surface)', border: '0.5px solid var(--border)',
        color: 'var(--text-3)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon name="qr" size={18} color="var(--text-3)" strokeWidth={1.8} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, letterSpacing: '-0.1px', color: 'var(--text-2)', lineHeight: 1.2 }}>
          QR-пропуск
        </div>
        <div style={{ marginTop: 1, fontSize: 12, color: 'var(--text-3)', lineHeight: 1.3 }}>
          Активируется после оплаты абонемента
        </div>
      </div>
      <Icon name="lock" size={16} color="var(--text-3)" strokeWidth={1.8} />
    </div>
  )
}

// Top-level newbie variant — composes all newbie sub-components with stagger (v2 mockup)
export function HomeNewbie({ me, homeData, bookings, userName, onOpenPlans, onOpenGymInfo, onOpenNotifications, onTab, onOpenOnboarding }) {
  const { steps, doneCount, title, badge } = deriveOnboardingSteps(me, homeData, bookings)

  // Derive real initials from me.firstName (API-backed)
  const initial = userName ? [...userName.trim()][0]?.toUpperCase() : null

  return (
    <div className="stagger">
      {/* (1) Hero-card header — v2 surface card (stagger child 1) */}
      <div style={{ margin: '0 16px 12px' }}>
        <div style={{
          background: 'var(--surface)',
          border: '0.5px solid var(--border)',
          borderRadius: 20,
          boxShadow: 'var(--sh-2)',
          padding: '11px 14px',
          position: 'relative',
        }}>
          {/* Top row: title + actions */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            {/* Left: gym title + location */}
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 18, fontWeight: 750, letterSpacing: '-0.4px', lineHeight: 1.05 }}>
                Мой зал
              </div>
              <div style={{
                marginTop: 2, fontSize: 12, color: 'var(--text-2)',
                display: 'inline-flex', alignItems: 'center', gap: 5,
              }}>
                <Icon name="mapPin" size={13} color="var(--accent-deep)" strokeWidth={2} />
                Тверская
              </div>
            </div>
            {/* Right: bell + avatar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>
              <button
                type="button"
                onClick={onOpenNotifications}
                aria-label="Уведомления"
                className="press"
                style={{
                  width: 38, height: 38, borderRadius: 12,
                  border: '0.5px solid var(--border)', background: 'var(--surface)',
                  boxShadow: 'var(--sh-1)', color: 'var(--text)',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer', appearance: 'none', fontFamily: 'inherit',
                  flexShrink: 0, padding: 0,
                }}
              >
                <Icon name="bell" size={19} color="var(--text)" strokeWidth={1.8} />
              </button>
              {/* Avatar: real initials from me.firstName (API-backed); no fake presence dot */}
              <div style={{
                width: 38, height: 38, borderRadius: 12,
                background: 'var(--accent)', color: 'var(--on-accent)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 16, fontWeight: 800, letterSpacing: '-0.5px',
                boxShadow: '0 6px 16px color-mix(in oklab, var(--accent) 30%, transparent)',
                flexShrink: 0,
              }}>
                {initial
                  ? initial
                  : <Icon name="user" size={18} color="var(--on-accent)" strokeWidth={1.8} />}
              </div>
            </div>
          </div>

          {/* Stats row — single truthful stat: «Зал» → onOpenGymInfo */}
          {/* D-LIVE: occupancy and closing time are NOT API-backed — omitted */}
          <div style={{
            marginTop: 10, paddingTop: 10,
            borderTop: '0.5px solid var(--border)',
            display: 'flex',
          }}>
            <button
              type="button"
              onClick={onOpenGymInfo}
              className="press"
              style={{
                flex: 1, display: 'flex', flexDirection: 'column', gap: 6,
                alignItems: 'flex-start', background: 'transparent', border: 0,
                padding: 0, cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
              }}
            >
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: '0.4px', textTransform: 'uppercase',
                color: 'var(--text-3)', lineHeight: 1,
              }}>Зал</span>
              <span style={{
                display: 'flex', alignItems: 'center', gap: 7,
                fontSize: 14, fontWeight: 700, color: 'var(--text)',
                letterSpacing: '-0.2px', lineHeight: 1,
              }}>
                Расписание
                <Icon name="chevronRight" size={12} color="var(--text-3)" strokeWidth={2.2} />
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* (2) HeroNewbie plan-card (stagger child 2) */}
      <HeroNewbie onOpenPlans={onOpenPlans} />

      {/* (3) OnboardingStrip (stagger child 3) */}
      <OnboardingStrip
        steps={steps}
        doneCount={doneCount}
        title={title}
        badge={badge}
        onOpenPlans={onOpenPlans}
        onTab={onTab}
        onOpenOnboarding={onOpenOnboarding}
      />

      {/* (4) FirstVisitNudge + QrPlaceholder grouped as one stagger child */}
      <div>
        <FirstVisitNudge onTab={onTab} />
        <QrPlaceholder />
      </div>

      {/* (5) Tiles grid (stagger child 5) */}
      <div style={{ padding: '0 16px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {/* Trainers tile — anonymous avatar stack (D-LIVE: no fake identities/counts) */}
        <button
          type="button"
          onClick={() => onTab?.('book')}
          className="press"
          style={{
            borderRadius: 20, border: '0.5px solid var(--border)',
            padding: '15px 15px 16px', minHeight: 132,
            display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
            background: 'var(--surface)', cursor: 'pointer', textAlign: 'left',
            fontFamily: 'inherit', color: 'var(--text)', appearance: 'none',
          }}
        >
          {/* Anonymous avatar stack — 3 plain circles, no fake initials */}
          <div style={{ display: 'flex', alignItems: 'center' }} aria-hidden="true">
            {[
              'var(--accent)',
              'color-mix(in oklab, var(--accent) 60%, #6ee7c4)',
              'var(--accent-deep)',
            ].map((bg, i) => (
              <div key={i} style={{
                width: 34, height: 34, borderRadius: '50%',
                border: '2.5px solid var(--surface)',
                marginLeft: i === 0 ? 0 : -11,
                background: bg,
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}>
                <Icon name="user" size={14} color="var(--on-accent)" strokeWidth={1.6} />
              </div>
            ))}
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 650, letterSpacing: '-0.2px' }}>Тренеры</div>
            <div style={{ marginTop: 2, fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.3 }}>
              кто работает в зале
            </div>
          </div>
        </button>

        {/* Chat tile — dark, typing bubble (D-LIVE: no fake unread badge/SLA) */}
        <button
          type="button"
          onClick={() => onTab?.('chat')}
          className="press"
          style={{
            borderRadius: 20, border: '0.5px solid var(--text)',
            padding: '15px 15px 16px', minHeight: 132,
            display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
            background: 'var(--text)', cursor: 'pointer', textAlign: 'left',
            fontFamily: 'inherit', color: 'var(--bg)', appearance: 'none',
          }}
        >
          {/* Typing bubble illustration */}
          <div style={{ position: 'relative', width: 'fit-content' }} aria-hidden="true">
            <span style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              width: 50, height: 38,
              borderRadius: '15px 15px 15px 5px',
              background: 'rgba(255,255,255,0.13)',
            }}>
              {[0, 0.2, 0.4].map((delay, i) => (
                <i key={i} style={{
                  display: 'block', width: 6, height: 6, borderRadius: '50%',
                  background: 'var(--accent)',
                  animation: 'chat-dot 1.4s ease-in-out infinite',
                  animationDelay: `${delay}s`,
                  opacity: i === 0 ? 1 : i === 1 ? 0.7 : 0.45,
                }} />
              ))}
            </span>
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 650, letterSpacing: '-0.2px' }}>Чат</div>
            <div style={{ marginTop: 2, fontSize: 12.5, lineHeight: 1.3, color: 'color-mix(in oklab, var(--bg) 62%, transparent)' }}>
              админ + тренер
            </div>
          </div>
        </button>
      </div>

      {/* (6) Bottom spacer */}
      <div style={{ height: 8 }} />
    </div>
  )
}

// Variant A: Classic — subscription card + QR button + actions + feed
export function HomeClassic({ isEmpty, sub, subTone, fillTone, pct, onOpenQR, onOpenPlans, onOpenManage, onOpenNotifications, onTab, unread, trainerCancelled, subCardStyle, nextBooking }) {
  return (
    <>
      {/* Trainer cancelled — strong alert (demo-only, tweaks-driven) */}
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
      {!isEmpty && nextBooking ? (
        <UpcomingCard booking={nextBooking} onClick={onOpenManage} onCancel={onOpenManage} />
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
        <QuickTile icon="chat" title="Чат" sub="админ + тренер" onClick={() => onTab('chat')} badge={unread > 0 ? unread : null} />
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
export function HomeQrHero({ isEmpty, sub, subTone, fillTone, pct, onOpenQR, onOpenPlans, onOpenManage, onOpenNotifications, onTab, unread, trainerCancelled, nextBooking }) {
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

      {!isEmpty && nextBooking && <UpcomingCard booking={nextBooking} onClick={onOpenManage} onCancel={onOpenManage} compact />}

      <div style={{ padding: '4px 16px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <QuickTile icon="calendar" title="Записаться" sub="к тренеру" onClick={() => onTab('book')} />
        <QuickTile icon="chat" title="Чат" sub="админ + тренер" onClick={() => onTab('chat')} badge={isEmpty ? 0 : unread > 0 ? unread : null} />
      </div>

      <FeedSection unread={unread} isEmpty={isEmpty} onOpenNotifications={onOpenNotifications} />
    </>
  );
}

// Variant C: Minimal — single big "next thing" hero
export function HomeMinimal({ isEmpty, sub, subTone, fillTone, pct, onOpenQR, onOpenPlans, onOpenManage, onOpenNotifications, onTab, unread, trainerCancelled, nextBooking }) {
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

  // Format nextBooking for display
  const bookingTime = nextBooking?.startTime
    ? new Date(nextBooking.startTime).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' })
    : null;
  const bookingTrainer = nextBooking?.trainerName ?? null;

  if (isEmpty || !nextBooking) {
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
          {bookingTime ? `Сегодня в ${bookingTime} · через ${cd.primary}` : `через ${cd.primary}`}
        </div>
        <div className="t-display" style={{ marginTop: 4, marginBottom: 6, letterSpacing: -1 }}>
          Тренировка<br/>{bookingTrainer ? `с ${bookingTrainer}` : ''}
        </div>
        <div className="t-body" style={{ color: 'var(--text-2)' }}>
          Зал на Тверской
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

// ─── Upcoming booking card — receives real booking from API ─────────────────
// booking: ClientNextBookingResponse | null { id, trainerName, startTime, status }
export function UpcomingCard({ booking, onClick, compact, onCancel }) {
  const ms = useCountdown(4 * 3600 * 1000 + 12 * 60 * 1000);
  const cd = formatCountdown(ms);

  const trainerName = booking?.trainerName ?? 'Тренер';
  const startTime = booking?.startTime
    ? new Date(booking.startTime).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' })
    : '—';
  const startDate = booking?.startTime
    ? new Date(booking.startTime).toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', timeZone: 'Europe/Moscow' })
    : '—';

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
        background: 'var(--accent-soft)', color: 'var(--accent-deep)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon name="calendar" size={20} color="currentColor" strokeWidth={1.8} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="row-between" style={{ gap: 8 }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', whiteSpace: 'nowrap' }}>Ближайшая запись</div>
          <div className="t-mini t-num" style={{ color: 'var(--accent-deep)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
            через {cd.primary}
          </div>
        </div>
        <div className="t-h3" style={{ marginTop: 2, fontSize: 15 }}>
          {startTime} · {startDate}
        </div>
        <div className="row-between" style={{ marginTop: 1, gap: 8 }}>
          <div className="t-small">с {trainerName}</div>
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
    </div>
  );
}

// ─── Trainer cancellation card (demo-only, tweaks-driven) ────────────────────
export function TrainerCancelCard({ onTab }) {
  const c = DEMO_TRAINER_CANCEL;
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
  // Notifications are not yet available from the API — show empty state
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
      <div style={{ padding: '0 16px' }}>
        <div className="card" style={{ padding: 0 }}>
          <EmptyState
            illustration="sparkle"
            title="Нет новых уведомлений"
            body="Здесь появятся новости, акции и изменения расписания."
            compact
          />
        </div>
      </div>
    </div>
  );
}
