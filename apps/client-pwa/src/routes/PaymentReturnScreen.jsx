/**
 * ЮKassa return_url target — polls payment status, shows anti-oracle copy, routes Home.
 *
 * Criterion #1 (anti-oracle): ONLY shows "Ожидаем подтверждение" while status
 * is pending. Never shows membership-active or any activation state prematurely.
 * Navigates to "/" only after user taps "Хорошо" on confirmed succeeded state (D-10).
 *
 * D-10: success state rendered via PaymentSucceededView — no immediate Navigate on
 * succeeded. The success view renders ONLY when data.status === 'succeeded' (confirmed
 * server truth). Never on loading / pending / any other status.
 *
 * D-11: "Открыть чек" button shown only when data.receiptUrl is non-null.
 *
 * D-71-04 (PT idempotency): the idempotency_key is carried in the return_url query
 * param — read from useSearchParams() for display/retry purposes.
 *
 * D-20-PWA-ROUTER: react-router v6 kept (no TanStack Router migration).
 */
import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useClientPaymentStatus, useClientMe, useClientMembership } from '@/data';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { formatRuDate } from '@/utils/format.js';

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
        onDone={() => navigate('/', { replace: true })}
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
 * Receipt link conditional on D-11. a11y: focus CTA on mount, aria-live region, aria-labels.
 */
function PaymentSucceededView({ data, onDone }) {
  const primaryBtnRef = React.useRef(null);

  // a11y: focus the primary CTA when this view mounts (UI-SPEC accessibility rule).
  React.useEffect(() => {
    primaryBtnRef.current?.focus();
  }, []);

  // Personalized greeting — firstName from /client/me; fallback when absent.
  const { data: meData } = useClientMe();
  const firstName = meData?.firstName ?? '';

  // D-10 anti-oracle gate: membership is ONLY fetched when status === 'succeeded'.
  // data.status is already confirmed 'succeeded' here (caller branch guard), so
  // passing true is safe — but wire it explicitly for clarity and future-proofing.
  const { data: membership } = useClientMembership(data?.status === 'succeeded');

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

        {/* ── Truthful sub copy — no hardcoded plan duration ── */}
        <div className="pa-sub">
          Оплата подтверждена. Доступ активен.
        </div>

        {/* ── Real plan card — rendered ONLY when membership is non-null ── */}
        {membership && (
          <div className="pa-card" aria-label="Активный абонемент">
            <div className="pa-card-head">
              <span className="pa-card-name">{membership.planNameSnapshot}</span>
              {membership.status === 'active' && (
                <span className="pa-badge">Активен</span>
              )}
            </div>
            <div className="pa-card-meta">
              Действует до {formatRuDate(membership.endDate)}
            </div>
            <div className="pa-days">
              Впереди {membership.daysUntilEnd} дней
            </div>
          </div>
        )}

        {/* ── Receipt destination chip (anti-oracle: only in succeeded branch) ── */}
        {(data?.receiptEmail || data?.receiptPhone) && (
          <div className="pa-receipt-chip">
            <Icon name="mail" size={20} color="var(--text-2)" aria-hidden="true" />
            <div>
              <div style={{
                fontSize: 11, fontWeight: 600, letterSpacing: 0.4,
                color: 'var(--text-3)', textTransform: 'uppercase',
              }}>
                ЧЕК ОТПРАВЛЕН НА
              </div>
              <div style={{
                fontSize: 15, fontWeight: 650, letterSpacing: -0.2,
                color: 'var(--text)',
              }}>
                {data.receiptEmail ?? data.receiptPhone}
              </div>
            </div>
          </div>
        )}

        {/* ── CTA stack ── */}
        <div className="pa-actions">
          {/* D-11: "Открыть чек" shown ONLY when receiptUrl is non-null */}
          {data?.receiptUrl && (
            <a
              href={data.receiptUrl}
              target="_blank"
              rel="noreferrer"
              className="btn btn-ghost"
              style={{ height: 54, width: '100%', textDecoration: 'none' }}
              aria-label="Открыть чек оплаты (новая вкладка)"
            >
              Открыть чек
            </a>
          )}
          {/* Single primary CTA — focuses on mount via primaryBtnRef */}
          <button
            ref={primaryBtnRef}
            onClick={onDone}
            className="btn btn-accent"
            style={{ height: 54, width: '100%' }}
          >
            Хорошо
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
