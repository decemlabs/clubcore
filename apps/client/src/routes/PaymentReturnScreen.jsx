/**
 * ЮKassa return_url target — polls payment status, shows anti-oracle copy, routes Home.
 *
 * Criterion #1 (anti-oracle): ONLY shows "Ожидаем подтверждение" while status
 * is pending. Never shows membership-active or any activation state prematurely.
 * Navigates to "/" only after user taps a CTA on confirmed succeeded state (D-10).
 *
 * D-10: success state rendered via PaymentSucceededView — no immediate Navigate on
 * succeeded. The success view renders ONLY when data.status === 'succeeded' (confirmed
 * server truth). Never on loading / pending / any other status.
 *
 * D-11: "Открыть чек" link shown only when data.receiptUrl is non-null.
 *
 * D-71-04 (PT idempotency): the idempotency_key is carried in the return_url query
 * param — read from useSearchParams() for display/retry purposes.
 *
 * D-20-PWA-ROUTER: react-router v6 kept (no TanStack Router migration).
 *
 * REVISION 1 (260601-vxr-01): Restored to full visual 1:1 with the mockup.
 * Added: achievement chip, validity progress bar (100% at activation), perks list
 * (static hardcoded copy), receipt-link row inside card (real amount from payment
 * history), two CTA buttons (QR-pass + home). QR button signals App shell via
 * navigate state { openQr: true } — App.jsx reads it once on HomeRoute mount.
 *
 * REVISION 2 (260601-vxr): User-feedback corrections.
 * - Removed "ЧЕК ОТПРАВЛЕН НА" receipt-destination chip (not in mockup).
 * - Receipt-link row now always renders inside the card (was gated on paidAmount/receiptUrl);
 *   fallback label "Оплата · картой" shown when amount unavailable.
 * - TabBar hidden on /payment/return via App.jsx hideTabBar (navigation not needed here).
 * - Increased spacing between check medallion and headline (pa-title margin-top: 14px).
 * Chip omission accepted per amended 999.5-UI-SPEC §Screen 2 D-09 (Phase 77 / FIX-02).
 */
import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useClientPaymentStatus, useClientMe, useClientMembership, useClientPaymentHistory } from '@/data';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { formatRuDate, formatMoney } from '@/utils/format.js';

// WR-02: after this many ms still pending, surface a manual exit so an
// abandoned-payment user is never stranded on the spinner indefinitely.
const PENDING_TIMEOUT_MS = 30_000;

export function PaymentReturnScreen() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const paymentId = params.get('payment_id');
  // D-71-04: idempotency_key carried in return_url for PT packages (retry safety).
  // Stored here so retry flows can read it back from useSearchParams().
  const _idempotencyKey = params.get('idempotency_key');

  const { data, isLoading } = useClientPaymentStatus(paymentId, !!paymentId);

  // WR-02: track when the pending poll has run long enough to offer an exit.
  const [pollTimedOut, setPollTimedOut] = React.useState(false);
  React.useEffect(() => {
    if (!paymentId) return undefined;
    const timer = setTimeout(() => setPollTimedOut(true), PENDING_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [paymentId]);

  // D-10: on succeeded — render the in-app success state (anti-oracle preserved:
  // this branch only runs when data.status is the confirmed string 'succeeded').
  // NEVER shown while loading, pending, or any other status.
  if (data?.status === 'succeeded') {
    return (
      <PaymentSucceededView
        data={data}
      />
    );
  }

  // On canceled: show a restyled canceled state with action buttons.
  if (data?.status === 'canceled') {
    return <PaymentCanceledView />;
  }

  // While loading, pending, or no paymentId: ONLY show "Ожидаем подтверждение".
  // NEVER display membership-active or any premature activation (T-71-18 / criterion #1).
  return (
    <div
      className="page"
      style={{ background: 'var(--bg)' }}
      aria-live="polite"
    >
      <StatusBar />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '32px 32px',
          textAlign: 'center',
          gap: 16,
        }}
      >
        {/* Big spinner — 56×56px accent top-border per UI-SPEC */}
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 999,
            border: '4px solid var(--surface-2)',
            borderTopColor: 'var(--accent)',
            animation: 'ptr-spin 0.8s linear infinite',
          }}
        />

        {/* Anti-oracle copy — criterion #1: ONLY this text while pending */}
        <div className="state-title" style={{ marginTop: 8 }}>
          Ожидаем подтверждение
        </div>
        <div className="state-desc" style={{ marginTop: 0 }}>
          Платёж обрабатывается. Это займёт несколько секунд.
        </div>

        {!paymentId && (
          <div className="t-small" style={{ color: 'var(--text-3)', marginTop: 8 }}>
            Неверная ссылка возврата — payment_id не найден.
          </div>
        )}

        {/* WR-02: after a timeout (or no payment_id) offer a manual exit so the
            user is never stranded on the spinner. Stays anti-oracle compliant —
            reveals no activation state, just lets the user leave. */}
        {(pollTimedOut || !paymentId) && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 8,
              marginTop: 8,
            }}
          >
            {pollTimedOut && paymentId && (
              <div className="t-small" style={{ color: 'var(--text-3)', maxWidth: 280 }}>
                Подтверждение занимает дольше обычного. Если платёж прошёл, статус
                обновится автоматически.
              </div>
            )}
            <button
              onClick={() => navigate('/', { replace: true })}
              className="btn"
              style={{ height: 48, padding: '0 28px' }}
            >
              На главную
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * D-10: Success view — rendered ONLY when data.status === 'succeeded' (confirmed server truth).
 * Never shown while loading or pending. Plan card fed by real membership endpoint, gated by D-10.
 * Receipt link inside card conditional on D-11. Amount sourced from payment history (real, gated).
 * a11y: focus CTA on mount, aria-live region, aria-labels.
 *
 * REVISION 1: Full 1:1 mockup restore — achievement chip, validity progress bar (100% at
 * activation), hardcoded perks, receipt-link row in card (real amount), two CTA buttons.
 */
function PaymentSucceededView({ data }) {
  const navigate = useNavigate();
  const primaryBtnRef = React.useRef(null);

  // a11y: focus the primary CTA when this view mounts (UI-SPEC accessibility rule).
  React.useEffect(() => {
    primaryBtnRef.current?.focus();
  }, []);

  // Personalized greeting — firstName from /client/me; fallback when absent.
  const { data: meData } = useClientMe();
  const firstName = meData?.firstName ?? '';

  // D-10 anti-oracle gate: membership and payment history ONLY fetched when status === 'succeeded'.
  // data.status is already confirmed 'succeeded' here (caller branch guard), so
  // passing true is safe — but wire it explicitly for clarity and future-proofing.
  const succeeded = data?.status === 'succeeded';
  const { data: membership } = useClientMembership(succeeded);

  // Real paid amount from payment history — pick most recent positive online payment.
  // D-10 anti-oracle: enabled gated on succeeded — never fetches while pending.
  const { data: payHistPage } = useClientPaymentHistory(1, succeeded);
  const paidAmount = React.useMemo(() => {
    const items = payHistPage?.items ?? [];
    // Find most recent item where amount > 0 (online positive charge)
    const found = items.find(item => (item.amountKopecks ?? 0) > 0);
    return found?.amountKopecks ?? null;
  }, [payHistPage]);

  // CTA: primary opens QR pass by signalling App shell via navigation state (one-shot).
  const handleOpenQr = () => {
    navigate('/', { state: { openQr: true } });
  };

  const handleHome = () => {
    navigate('/', { replace: true });
  };

  return (
    <div className="page" style={{ background: 'var(--bg)' }}>
      <StatusBar />
      {/* aria-live="polite" so screen readers announce the success state on mount */}
      <div className="pa-screen" aria-live="polite" role="region" aria-label="Оплата подтверждена">

        {/* ── Animated check medallion + confetti ── */}
        <div
          className="pa-check-hero"
          aria-label="Анимированный знак подтверждения"
          role="img"
        >
          {/* Confetti dots — decorative; hidden from assistive technology */}
          <div className="pa-confetti" aria-hidden="true">
            <i /><i /><i /><i /><i /><i /><i /><i />
          </div>
          {/* Check SVG — aria-hidden; region label covers the meaning */}
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.6}
            strokeLinecap="round"
            strokeLinejoin="round"
            width={50}
            height={50}
            aria-hidden="true"
          >
            <path d="M5 12l5 5L20 6" />
          </svg>
        </div>

        {/* ── Personalized headline ── */}
        <div className="pa-title">
          {firstName ? `Ты в команде, ${firstName}` : 'Ты в команде!'}
        </div>

        {/* ── Truthful sub copy ── */}
        <div className="pa-sub">
          Оплата подтверждена. Доступ активен.
        </div>

        {/* ── Achievement chip — static celebratory badge, always shown ── */}
        <div className="pa-achv" aria-label="Достижение: новый участник клуба">
          <span className="pa-achv-star" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth={1.4} strokeLinejoin="round" width={14} height={14} aria-hidden="true">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
          </span>
          Новый участник клуба
        </div>

        {/* ── Real plan card — rendered ONLY when membership is non-null ── */}
        {membership && (
          <div className="pa-card" aria-label="Активный абонемент">
            {/* Card header: plan name + live "Активен" badge */}
            <div className="pa-card-head">
              <span className="pa-card-name">{membership.planNameSnapshot}</span>
              {membership.status === 'active' && (
                <span className="pa-badge pa-badge-live">
                  <span className="pa-badge-dot" aria-hidden="true" />
                  Активен
                </span>
              )}
            </div>

            {/* Validity date */}
            <div className="pa-card-meta">
              Действует до {formatRuDate(membership.endDate)}
            </div>

            {/* Validity progress block — 100% at activation moment */}
            <div className="pa-validity">
              <div className="pa-validity-row">
                <span className="pa-validity-lbl">
                  Впереди{' '}
                  <b>{membership.daysUntilEnd}</b>
                  {' '}дней
                </span>
                <span className="pa-validity-pct">100%</span>
              </div>
              <div className="pa-validity-track" role="progressbar" aria-valuenow={100} aria-valuemin={0} aria-valuemax={100} aria-label="Использовано времени абонемента">
                <div className="pa-validity-fill" style={{ width: '100%' }} />
              </div>
            </div>

            {/* Perks list — hardcoded static copy (no API field; single-gym project) */}
            <div className="pa-perks">
              <div className="pa-perk">
                <span className="pa-perk-dot" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" width={12} height={12} aria-hidden="true">
                    <path d="M5 12l5 5L20 6" />
                  </svg>
                </span>
                Зал круглосуточно
              </div>
              <div className="pa-perk">
                <span className="pa-perk-dot" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" width={12} height={12} aria-hidden="true">
                    <path d="M5 12l5 5L20 6" />
                  </svg>
                </span>
                14 дней заморозки в подарок
              </div>
              <div className="pa-perk">
                <span className="pa-perk-dot" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" width={12} height={12} aria-hidden="true">
                    <path d="M5 12l5 5L20 6" />
                  </svg>
                </span>
                Сауна и групповые без лимита
              </div>
            </div>

            {/* Receipt-link row — always shown inside the card (mockup footer).
                Left: real paid amount when available; fallback neutral label if not.
                Right: "Открыть чек" link only when receiptUrl is non-null (D-11). */}
            <div className="pa-receipt-link">
              <span className="pa-receipt-lbl">
                {paidAmount !== null ? (
                  <>Списано · <b style={{ fontWeight: 600, color: 'var(--text-2)', fontVariantNumeric: 'tabular-nums' }}>{formatMoney(paidAmount)}</b></>
                ) : (
                  <>Оплата · картой</>
                )}
              </span>
              {/* D-11: "Открыть чек" only when receiptUrl is non-null */}
              {data?.receiptUrl ? (
                <a
                  href={data.receiptUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="pa-receipt-val"
                  aria-label="Открыть чек оплаты (новая вкладка)"
                >
                  Открыть чек
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" width={12} height={12} aria-hidden="true">
                    <path d="M9 6l6 6-6 6" />
                  </svg>
                </a>
              ) : null}
            </div>
          </div>
        )}

        {/* ── CTA stack — two buttons per REVISION 1 ── */}
        <div className="pa-actions">
          {/* Primary: open QR pass — signals App shell via navigate state (one-shot) */}
          <button
            ref={primaryBtnRef}
            onClick={handleOpenQr}
            className="btn btn-accent"
            style={{ height: 54, width: '100%' }}
            aria-label="Открыть QR-пропуск"
          >
            {/* QR/grid icon from mockup */}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden="true" width={18} height={18}>
              <rect x="3" y="3" width="7" height="7" rx="1.5" />
              <rect x="14" y="3" width="7" height="7" rx="1.5" />
              <rect x="3" y="14" width="7" height="7" rx="1.5" />
              <path d="M14 14h3v3M21 14v7M14 21h3M17 17v4" />
            </svg>
            Открыть QR-пропуск
          </button>
          {/* Secondary: navigate home */}
          <button
            onClick={handleHome}
            className="btn btn-ghost"
            style={{ height: 54, width: '100%' }}
          >
            На главную
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Canceled view — restyled to .state pattern per UI-SPEC (D-12).
 * .state-icon.info: var(--surface-2) bg, x icon, var(--text-2) color.
 */
function PaymentCanceledView() {
  const navigate = useNavigate();
  return (
    <div className="page" style={{ background: 'var(--bg)' }}>
      <StatusBar />
      <div className="state" aria-live="polite">
        {/* State icon — info tone: var(--surface-2) bg, x icon, var(--text-2) color */}
        <div className="state-icon info">
          <Icon name="x" size={44} strokeWidth={2} color="var(--text-2)" />
        </div>

        <div className="state-title">Оплата отменена</div>
        <div className="state-desc">Ты отменил оплату. Деньги не списались.</div>

        <div
          className="state-actions"
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
          }}
        >
          <button
            onClick={() => navigate(-1)}
            className="btn btn-accent"
            style={{ height: 54, width: '100%' }}
          >
            Попробовать снова
          </button>
          <button
            onClick={() => navigate('/', { replace: true })}
            className="btn btn-ghost"
            style={{ height: 54, width: '100%' }}
          >
            На главную
          </button>
        </div>
      </div>
    </div>
  );
}
