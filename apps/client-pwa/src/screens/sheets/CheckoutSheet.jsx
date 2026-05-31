import React from 'react';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { useClientCheckoutMembership, useClientCheckoutPtPackage, usePromoValidate, useClientMe } from '@/data';
import { formatMoney } from '@/utils/format.js';
import { ReceiptEmailGate } from './ReceiptEmailGate.jsx';

// Accepts: { kind: 'sub' | 'pt', planId, title, subtitle, amount }
// kind: 'sub' → membership checkout (CPAY-01)
// kind: 'pt'  → PT-package checkout (CPAY-02, client-supplied idempotency key D-71-04)
// amount in kopecks

// ─── Error code → inline error kind mapping (D-71-02 discretion) ───────────
function mapApiErrorToKind(code) {
  if (code === 'client_email_required_for_online_payment') return 'email-required';
  if (code === 'yookassa_unavailable') return 'offline';
  if (code === 'yookassa_permanent_error') return 'payment';
  if (code === 'network_error') return 'offline';
  return 'payment';
}

// ─── Promo error code → Russian message map (D-09) ────────────────────────
const PROMO_ERROR_MESSAGES = {
  not_found:      'Промокод не найден',
  expired:        'Промокод истёк',
  not_yet_active: 'Промокод ещё не активен',
  used_up:        'Промокод уже использован',
  not_applicable: 'Промокод не применяется к этому продукту',
  inactive:       'Промокод неактивен',
};

export const CheckoutSheet = ({ ctx, onClose, onDone, forceOutcome }) => {
  const [stage, setStage] = React.useState('review'); // 'review' | 'email-gate' | 'paying' | 'error'
  const [errorKind, setErrorKind] = React.useState(null); // 'payment' | 'slot-busy' | 'offline' | 'email-required'
  const [promoCode, setPromoCode] = React.useState('');
  const [promoLoading, setPromoLoading] = React.useState(false);
  const [promoError, setPromoError] = React.useState(null); // error code string | null
  const [promoResult, setPromoResult] = React.useState(null); // { discountKopecks, newAmountKopecks, discountType } | null

  // D-71-04: generate idempotency key once per checkout intent (for PT packages).
  const idempotencyKey = React.useRef(
    typeof crypto !== 'undefined' ? crypto.randomUUID() : Math.random().toString(36).slice(2)
  );

  const checkoutMembership = useClientCheckoutMembership();
  const checkoutPtPackage = useClientCheckoutPtPackage();
  const promoValidate = usePromoValidate();
  // D-03: read clientMe to decide whether to show the email-gate or skip it.
  const { data: clientMe } = useClientMe();

  if (!ctx) return null;

  // D-06: server-authoritative amount — never compute price on client
  const total = promoResult ? promoResult.newAmountKopecks : ctx.amount;
  const discount = promoResult ? promoResult.discountKopecks : 0;

  // ─── Promo "Применить" handler ──────────────────────────────────────────
  const handlePromoApply = async () => {
    if (!promoCode || promoLoading) return;
    setPromoLoading(true);
    setPromoError(null);
    try {
      const result = await promoValidate.mutateAsync({ code: promoCode, kind: ctx.kind, planId: ctx.planId });
      // WR-03 fix: snapshot the validated code string into promoResult so that
      // appliedPromoCode at checkout time uses the validated code, not the live
      // input state (which is disabled after validation but fragile as a correctness invariant).
      setPromoResult({ ...result, _validatedCode: promoCode });
    } catch (err) {
      setPromoError(err?.code ?? 'not_found');
    } finally {
      setPromoLoading(false);
    }
  };

  // ─── Promo "Убрать" handler ─────────────────────────────────────────────
  const handlePromoRemove = () => {
    setPromoResult(null);
    setPromoError(null);
    setPromoCode('');
  };

  const startPay = async () => {
    // D-02/D-03: if email absent, show receipt-email gate before proceeding.
    // Skip check when already in email-gate (gate calls startPay after saving).
    if (!clientMe?.email && stage !== 'email-gate') {
      setStage('email-gate');
      return;
    }

    // Demo mode override: if forceOutcome is set, use mock behavior.
    if (forceOutcome && forceOutcome !== 'ok') {
      setStage('paying');
      setTimeout(() => {
        setErrorKind(forceOutcome);
        setStage('error');
      }, 1300);
      return;
    }

    if (!ctx.planId) {
      // No planId — cannot call real checkout; fall back to demo behavior.
      setStage('paying');
      setTimeout(() => {
        setStage('error');
        setErrorKind('payment');
      }, 1300);
      return;
    }

    setStage('paying');
    try {
      let result;
      // D-06: pass promoCode only when a valid promo has been applied.
      // WR-03 fix: use the validated code snapshot from promoResult._validatedCode
      // rather than the live promoCode input state, so the sent code always matches
      // the code that produced the validated discount (input is disabled after validation,
      // but correctness must not rely on UI disabled-ness as an invariant).
      const appliedPromoCode = promoResult ? promoResult._validatedCode : undefined;

      if (ctx.kind === 'sub') {
        // CPAY-01: membership checkout — server-derived idempotency key (D-71-04).
        result = await checkoutMembership.mutateAsync({ planId: ctx.planId, promoCode: appliedPromoCode });
        window.location.href = result.confirmationUrl;
      } else {
        // CPAY-02: PT-package checkout — client-supplied idempotency key (D-71-04).
        const idemKey = idempotencyKey.current;
        result = await checkoutPtPackage.mutateAsync({
          planId: ctx.planId,
          idempotencyKey: idemKey,
          promoCode: appliedPromoCode,
        });
        window.location.href = result.confirmationUrl;
      }
    } catch (err) {
      const code = err?.code ?? err?.message ?? 'payment';
      setErrorKind(mapApiErrorToKind(code));
      setStage('error');
    }
  };

  if (stage === 'error') {
    return (
      <CheckoutError
        kind={errorKind}
        onRetry={() => { setStage('review'); setErrorKind(null); }}
        onClose={onClose}
      />
    );
  }

  // D-02: show receipt-email gate when email absent (D-03: skipped when email present).
  if (stage === 'email-gate') {
    return (
      <ReceiptEmailGate
        onSaved={() => {
          // Email saved — invalidation already fired by useUpdateClientEmail onSettled.
          // Proceed directly to paying (startPay will skip gate since email now in cache).
          setStage('paying');
          // Call the actual pay logic directly (bypass gate re-check since we just set paying).
          void (async () => {
            try {
              let result;
              const appliedPromoCode = promoResult ? promoResult._validatedCode : undefined;
              if (ctx.kind === 'sub') {
                result = await checkoutMembership.mutateAsync({ planId: ctx.planId, promoCode: appliedPromoCode });
                window.location.href = result.confirmationUrl;
              } else {
                const idemKey = idempotencyKey.current;
                result = await checkoutPtPackage.mutateAsync({
                  planId: ctx.planId,
                  idempotencyKey: idemKey,
                  promoCode: appliedPromoCode,
                });
                window.location.href = result.confirmationUrl;
              }
            } catch (err) {
              const code = err?.code ?? err?.message ?? 'payment';
              setErrorKind(mapApiErrorToKind(code));
              setStage('error');
            }
          })();
        }}
        onSkip={() => {
          // D-10: no email collected; receipt goes to phone. Proceed to pay.
          setStage('paying');
          void (async () => {
            try {
              let result;
              const appliedPromoCode = promoResult ? promoResult._validatedCode : undefined;
              if (ctx.kind === 'sub') {
                result = await checkoutMembership.mutateAsync({ planId: ctx.planId, promoCode: appliedPromoCode });
                window.location.href = result.confirmationUrl;
              } else {
                const idemKey = idempotencyKey.current;
                result = await checkoutPtPackage.mutateAsync({
                  planId: ctx.planId,
                  idempotencyKey: idemKey,
                  promoCode: appliedPromoCode,
                });
                window.location.href = result.confirmationUrl;
              }
            } catch (err) {
              const code = err?.code ?? err?.message ?? 'payment';
              setErrorKind(mapApiErrorToKind(code));
              setStage('error');
            }
          })();
        }}
        onBack={() => setStage('review')}
      />
    );
  }

  if (stage === 'paying') {
    return (
      <div style={{
        position: 'absolute', inset: 0, zIndex: 240,
        background: 'var(--bg)', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
      }}>
        <StatusBar />
        <div style={{
          width: 56, height: 56, borderRadius: 999,
          border: '4px solid var(--surface-2)',
          borderTopColor: 'var(--accent)',
          animation: 'ptr-spin 0.8s linear infinite',
        }} />
        <div className="state-title" style={{ marginTop: 24 }}>Оплачиваем…</div>
        <div className="state-desc">Не закрывай экран — это займёт пару секунд.</div>
      </div>
    );
  }

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 240,
      background: 'var(--bg)', display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />

      {/* Top bar */}
      <div style={{
        padding: '48px 12px 4px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <button
          onClick={onClose}
          aria-label="Назад"
          style={{
            width: 36, height: 36, borderRadius: 999, border: 0,
            background: 'var(--surface)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <Icon name="chevronLeft" size={22} color="var(--text)" strokeWidth={2.2} />
        </button>
        <span style={{ fontSize: 15, fontWeight: 650, letterSpacing: -0.1 }}>Оплата</span>
        <div style={{ width: 36 }} />
      </div>

      <div className="scroller" style={{ paddingTop: 0 }}>
        {/* Amount header */}
        <div style={{ padding: '8px 20px 20px', textAlign: 'center' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', marginTop: 8 }}>К ОПЛАТЕ</div>
          <div style={{
            fontSize: 44, fontWeight: 700, letterSpacing: -1.4,
            fontVariantNumeric: 'tabular-nums', lineHeight: 1,
            marginTop: 4,
          }}>
            {formatMoney(total)}
          </div>
          {discount > 0 && (
            <>
              <div className="t-small" style={{ marginTop: 4, color: 'var(--accent-deep)', fontWeight: 600 }}>
                Скидка −{formatMoney(discount)} применена
              </div>
              <div className="t-small" style={{ marginTop: 2, color: 'var(--text-3)', textDecoration: 'line-through' }}>
                {formatMoney(ctx.amount)}
              </div>
            </>
          )}
        </div>

        {/* Order summary */}
        <div style={{ padding: '0 16px 12px' }}>
          <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>ЗАКАЗ</div>
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
              <div style={{
                width: 40, height: 40, borderRadius: 10,
                background: 'var(--surface-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}>
                <Icon name={ctx.kind === 'sub' ? 'card' : ctx.kind === 'pt' ? 'user' : 'tag'}
                      size={20} color="var(--text)" />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 650, letterSpacing: -0.1 }}>{ctx.title}</div>
                <div className="t-small" style={{ marginTop: 2, color: 'var(--text-2)' }}>{ctx.subtitle}</div>
              </div>
              <div style={{ fontSize: 15, fontWeight: 650, fontVariantNumeric: 'tabular-nums' }}>
                {formatMoney(ctx.amount)}
              </div>
            </div>
            {discount > 0 && (
              <>
                <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 16 }} />
                <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <span className="t-small" style={{ color: 'var(--accent-deep)' }}>Промокод {promoCode}</span>
                  <span className="t-small" style={{ color: 'var(--accent-deep)', fontVariantNumeric: 'tabular-nums' }}>
                    −{formatMoney(discount)}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Method info plate (D-01 — no in-app card picker) */}
        <div style={{ padding: '0 16px 12px' }}>
          <div className="card" style={{
            padding: '12px 16px', borderRadius: 'var(--r-lg)',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <Icon name="lock" size={16} color="var(--text-2)" />
            <span className="t-small" style={{ color: 'var(--text-2)' }}>
              Оплата на защищённой странице ЮKassa · Карта, СБП, Мир
            </span>
          </div>
        </div>

        {/* Promo code */}
        <div style={{ padding: '0 16px 12px' }}>
          <div className="card" style={{ padding: '4px 0', borderRadius: 'var(--r-lg)' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '0 16px',
              borderRadius: promoError ? 'var(--r-lg)' : undefined,
              boxShadow: promoResult ? '0 0 0 3px var(--accent-soft)' : undefined,
            }}>
              <Icon name="tag" size={16} color="var(--text-3)" />
              <input
                value={promoCode}
                onChange={e => {
                  setPromoCode(e.target.value.toUpperCase());
                  if (promoError) setPromoError(null);
                }}
                placeholder="Промокод"
                disabled={!!promoResult}
                style={{
                  flex: 1, minWidth: 0, width: '100%',
                  border: 0, outline: 0, background: 'transparent',
                  color: 'var(--text)', fontFamily: 'inherit', fontSize: 15,
                  padding: '8px 0',
                  borderColor: promoError ? 'var(--danger)' : undefined,
                }}
              />
              {promoResult ? (
                <button
                  onClick={handlePromoRemove}
                  style={{
                    background: 'transparent', border: 0, cursor: 'pointer',
                    fontFamily: 'inherit', fontSize: 13, color: 'var(--text-2)',
                    fontWeight: 400, padding: '8px 0', whiteSpace: 'nowrap',
                    minHeight: 44,
                  }}
                >Убрать</button>
              ) : (
                <button
                  onClick={handlePromoApply}
                  disabled={!promoCode || promoLoading}
                  style={{
                    background: 'transparent', border: 0,
                    cursor: promoCode && !promoLoading ? 'pointer' : 'default',
                    fontFamily: 'inherit', fontSize: 13, fontWeight: 600,
                    color: promoCode && !promoLoading ? 'var(--accent-deep)' : 'var(--text-3)',
                    padding: '8px 0', whiteSpace: 'nowrap',
                    display: 'flex', alignItems: 'center', gap: 4,
                    minHeight: 44,
                  }}
                >
                  {promoLoading ? (
                    <span className="ptr-spin" style={{ width: 13, height: 13 }} />
                  ) : 'Применить'}
                </button>
              )}
            </div>
            {promoError && (
              <div
                role="alert"
                className="t-small"
                style={{ color: 'var(--danger)', padding: '4px 16px 8px' }}
              >
                {PROMO_ERROR_MESSAGES[promoError] ?? 'Промокод не найден'}
              </div>
            )}
          </div>
        </div>

        <div style={{ height: 110 }} />
      </div>

      {/* Sticky pay bar */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        padding: '16px 16px 24px',
        background: 'color-mix(in oklab, var(--bg) 88%, transparent)',
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
        borderTop: '0.5px solid var(--border)',
      }}>
        <button
          onClick={startPay}
          disabled={!ctx.planId && !forceOutcome}
          className="btn btn-accent"
          style={{
            width: '100%', height: 54,
            opacity: (!ctx.planId && !forceOutcome) ? 0.4 : 1,
            cursor: (!ctx.planId && !forceOutcome) ? 'not-allowed' : 'pointer',
          }}
        >
          Оплатить · {formatMoney(total)}
        </button>
        <div className="t-mini" style={{
          textAlign: 'center', marginTop: 8, color: 'var(--text-3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
        }}>
          <Icon name="lock" size={11} color="var(--text-3)" />
          Защищено · ЮKassa
        </div>
      </div>
    </div>
  );
};

// Inline error states (D-12 — exactly 4 reachable kinds)
function CheckoutError({ kind, onRetry, onClose }) {
  const primaryRef = React.useRef(null);

  React.useEffect(() => {
    if (primaryRef.current) {
      primaryRef.current.focus();
    }
  }, []);

  const variants = {
    payment: {
      icon: 'alertCircle', tone: 'error',
      title: 'Не удалось оплатить',
      desc: 'Что-то пошло не так при отправке платежа. Попробуй снова или обратись в зал.',
      primary: 'Попробовать снова',
    },
    'slot-busy': {
      icon: 'clock', tone: 'warn',
      title: 'Слот уже занят',
      desc: 'Пока ты оформлял оплату, это время забронировали. Выбери другой слот.',
      primary: 'Выбрать другое время',
    },
    offline: {
      icon: 'wifiOff', tone: 'info',
      title: 'Нет связи',
      desc: 'Похоже, интернет пропал. Попробуй ещё раз, когда появится сеть.',
      primary: 'Повторить',
    },
    'email-required': {
      icon: 'mail', tone: 'error',
      title: 'Нужен email',
      desc: 'Для онлайн-оплаты нужен email — он указывается в фискальном чеке. Добавь его в профиле.',
      primary: 'Открыть профиль',
    },
  }[kind] ?? {
    icon: 'alertCircle', tone: 'error',
    title: 'Не удалось оплатить',
    desc: 'Что-то пошло не так при отправке платежа. Попробуй снова или обратись в зал.',
    primary: 'Попробовать снова',
  };

  return (
    <div
      style={{ position: 'absolute', inset: 0, zIndex: 240, background: 'var(--bg)' }}
      aria-live="polite"
    >
      <StatusBar />
      <div style={{
        padding: '48px 12px 4px', display: 'flex', alignItems: 'center', justifyContent: 'flex-start',
      }}>
        <button
          onClick={onClose}
          aria-label="Закрыть"
          style={{
            width: 36, height: 36, borderRadius: 999, border: 0,
            background: 'var(--surface)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <Icon name="x" size={22} color="var(--text)" strokeWidth={2.2} />
        </button>
      </div>

      <div className="state" style={{ position: 'relative', flex: 1, justifyContent: 'center', animation: 'state-in 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)' }}>
        <div className={`state-icon ${variants.tone}`}>
          <Icon name={variants.icon} size={44} color="currentColor" strokeWidth={2} />
        </div>
        <div className="state-title">{variants.title}</div>
        <div className="state-desc">{variants.desc}</div>
      </div>

      <div className="state-actions">
        <button
          ref={primaryRef}
          onClick={onRetry}
          className="btn btn-accent"
          style={{ width: '100%', height: 54 }}
        >
          {variants.primary}
        </button>
        <button
          onClick={onClose}
          className="btn btn-ghost"
          style={{ width: '100%', height: 54 }}
        >
          Закрыть
        </button>
      </div>
    </div>
  );
}
