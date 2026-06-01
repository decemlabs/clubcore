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

        {/* Spot illustration: fiscal receipt → email (aria-hidden, decorative).
            Full-width, mirrors Email-for-Receipt mockup .illus 1:1. */}
        <div aria-hidden="true" style={{
          position: 'relative', width: '100%', height: 166,
          margin: '2px 0 4px', flexShrink: 0,
        }}>
          {/* Branded halo */}
          <div style={{
            position: 'absolute', left: '50%', top: '52%', transform: 'translate(-50%, -50%)',
            width: 188, height: 188, borderRadius: '50%',
            background: 'radial-gradient(circle, color-mix(in oklab, var(--accent) 18%, transparent) 0%, transparent 62%)',
          }} />
          {/* Outer dashed ring */}
          <div style={{
            position: 'absolute', left: '50%', top: '52%', transform: 'translate(-50%, -50%)',
            width: 198, height: 198, borderRadius: '50%',
            border: '1.5px dashed color-mix(in oklab, var(--accent) 45%, transparent)', opacity: 0.28,
          }} />
          {/* Inner dashed ring */}
          <div style={{
            position: 'absolute', left: '50%', top: '52%', transform: 'translate(-50%, -50%)',
            width: 150, height: 150, borderRadius: '50%',
            border: '1.5px dashed color-mix(in oklab, var(--accent) 45%, transparent)', opacity: 0.5,
          }} />

          {/* Floating sparks — small accent squares + dots */}
          {[
            { pos: { left: 30, top: 18 }, w: 9, h: 9, rot: '18deg', round: 3, bg: 'var(--accent-deep)', delay: '0s' },
            { pos: { right: 36, top: 30 }, w: 7, h: 7, rot: '0deg', round: '50%', bg: 'var(--accent)', delay: '0.6s' },
            { pos: { right: 58, bottom: 22 }, w: 6, h: 6, rot: '-12deg', round: 3, bg: 'var(--accent-deep)', delay: '1.1s' },
            { pos: { left: 46, bottom: 26 }, w: 8, h: 8, rot: '0deg', round: '50%', bg: 'var(--accent)', delay: '0.3s' },
          ].map((sp, i) => (
            <span key={i} style={{
              position: 'absolute', ...sp.pos,
              width: sp.w, height: sp.h, borderRadius: sp.round,
              background: sp.bg, transform: `rotate(${sp.rot})`,
              animation: `float 3.4s ${sp.delay} ease-in-out infinite`,
            }} />
          ))}

          {/* Receipt slip — barbell mark, dashed separators, torn perforated edge, total row */}
          <div style={{
            position: 'absolute', left: '50%', top: '50%',
            transform: 'translate(-50%, -50%) rotate(-5deg)',
            width: 116, background: 'var(--surface)',
            border: '0.5px solid var(--border)',
            boxShadow: '0 14px 30px rgba(28,25,23,0.12), 0 2px 6px rgba(28,25,23,0.05)',
            borderRadius: '10px 10px 0 0',
            padding: '16px 15px 18px',
            display: 'flex', flexDirection: 'column', gap: 8, zIndex: 2,
            WebkitMask: 'linear-gradient(#000 0 0) top / 100% calc(100% - 7px) no-repeat, radial-gradient(circle 5px at 50% 100%, #0000 96%, #000) bottom left / 14px 14px repeat-x',
            mask: 'linear-gradient(#000 0 0) top / 100% calc(100% - 7px) no-repeat, radial-gradient(circle 5px at 50% 100%, #0000 96%, #000) bottom left / 14px 14px repeat-x',
            animation: 'scene-in 0.46s cubic-bezier(0.32, 1.6, 0.32, 1)',
          }}>
            {/* Header: barbell mark + title bar, dashed underline */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              paddingBottom: 8, borderBottom: '1.5px dashed var(--border-strong)',
            }}>
              <span style={{
                width: 18, height: 18, borderRadius: 6,
                background: 'var(--text)', color: 'var(--bg)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <Icon name="barbell" size={11} color="var(--bg)" strokeWidth={2.2} />
              </span>
              <span style={{ height: 5, width: 46, borderRadius: 999, background: 'var(--border-strong)' }} />
            </div>
            {/* Line items (w1 / w3 / w2) */}
            <span style={{ height: 4, width: '100%', borderRadius: 999, background: 'var(--border)' }} />
            <span style={{ height: 4, width: '86%', borderRadius: 999, background: 'var(--border)' }} />
            <span style={{ height: 4, width: '72%', borderRadius: 999, background: 'var(--border)' }} />
            {/* Total: dashed top, label + accent amount */}
            <div style={{
              marginTop: 3, paddingTop: 8,
              borderTop: '1.5px dashed var(--border-strong)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <span style={{ height: 5, width: 26, borderRadius: 999, background: 'var(--border-strong)' }} />
              <span style={{ height: 7, width: 38, borderRadius: 999, background: 'var(--accent)' }} />
            </div>
          </div>

          {/* @ envelope badge — clipped to receipt's lower-right corner */}
          <div style={{
            position: 'absolute', right: 40, bottom: 30,
            width: 58, height: 58, borderRadius: '50%',
            background: 'var(--accent)', color: '#06120c',
            border: '4px solid var(--bg)',
            boxShadow: '0 12px 26px rgba(15,155,118,0.4)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', zIndex: 3,
            animation: 'pop 0.5s 0.1s cubic-bezier(0.32, 1.6, 0.32, 1) both',
          }}>
            <Icon name="mail" size={30} color="#06120c" strokeWidth={2} />
          </div>
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
