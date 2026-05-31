/**
 * ReceiptEmailGate — pre-checkout receipt-email collection gate (D-02/D-10).
 *
 * Rendered as a new 'email-gate' stage inside CheckoutSheet's state machine
 * (NOT a separate route — PATTERNS.md §ReceiptEmailGate).
 *
 * Flow:
 *   «Продолжить к оплате»: validates + saves email via useUpdateClientEmail →
 *     on success calls onSaved(email) → CheckoutSheet proceeds to 'paying'.
 *   «Чек не нужен»: calls onSkip() with NO PATCH → receipt sent to phone (D-10).
 *   Back chevron: calls onBack() → returns to 'review'.
 *
 * D-02: gate collected BEFORE the ЮKassa redirect.
 * D-03: gate is skipped when clientMe.email is already present (CheckoutSheet decides).
 * D-10: «Чек не нужен» is a legal 54-ФЗ path — phone is always present (OTP invariant).
 * T-999.5-17: client regex is UX-only; server re-validates (Plan 02 authoritative).
 */
import React from 'react';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { useUpdateClientEmail } from '@/data';

// D-10: four suggested domains per UI-SPEC §"Screen 2: Domain suggestion chips"
const DOMAINS = ['gmail.com', 'yandex.ru', 'mail.ru', 'icloud.com'];

// T-999.5-17: UX validation — server is authoritative for format enforcement
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const validate = (v) => EMAIL_RE.test(v);

export function ReceiptEmailGate({ onSaved, onSkip, onBack }) {
  const [email, setEmail] = React.useState('');
  const [focused, setFocused] = React.useState(false);
  const [error, setError] = React.useState(false);
  const [saveError, setSaveError] = React.useState(null);
  const [saving, setSaving] = React.useState(false);
  const inputRef = React.useRef(null);

  const updateEmail = useUpdateClientEmail();

  // ─── Domain chip logic ────────────────────────────────────────────────────
  const atIdx = email.indexOf('@');
  const showChips = atIdx > 0 && !email.slice(atIdx + 1).includes('.');
  const domainPart = atIdx > 0 ? email.slice(atIdx + 1) : '';
  const chips = DOMAINS.filter(d => d.startsWith(domainPart));

  const applyDomain = (d) => {
    setEmail(email.slice(0, atIdx + 1) + d);
    setError(false);
    inputRef.current?.focus();
  };

  // ─── Blur validation ──────────────────────────────────────────────────────
  const validateOnBlur = () => {
    if (email && !validate(email)) setError(true);
  };

  // ─── Primary: save email → proceed ───────────────────────────────────────
  const handleSaveEmail = async () => {
    if (!validate(email) || saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      await updateEmail.mutateAsync({ email });
      onSaved(email);
    } catch (_e) {
      setSaveError('Не удалось сохранить почту. Попробуйте снова.');
    } finally {
      setSaving(false);
    }
  };

  // ─── Secondary: skip (no PATCH — D-10 phone fallback) ────────────────────
  const handleSkip = () => {
    onSkip();
  };

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 240,
      background: 'var(--bg)', display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />

      {/* ── Topbar ─────────────────────────────────────────────────────────── */}
      <div style={{
        padding: '48px 12px 4px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <button
          onClick={onBack}
          aria-label="Назад"
          className="topbar-btn"
          style={{ width: 38, height: 38 }}
        >
          <Icon name="chevronLeft" size={22} color="var(--text)" strokeWidth={2.2} />
        </button>
        <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: -0.2 }}>Чек об оплате</span>
        <div style={{ width: 38 }} />
      </div>

      {/* ── Scrollable body ─────────────────────────────────────────────────── */}
      <div className="scroller" style={{ padding: '4px 28px 0', flex: 1 }}>

        {/* Spot illustration — aria-hidden (decorative) */}
        <div aria-hidden="true" style={{
          position: 'relative',
          width: 188, height: 188,
          margin: '8px auto 0',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          {/* Halo */}
          <div style={{
            position: 'absolute', inset: 0, borderRadius: '50%',
            background: 'radial-gradient(circle at 52% 52%, color-mix(in oklab, var(--accent) 22%, transparent) 0%, transparent 68%)',
          }} />
          {/* Outer dashed ring */}
          <div style={{
            position: 'absolute', width: 198, height: 198,
            borderRadius: '50%',
            border: '1.5px dashed color-mix(in oklab, var(--accent) 24%, transparent)',
            top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
          }} />
          {/* Inner dashed ring */}
          <div style={{
            position: 'absolute', width: 150, height: 150,
            borderRadius: '50%',
            border: '1.5px dashed color-mix(in oklab, var(--accent) 42%, transparent)',
            top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
          }} />
          {/* Receipt card */}
          <div style={{
            width: 116, height: 136,
            background: 'var(--surface)',
            border: '0.5px solid var(--border)',
            borderRadius: '8px 8px 0 0',
            transform: 'rotate(-5deg)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
            padding: '12px 10px',
            display: 'flex', flexDirection: 'column', gap: 6,
            flexShrink: 0,
            animation: 'scene-in 0.46s cubic-bezier(0.32, 1.6, 0.32, 1)',
          }}>
            {/* Receipt line-items skeleton */}
            {[1, 2, 3].map(i => (
              <div key={i} style={{
                height: 8, borderRadius: 4,
                background: i === 1 ? 'var(--border-strong)' : 'var(--border)',
                width: i === 1 ? '80%' : i === 2 ? '60%' : '70%',
              }} />
            ))}
            <div style={{ flex: 1 }} />
            <div style={{ height: 1, background: 'var(--border)', marginBottom: 4 }} />
            <div style={{
              height: 10, borderRadius: 4,
              background: 'color-mix(in oklab, var(--accent) 40%, var(--border))',
              width: '90%',
            }} />
          </div>
          {/* @ badge */}
          <div style={{
            position: 'absolute',
            bottom: 16, right: 18,
            width: 48, height: 48,
            borderRadius: '50%',
            background: 'var(--accent)',
            border: '4px solid var(--bg)',
            boxShadow: '0 12px 26px rgba(15,155,118,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            animation: 'pop 0.5s 0.1s cubic-bezier(0.32, 1.6, 0.32, 1) both',
          }}>
            <Icon name="mail" size={22} color="#06120c" strokeWidth={2.2} />
          </div>
          {/* Floating sparks */}
          {[
            { top: 14, left: 10, delay: '0s', size: 20 },
            { top: 20, right: 14, delay: '0.6s', size: 16 },
            { bottom: 30, left: 20, delay: '1.1s', size: 14 },
            { bottom: 14, right: 32, delay: '0.3s', size: 18 },
          ].map((sp, i) => (
            <div key={i} style={{
              position: 'absolute',
              top: sp.top, left: sp.left, right: sp.right, bottom: sp.bottom,
              width: sp.size, height: sp.size,
              borderRadius: '50%',
              background: 'color-mix(in oklab, var(--accent) 30%, var(--border))',
              animation: `float 3.4s ${sp.delay} ease-in-out infinite`,
            }} />
          ))}
        </div>

        {/* Heading + subtitle */}
        <div style={{ marginTop: 20, textAlign: 'center' }}>
          <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: -0.5, lineHeight: 1.2 }}>
            Куда отправить чек?
          </div>
          <div style={{ fontSize: 14.5, fontWeight: 400, lineHeight: 1.5, color: 'var(--text-2)', marginTop: 8 }}>
            Укажите почту — на неё придёт электронный кассовый чек об оплате абонемента.
          </div>
        </div>

        {/* Email field */}
        <div style={{ marginTop: 20 }}>
          <div
            className={`field${focused ? ' focused' : ''}${error ? ' error' : ''}`}
            style={{ height: 56, display: 'flex', alignItems: 'center', gap: 8, padding: '0 12px' }}
          >
            <Icon
              name="mail"
              size={20}
              color={focused ? 'var(--accent-deep)' : 'var(--text-3)'}
            />
            <input
              ref={inputRef}
              type="email"
              inputMode="email"
              autoComplete="email"
              autoCapitalize="off"
              spellCheck={false}
              placeholder="you@example.com"
              value={email}
              onChange={e => { setEmail(e.target.value); setError(false); setSaveError(null); }}
              onFocus={() => setFocused(true)}
              onBlur={() => { setFocused(false); validateOnBlur(); }}
              style={{
                flex: 1, border: 0, outline: 0, background: 'transparent',
                color: 'var(--text)', fontSize: 17, fontWeight: 500,
                letterSpacing: 0.1, fontFamily: 'inherit',
              }}
            />
            {email && (
              <button
                onClick={() => { setEmail(''); setError(false); setSaveError(null); inputRef.current?.focus(); }}
                aria-label="Очистить"
                style={{
                  width: 24, height: 24, borderRadius: 999,
                  background: 'var(--surface-2)', border: 0, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Icon name="x" size={14} color="var(--text-3)" />
              </button>
            )}
          </div>

          {/* Field hint */}
          <div
            role={error ? 'alert' : undefined}
            style={{
              fontSize: 12.5,
              color: error ? 'var(--danger)' : 'var(--text-3)',
              marginTop: 6,
            }}
          >
            {error
              ? 'Похоже, в адресе опечатка. Проверьте почту.'
              : 'Чек придёт в течение пары минут после оплаты.'}
          </div>
        </div>

        {/* Domain suggestion chips */}
        {showChips && chips.length > 0 && (
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 7,
            justifyContent: 'center', marginTop: 12,
          }}>
            {chips.map(d => (
              <button
                key={d}
                onClick={() => applyDomain(d)}
                className="domain-chip"
              >
                @{d}
              </button>
            ))}
          </div>
        )}

        {/* 54-ФЗ reassurance note */}
        <div className="note" style={{ marginTop: 20 }}>
          <div className="n-header">
            <div className="n-shield">
              <Icon name="shield" size={14} color="var(--accent-deep)" strokeWidth={2} />
            </div>
            <span className="n-title">Почта в безопасности</span>
          </div>
          <div className="n-row">
            <Icon name="check" size={14} color="var(--accent-deep)" strokeWidth={2.5} />
            <span>Используем только для чека по <b>54-ФЗ</b></span>
          </div>
          <div className="n-row">
            <Icon name="check" size={14} color="var(--accent-deep)" strokeWidth={2.5} />
            <span>Без рекламных рассылок и передачи третьим лицам</span>
          </div>
        </div>

        {/* Network save error */}
        {saveError && (
          <div role="alert" style={{
            fontSize: 12.5, color: 'var(--danger)',
            textAlign: 'center', marginTop: 10,
          }}>
            {saveError}
          </div>
        )}

        <div style={{ height: 130 }} />
      </div>

      {/* ── Sticky CTA wrap ─────────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        padding: '16px 16px 26px',
        background: 'color-mix(in oklab, var(--bg) 88%, transparent)',
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
        borderTop: '0.5px solid var(--border)',
        display: 'flex', flexDirection: 'column', gap: 6,
      }}>
        {/* Primary: save email + proceed */}
        <button
          onClick={handleSaveEmail}
          disabled={!validate(email) || saving}
          className="btn btn-accent"
          style={{
            width: '100%', height: 54,
            opacity: (!validate(email) || saving) ? 0.4 : 1,
            cursor: (!validate(email) || saving) ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          {saving ? (
            <span style={{
              width: 18, height: 18, borderRadius: 999,
              border: '2px solid rgba(6,18,12,0.25)',
              borderTopColor: '#06120c',
              animation: 'ptr-spin 0.7s linear infinite',
              display: 'inline-block',
            }} />
          ) : 'Продолжить к оплате'}
        </button>

        {/* Secondary: skip (D-10 phone fallback — no PATCH) */}
        <button
          onClick={handleSkip}
          className="btn btn-ghost"
          style={{ height: 44, width: '100%', fontSize: 14, fontWeight: 500 }}
        >
          Чек не нужен
        </button>
      </div>
    </div>
  );
}
