/**
 * ЮKassa return_url target — polls payment status, shows anti-oracle copy, routes Home.
 *
 * Criterion #1 (anti-oracle): ONLY shows "Ожидаем подтверждение..." while status
 * is pending. Never shows membership-active or any activation state prematurely.
 * Navigates to "/" only when status === 'succeeded'.
 *
 * D-71-04 (PT idempotency): the idempotency_key is carried in the return_url query
 * param — read from useSearchParams() for display/retry purposes.
 *
 * D-20-PWA-ROUTER: react-router v6 kept (no TanStack Router migration).
 */
import React from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useClientPaymentStatus } from '@/data';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';

export function PaymentReturnScreen() {
  const [params] = useSearchParams();
  const paymentId = params.get('payment_id');
  // D-71-04: idempotency_key carried in return_url for PT packages (retry safety).
  // Stored here so retry flows can read it back from useSearchParams().
  const _idempotencyKey = params.get('idempotency_key');

  const { data, isLoading } = useClientPaymentStatus(paymentId, !!paymentId);

  // On succeeded: navigate Home to show now-active membership/PT package.
  // This is the ONLY condition under which we leave this screen upward (criterion #1).
  if (data?.status === 'succeeded') {
    return <Navigate to="/" replace />;
  }

  // On canceled: show a canceled state with a button to go back.
  if (data?.status === 'canceled') {
    return <PaymentCanceledView />;
  }

  // While loading, pending, or no paymentId: ONLY show "ожидаем подтверждение".
  // NEVER display membership-active or any premature activation (T-71-18 / criterion #1).
  return (
    <div
      className="page"
      style={{
        background: 'var(--bg)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 20,
        padding: 32,
        textAlign: 'center',
      }}
    >
      <StatusBar />

      {/* Spinner */}
      <div style={{
        width: 64, height: 64, borderRadius: 999,
        background: 'var(--accent-soft)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {isLoading || !data || data.status === 'pending' ? (
          <div
            className="ptr-spin"
            style={{
              width: 32, height: 32, borderWidth: 3,
              borderColor: 'var(--accent-deep)',
              borderTopColor: 'transparent',
            }}
          />
        ) : (
          <Icon name="clock" size={32} color="var(--accent-deep)" strokeWidth={1.8} />
        )}
      </div>

      {/* Anti-oracle copy — criterion #1: ONLY this text while pending */}
      <div>
        <div className="t-h2" style={{ marginBottom: 8 }}>
          Ожидаем подтверждение...
        </div>
        <div className="t-small" style={{ color: 'var(--text-2)', maxWidth: 280 }}>
          Платёж обрабатывается. Страница обновится автоматически.
        </div>
      </div>

      {!paymentId && (
        <div className="t-small" style={{ color: 'var(--text-3)', marginTop: 8 }}>
          Неверная ссылка возврата — payment_id не найден.
        </div>
      )}
    </div>
  );
}

function PaymentCanceledView() {
  const navigate = useNavigate();
  return (
    <div
      className="page"
      style={{
        background: 'var(--bg)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 20,
        padding: 32,
        textAlign: 'center',
      }}
    >
      <StatusBar />

      <div style={{
        width: 64, height: 64, borderRadius: 999,
        background: 'var(--warn-soft)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon name="close" size={32} color="#a36a16" strokeWidth={2} />
      </div>

      <div>
        <div className="t-h2" style={{ marginBottom: 8 }}>Оплата отменена</div>
        <div className="t-small" style={{ color: 'var(--text-2)', maxWidth: 280 }}>
          Платёж был отменён. Вернись и выбери тариф снова.
        </div>
      </div>

      <button
        onClick={() => navigate('/', { replace: true })}
        className="btn btn-accent"
        style={{ height: 48, padding: '0 28px' }}
      >
        На главную
      </button>
    </div>
  );
}
