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

// ─── Deferred-feature scaffolding (BUILT, HIDDEN) ─────────────────────────
// Two UI blocks are fully built but gated OFF here. To reveal one, flip its flag.
//
//  • recommendedPromo — a one-tap chip that applies RECOMMENDED_PROMO.code through
//    the existing server-authoritative promo flow (handlePromoApply). When the flag
//    is true AND the code is a real, server-known promo, it works end-to-end.
//
//  • clubBonuses — the "Списать бонусы" toggle. The UI is built, but REAL point
//    redemption is NOT wired: it requires the deferred loyalty backend (server-
//    authoritative price override via price_override_kopecks, a balance source, and
//    webhook redemption). See 260601-sxf-CONTEXT.md <deferred>. While the flag is on
//    the toggle renders, but it MUST NOT mutate `total`/`discount` client-side (D-06)
//    until that backend lands — flipping it true here only reveals the UI.
const CHECKOUT_FEATURE_FLAGS = {
  recommendedPromo: true,
  clubBonuses:      false,
};
// Placeholder until a real "recommended promo" source exists on the backend.
const RECOMMENDED_PROMO = { code: 'FIT15', label: '−15%' };
// Placeholder loyalty display — replace with real balance data when the backend lands.
const BONUS_PLACEHOLDER = { balance: 1080, toGold: 220 };

// ─── Barbell SVG watermark (inline, accent-colored, aria-hidden) ─────────
function BarbellMark() {
  return (
    <svg
      className="co-pass-mark"
      viewBox="0 0 200 120"
      fill="currentColor"
      aria-hidden="true"
    >
      <rect x="40" y="54" width="120" height="12" rx="6" />
      <rect x="52" y="44" width="9" height="32" rx="4" />
      <rect x="139" y="44" width="9" height="32" rx="4" />
      <rect x="30" y="38" width="14" height="44" rx="6" />
      <rect x="156" y="38" width="14" height="44" rx="6" />
      <rect x="18" y="48" width="11" height="24" rx="5" />
      <rect x="171" y="48" width="11" height="24" rx="5" />
    </svg>
  );
}

// ─── Count-up hook — animates a kopeck value to a formatted money string ──
// Respects prefers-reduced-motion: skips tween and snaps immediately.
function useCountUp(targetKopecks, deps) {
  const [display, setDisplay] = React.useState(() => formatMoney(targetKopecks));
  const rafRef = React.useRef(null);
  const prevRef = React.useRef(targetKopecks);

  React.useEffect(() => {
    const prefersReduced =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReduced) {
      setDisplay(formatMoney(targetKopecks));
      prevRef.current = targetKopecks;
      return;
    }

    const from = prevRef.current;
    const to = targetKopecks;
    const dur = 440;
    let start = null;

    if (rafRef.current) cancelAnimationFrame(rafRef.current);

    function step(t) {
      if (start === null) start = t;
      const pr = Math.min(1, (t - start) / dur);
      const v = from + (to - from) * (1 - Math.pow(1 - pr, 3));
      setDisplay(formatMoney(Math.round(v)));
      if (pr < 1) {
        rafRef.current = requestAnimationFrame(step);
      } else {
        setDisplay(formatMoney(to));
        prevRef.current = to;
      }
    }

    rafRef.current = requestAnimationFrame(step);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return display;
}

export const CheckoutSheet = ({ ctx, onClose, onDone, forceOutcome }) => {
  const [stage, setStage] = React.useState('review'); // 'review' | 'email-gate' | 'paying' | 'error'
  const [errorKind, setErrorKind] = React.useState(null); // 'payment' | 'slot-busy' | 'offline' | 'email-required'
  const [promoCode, setPromoCode] = React.useState('');
  const [promoLoading, setPromoLoading] = React.useState(false);
  const [promoError, setPromoError] = React.useState(null); // error code string | null
  const [promoResult, setPromoResult] = React.useState(null); // { discountKopecks, newAmountKopecks, discountType } | null

  // Local in-sheet toast state
  const [toast, setToast] = React.useState(null); // { message: string } | null
  const toastTimerRef = React.useRef(null);

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

  // ─── Toast helper ───────────────────────────────────────────────────────
  const showToast = (message) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ message });
    toastTimerRef.current = setTimeout(() => setToast(null), 2600);
  };

  // ─── Promo "Применить" handler ──────────────────────────────────────────
  const handlePromoApply = async (codeArg) => {
    // codeArg lets the (hidden) recommended-promo chip apply a configured code.
    // onClick passes a React event, not a string — the typeof guard ignores it
    // and falls back to the live input, so existing call sites are unaffected.
    const code = (typeof codeArg === 'string' ? codeArg : promoCode).trim();
    if (!code || promoLoading) return;
    setPromoLoading(true);
    setPromoError(null);
    try {
      const result = await promoValidate.mutateAsync({ code, kind: ctx.kind, planId: ctx.planId });
      // WR-03 fix: snapshot the validated code string into promoResult so that
      // appliedPromoCode at checkout time uses the validated code, not the live
      // input state (which is disabled after validation but fragile as a correctness invariant).
      setPromoResult({ ...result, _validatedCode: code });
      setPromoCode(code);
      showToast(`Промокод ${code} применён`);
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
    showToast('Промокод удалён');
  };

  // WR-02 (Phase 999.5): single checkout-launch helper. Previously the
  // mutateAsync(...)-then-redirect block (plus the forceOutcome / !ctx.planId demo
  // guards) was copy-pasted across startPay, onSaved, and onSkip — and the gate
  // copies omitted the demo guards, so a falsy ctx.planId on the gate path called
  // mutateAsync({ planId: undefined }) instead of falling back. Centralizing here
  // gives all three call sites identical guards + error handling.
  const launchCheckout = async () => {
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

  const startPay = async () => {
    // D-02/D-03: if email absent, show receipt-email gate before proceeding.
    // Skip check when already in email-gate (gate calls startPay after saving).
    if (!clientMe?.email && stage !== 'email-gate') {
      setStage('email-gate');
      return;
    }

    await launchCheckout();
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
          // WR-02: launchCheckout owns the demo guards + redirect + error handling.
          void launchCheckout();
        }}
        onSkip={() => {
          // D-10: no email collected; receipt goes to phone. Proceed to pay.
          // WR-02: launchCheckout owns the demo guards + redirect + error handling.
          void launchCheckout();
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
    <ReviewStage
      ctx={ctx}
      total={total}
      discount={discount}
      promoCode={promoCode}
      setPromoCode={setPromoCode}
      promoLoading={promoLoading}
      promoError={promoError}
      setPromoError={setPromoError}
      promoResult={promoResult}
      handlePromoApply={handlePromoApply}
      handlePromoRemove={handlePromoRemove}
      startPay={startPay}
      onClose={onClose}
      forceOutcome={forceOutcome}
      toast={toast}
      showToast={showToast}
    />
  );
};

// ─── Review stage — v2 layout ───────────────────────────────────────────────
function ReviewStage({
  ctx,
  total,
  discount,
  promoCode,
  setPromoCode,
  promoLoading,
  promoError,
  setPromoError,
  promoResult,
  handlePromoApply,
  handlePromoRemove,
  startPay,
  onClose,
  forceOutcome,
  toast,
  showToast,
}) {
  // Count-up for pay-bar total — animates whenever `total` changes
  const totalDisplay = useCountUp(total, [total]);

  // Savings bar widths
  const savePct = total < ctx.amount
    ? Math.round(discount / ctx.amount * 100)
    : 0;
  const payPct = 100 - savePct;

  // Eyebrow label from ctx.kind
  const eyebrow = ctx.kind === 'pt' ? 'Тренировки' : 'Абонемент';

  // Pass headline price (matches the «К оплате v2» reference: "X ₽ /мес").
  // For a subscription the hero shows the per-month rate; the summary below shows
  // the period total. PT packages show the total with no "/мес" suffix.
  const isSub = ctx.kind !== 'pt';
  const subMonths = isSub ? (parseInt(String(ctx.subtitle ?? ''), 10) || 1) : 0;
  const passPriceKopecks = isSub && subMonths > 0 ? Math.round(ctx.amount / subMonths) : ctx.amount;

  // Hidden "Списать бонусы" toggle — local UI state only. Does NOT affect
  // total/discount (D-06): real redemption needs the deferred loyalty backend.
  const [bonusOn, setBonusOn] = React.useState(false);

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

      {/* Scrollable body */}
      <div className="scroller" style={{ padding: '4px 18px calc(120px + env(safe-area-inset-bottom))', display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* ── 1. Membership-pass hero ── */}
        <div className="co-pass">
          <BarbellMark />

          <div className="co-pass-row">
            {/* Brand is text-only per the «К оплате v2» reference — no logo square */}
            <div className="co-brand">
              <span className="co-brand-name">
                Мой зал
                <span>Клубная карта</span>
              </span>
            </div>
            {/* Duration pill — only render if ctx.subtitle is non-empty */}
            {ctx.subtitle ? (
              <span className="co-pass-pill">
                <span className="co-pill-dot" aria-hidden="true" />
                {ctx.subtitle}
              </span>
            ) : null}
          </div>

          <div className="co-pass-body">
            <div className="co-pass-eyebrow">{eyebrow}</div>
            <div className="co-pass-name">{ctx.title}</div>
            {/* Meta line: real plan features are not exposed by /client/plans
                (the reference's "Зал 24/7 · Сауна · Групповые" is mock content),
                so omit rather than duplicate the duration pill. */}
          </div>

          <div className="co-pass-foot">
            <div>
              <div className="co-pass-price-lbl">Стоимость</div>
              {/* Per-month headline for subs (reference "X ₽ /мес"); total for PT.
                  Never the discounted total (D-06) — discounts show in the summary. */}
              <div className="co-pass-price">
                {formatMoney(passPriceKopecks)}
                {isSub ? <small> /мес</small> : null}
              </div>
            </div>
            <span className="co-pass-secure">
              {/* Shield icon inline SVG — no Icon component name for "shield-check" */}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" />
                <path d="M9.5 12l1.7 1.7 3.3-3.4" />
              </svg>
              Гарантия возврата
            </span>
          </div>
        </div>

        {/* ── 2. Promo coupon ── */}
        <div className="co-sec-label">Промокод<span className="co-ln" /></div>

        {/* Recommended-promo chip — BUILT, HIDDEN (CHECKOUT_FEATURE_FLAGS.recommendedPromo).
            Applies a configured code via the existing server-authoritative flow. */}
        {CHECKOUT_FEATURE_FLAGS.recommendedPromo && !promoResult && (
          <div className="co-promo-rec">
            <button
              type="button"
              className="co-rec-chip"
              onClick={() => handlePromoApply(RECOMMENDED_PROMO.code)}
              disabled={promoLoading}
            >
              <span className="co-rec-tag">{RECOMMENDED_PROMO.label}</span>
              Применить {RECOMMENDED_PROMO.code}
            </button>
          </div>
        )}

        <PromoSection
          promoCode={promoCode}
          setPromoCode={setPromoCode}
          promoLoading={promoLoading}
          promoError={promoError}
          setPromoError={setPromoError}
          promoResult={promoResult}
          discount={discount}
          handlePromoApply={handlePromoApply}
          handlePromoRemove={handlePromoRemove}
        />

        {/* ── 2b. Club bonuses ── BUILT, HIDDEN (CHECKOUT_FEATURE_FLAGS.clubBonuses).
            UI only — toggling does NOT change the total (D-06). Real point redemption
            requires the deferred loyalty backend (see 260601-sxf-CONTEXT.md <deferred>). */}
        {CHECKOUT_FEATURE_FLAGS.clubBonuses && (
          <>
            <div className="co-sec-label">Бонусы клуба<span className="co-ln" /></div>
            <div className="co-bonus">
              <div className="co-bonus-ring" aria-hidden="true">
                <svg viewBox="0 0 62 62">
                  <circle className="co-bonus-track" cx="31" cy="31" r="25.5" />
                  <circle className="co-bonus-prog" cx="31" cy="31" r="25.5" />
                </svg>
                <span className="co-bonus-coin">₽</span>
              </div>
              <div className="co-bonus-text">
                <div className="co-bonus-title">Списать бонусы</div>
                <div className="co-bonus-sub">
                  На счёте <b>{BONUS_PLACEHOLDER.balance.toLocaleString('ru-RU')}</b>
                  {' · '}до Gold осталось <b>{BONUS_PLACEHOLDER.toGold}</b>
                </div>
              </div>
              <button
                type="button"
                className="co-bonus-switch"
                role="switch"
                aria-checked={bonusOn}
                aria-label="Списать бонусы"
                onClick={() => {
                  // TODO(loyalty-phase): wire server-authoritative redemption here.
                  // MUST keep `total`/`discount` server-derived — do NOT subtract bonuses
                  // on the client (D-06). For now this only flips local UI state.
                  const next = !bonusOn;
                  setBonusOn(next);
                  showToast(next ? 'Бонусы будут списаны' : 'Списание бонусов отменено');
                }}
              >
                <span className="co-bonus-knob" />
              </button>
            </div>
          </>
        )}

        {/* ── 3. Summary card ── */}
        <div className="co-sec-label">Итог<span className="co-ln" /></div>
        <div className="co-sum">
          {/* Base row */}
          <div className="co-sum-row">
            <span>{ctx.title}</span>
            <span className="co-sv">{formatMoney(ctx.amount)}</span>
          </div>

          {/* Discount row — only when promo applied */}
          {discount > 0 && (
            <div className="co-sum-row discount">
              <span className="co-sl-tag">
                Промокод{' '}
                <span className="co-mini">{promoResult?._validatedCode ?? promoCode}</span>
              </span>
              <span className="co-sv">−{formatMoney(discount)}</span>
            </div>
          )}

          {/* Total row */}
          <div className="co-sum-total">
            <div className="co-tt">
              <span className="co-tl">
                К оплате
                <small>Все включено</small>
              </span>
              <span className="co-amount">{totalDisplay}</span>
            </div>

            {/* Savings bar — only when there is a real discount */}
            <div className={`co-save-wrap${total < ctx.amount ? ' show' : ''}`}>
              <div className="co-save-bar">
                <span
                  className="co-pay-seg"
                  style={{ width: `${payPct}%` }}
                />
                <span
                  className="co-save-seg"
                  style={{ width: `${savePct}%` }}
                />
              </div>
              <div className="co-save-legend">
                <span className="co-sl">
                  <span className="co-dotm" aria-hidden="true" />
                  Ваша выгода
                </span>
                <span className="co-sl">
                  <b>{formatMoney(discount)}</b>
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── 4. Method plate ── */}
        <div className="co-sec-label">Способ оплаты<span className="co-ln" /></div>
        {/* D-01: static ЮKassa plate — no wallet/picker (cursor: default) */}
        <div
          className="co-method"
          role="button"
          tabIndex={0}
          aria-label="Способ оплаты: ЮKassa"
          onClick={() => showToast('ЮKassa · Способ оплаты подтверждён')}
          onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') showToast('ЮKassa · Способ оплаты подтверждён'); }}
          style={{ cursor: 'default' }}
        >
          <span className="co-method-logo" aria-hidden="true">Ю</span>
          <div className="co-method-text">
            <div className="co-method-name">ЮKassa</div>
            <div className="co-method-sub">Карта, СБП, Мир</div>
          </div>
          <span className="co-method-lock" aria-hidden="true">
            <Icon name="lock" size={18} color="var(--text-3)" strokeWidth={2} />
          </span>
        </div>

        {/* Spacer for sticky paybar */}
        <div style={{ height: 110 }} />
      </div>

      {/* ── Sticky pay bar ── */}
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
          Оплатить · {totalDisplay}
        </button>
        <div className="t-mini" style={{
          textAlign: 'center', marginTop: 8, color: 'var(--text-3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
        }}>
          <Icon name="lock" size={11} color="var(--text-3)" />
          Защищено · ЮKassa
        </div>
      </div>

      {/* ── In-sheet toast ── */}
      <div
        className={`co-toast${toast ? ' show' : ''}`}
        aria-live="polite"
        aria-atomic="true"
      >
        <span className="co-toast-ic" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12l5 5L20 7" />
          </svg>
        </span>
        <span className="co-toast-tx">{toast?.message}</span>
      </div>
    </div>
  );
}

// ─── Promo section — coupon ticket with idle/applied/error states ────────────
function PromoSection({
  promoCode,
  setPromoCode,
  promoLoading,
  promoError,
  setPromoError,
  promoResult,
  discount,
  handlePromoApply,
  handlePromoRemove,
}) {
  const isApplied = !!promoResult;
  const hasInput = promoCode.trim().length > 0;

  const couponClass = [
    'co-coupon',
    promoError ? 'error' : '',
    isApplied ? 'applied' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={couponClass}>
      <span className="co-coupon-glow" aria-hidden="true" />

      {/* Idle / error input view */}
      {!isApplied && (
        <>
          <div className="co-field">
            <span className="co-tag-ic" aria-hidden="true">
              {/* Tag icon SVG */}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0l-6.2-6.2A2 2 0 0 1 4 13V5a1 1 0 0 1 1-1h8a2 2 0 0 1 1.4.6l6.2 6.2a2 2 0 0 1 0 2.6z" />
                <circle cx="8.5" cy="8.5" r="1.3" fill="currentColor" stroke="none" />
              </svg>
            </span>
            <div className="co-input-wrap">
              <div className="co-input-lbl">Есть промокод?</div>
              <input
                type="text"
                inputMode="text"
                autoComplete="off"
                autoCapitalize="characters"
                spellCheck={false}
                placeholder="Промокод"
                maxLength={16}
                value={promoCode}
                onChange={e => {
                  setPromoCode(e.target.value.toUpperCase());
                  if (promoError) setPromoError(null);
                }}
                onKeyDown={e => { if (e.key === 'Enter') handlePromoApply(); }}
                aria-label="Поле промокода"
              />
            </div>
            <button
              type="button"
              className={`co-promo-apply${hasInput && !promoLoading ? ' ready' : ''}`}
              onClick={handlePromoApply}
              disabled={!promoCode || promoLoading}
              aria-label="Применить промокод"
            >
              {promoLoading
                ? <span className="ptr-spin" style={{ width: 14, height: 14 }} />
                : 'Применить'
              }
            </button>
          </div>

          {/* Per-reason error (D-09) */}
          {promoError && (
            <div
              role="alert"
              className="co-promo-hint err"
            >
              {PROMO_ERROR_MESSAGES[promoError] ?? 'Промокод не найден'}
            </div>
          )}
        </>
      )}

      {/* Applied view */}
      {isApplied && (
        <div className="co-applied-view">
          <span className="co-av-check" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12l5 5L20 7" />
            </svg>
          </span>
          <div className="co-av-text">
            <div className="co-av-code">{promoResult._validatedCode}</div>
            <div className="co-av-desc">
              Скидка −{formatMoney(discount)} применена
            </div>
          </div>
          <button
            type="button"
            className="co-av-remove"
            onClick={handlePromoRemove}
            aria-label="Удалить промокод"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}

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
