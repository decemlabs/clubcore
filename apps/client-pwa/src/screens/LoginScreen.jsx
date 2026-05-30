/**
 * LoginScreen (Plan 71-07) — redesigned to the provided HTML template.
 *
 * Two-step real OTP login flow:
 *  1. Phone step — formatted +7 phone input → POST /api/v1/client/otp/request
 *  2. Code step — 6-box OTP input → POST /api/v1/client/otp/verify
 *     On success: useAuth().login() → success flash → navigate('/home', { replace: true })
 *     On wrong/expired code: shake + "Код не подошёл" inline + clears boxes
 *
 * The OTP code is 6 digits (backend generate_otp_code → 0..999999 zero-padded).
 * OTP arrives via Telegram (the client's linked account), not SMS.
 *
 * Anti-oracle (T-68-22): /otp/request returns a byte-identical 202 for
 * known/unknown/unlinked phones — the UI never reveals whether the phone exists.
 * /otp/request and /otp/verify are CLIENT_AUTH_EXEMPT, so a 401/422 from verify
 * is a wrong-code error, never a session_expired trigger.
 *
 * JSX file — allowJs ramp; no TS lint. Russian i18n convention.
 * The device frame / dynamic island / home indicator are rendered by the App
 * shell, so this screen renders only its own StatusBar + content.
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useOtpRequest, useOtpVerify } from '@/data';
import { useAuth } from '@/context/AuthContext.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';

const OTP_LENGTH = 6;
const RESEND_SECONDS = 60;

// ── Phone formatting: NNN NNN-NN-NN (10 national digits, +7 country) ─────────
function formatPhone(raw) {
  const d = String(raw).replace(/\D/g, '').slice(0, 10);
  let out = '';
  if (d.length > 0) out += d.slice(0, 3);
  if (d.length >= 4) out += ' ' + d.slice(3, 6);
  if (d.length >= 7) out += '-' + d.slice(6, 8);
  if (d.length >= 9) out += '-' + d.slice(8, 10);
  return { display: out, digits: d };
}

function maskPhone(digits) {
  // +7 916 ***-12-34
  if (digits.length !== 10) return '+7 ' + digits;
  return `+7 ${digits.slice(0, 3)} ***-${digits.slice(6, 8)}-${digits.slice(8, 10)}`;
}

// ── OTP boxes (6 digits) — reuses the template's box visual ──────────────────
function OtpBoxes({ onComplete, loading, error }) {
  const [digits, setDigits] = useState(() => Array(OTP_LENGTH).fill(''));
  const refs = useRef([]);

  useEffect(() => {
    refs.current[0]?.focus();
  }, []);

  // Reset boxes when parent signals an error
  useEffect(() => {
    if (error) {
      setDigits(Array(OTP_LENGTH).fill(''));
      const id = setTimeout(() => refs.current[0]?.focus(), 60);
      return () => clearTimeout(id);
    }
  }, [error]);

  function commit(next) {
    setDigits(next);
    const full = next.join('');
    if (full.length === OTP_LENGTH && !next.includes('')) onComplete(full);
  }

  function setDigit(i, v) {
    const cleaned = v.replace(/\D/g, '').slice(-1);
    const next = [...digits];
    next[i] = cleaned;
    if (cleaned && i < OTP_LENGTH - 1) refs.current[i + 1]?.focus();
    commit(next);
  }

  function onKey(i, e) {
    if (e.key === 'Backspace' && !digits[i] && i > 0) refs.current[i - 1]?.focus();
  }

  function onPaste(e) {
    const text = (e.clipboardData || window.clipboardData).getData('text');
    const pasted = text.replace(/\D/g, '').slice(0, OTP_LENGTH);
    if (!pasted) return;
    e.preventDefault();
    const next = Array(OTP_LENGTH).fill('');
    pasted.split('').forEach((d, idx) => { next[idx] = d; });
    refs.current[Math.min(pasted.length, OTP_LENGTH - 1)]?.focus();
    commit(next);
  }

  return (
    <div className={`lg-otp${error ? ' error' : ''}`}>
      {digits.map((d, i) => (
        <input
          key={i}
          ref={el => { refs.current[i] = el; }}
          value={d}
          onChange={e => setDigit(i, e.target.value)}
          onKeyDown={e => onKey(i, e)}
          onPaste={onPaste}
          type="tel"
          inputMode="numeric"
          maxLength={1}
          disabled={loading}
          className={d ? 'filled' : ''}
          aria-label={`Цифра ${i + 1}`}
        />
      ))}
    </div>
  );
}

export function LoginScreen() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [step, setStep] = useState('phone'); // 'phone' | 'code'
  const [phoneDigits, setPhoneDigits] = useState('');
  const [phoneFocused, setPhoneFocused] = useState(false);
  const [phoneError, setPhoneError] = useState(null);
  const [codeError, setCodeError] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [success, setSuccess] = useState(false);
  const [resendIn, setResendIn] = useState(0);

  const otpRequest = useOtpRequest();
  const otpVerify = useOtpVerify();

  const e164 = `+7${phoneDigits}`;
  const phoneComplete = phoneDigits.length === 10;

  // Resend countdown
  useEffect(() => {
    if (resendIn <= 0) return;
    const id = setTimeout(() => setResendIn(s => s - 1), 1000);
    return () => clearTimeout(id);
  }, [resendIn]);

  function onPhoneChange(e) {
    const { digits } = formatPhone(e.target.value);
    setPhoneDigits(digits);
    setPhoneError(null);
  }

  async function requestCode() {
    if (!phoneComplete || otpRequest.isPending) return;
    setPhoneError(null);
    try {
      await otpRequest.mutateAsync({ phone: e164 });
      // Anti-oracle: always 202, never reveals whether the phone is registered.
      setStep('code');
      setResendIn(RESEND_SECONDS);
    } catch {
      setPhoneError('Не удалось отправить код. Проверьте соединение и попробуйте ещё раз.');
    }
  }

  async function resend() {
    if (resendIn > 0 || otpRequest.isPending) return;
    try {
      await otpRequest.mutateAsync({ phone: e164 });
      setResendIn(RESEND_SECONDS);
    } catch {
      /* keep the user on the code step; surfacing nothing avoids an oracle */
    }
  }

  const handleCode = useCallback(
    async code => {
      if (verifying) return;
      setCodeError(false);
      setVerifying(true);
      try {
        await otpVerify.mutateAsync({ phone: e164, code });
        // Verified — cookies set; refresh auth context, then enter the app.
        await login();
        setSuccess(true);
        setTimeout(() => navigate('/home', { replace: true }), 600);
      } catch {
        // Wrong/expired code — NOT session_expired (verify path is auth-exempt).
        setCodeError(true);
        setTimeout(() => setCodeError(false), 700);
      } finally {
        setVerifying(false);
      }
    },
    [verifying, otpVerify, e164, login, navigate],
  );

  function back() {
    setStep('phone');
    setCodeError(false);
    setResendIn(0);
  }

  return (
    <div className="lg-screen">
      <StatusBar />

      {/* Top bar — back button only on the code step */}
      <div className="lg-topbar">
        {step === 'code' ? (
          <button className="lg-topbar-btn" type="button" aria-label="Назад" onClick={back}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
          </button>
        ) : (
          <div className="lg-topbar-spacer" />
        )}
        <div />
        <div className="lg-topbar-spacer" />
      </div>

      {/* Brand */}
      <div className="lg-brand">
        <div className="lg-brand-mark" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9v6M9 7v10M15 7v10M18 9v6M9 12h6" /></svg>
        </div>
        <div className="lg-brand-name">Мой зал</div>
      </div>

      {/* Slides */}
      <div className="lg-slides">
        {/* STEP 1 — phone */}
        <section className={`lg-slide${step === 'phone' ? ' active' : ' past'}`}>
          <div className="lg-heading">
            <div className="lg-title">Вход в приложение</div>
            <div className="lg-subtitle">
              Введите номер телефона — отправим код подтверждения в Telegram.
            </div>
          </div>

          <div className={`lg-phone-row${phoneFocused ? ' focused' : ''}${phoneError ? ' error' : ''}`}>
            <span className="lg-country">
              <span>🇷🇺</span>
              <span>+7</span>
            </span>
            <input
              className="lg-phone-input"
              type="tel"
              inputMode="numeric"
              autoComplete="tel-national"
              placeholder="000 000-00-00"
              maxLength={13}
              value={formatPhone(phoneDigits).display}
              onChange={onPhoneChange}
              onFocus={() => setPhoneFocused(true)}
              onBlur={() => setPhoneFocused(false)}
              onKeyDown={e => { if (e.key === 'Enter') requestCode(); }}
            />
          </div>
          <div className={`lg-field-hint${phoneError ? ' err' : ''}`}>
            {phoneError || 'Если номер привязан к аккаунту, придёт код в Telegram.'}
          </div>

          <div className="lg-cta-wrap">
            <button
              className="lg-btn lg-btn-accent"
              type="button"
              disabled={!phoneComplete || otpRequest.isPending}
              onClick={requestCode}
            >
              {otpRequest.isPending ? <span className="lg-spin" /> : <span>Получить код</span>}
            </button>
            <div className="lg-legal">
              Продолжая, вы соглашаетесь с{' '}
              <a href="#">условиями использования</a> и{' '}
              <a href="#">политикой конфиденциальности</a>.
            </div>
          </div>
        </section>

        {/* STEP 2 — code */}
        <section className={`lg-slide${step === 'code' ? ' active' : ''}`}>
          <div className="lg-heading">
            <div className="lg-title">Введите код из Telegram</div>
            <div className="lg-subtitle">
              Отправили {OTP_LENGTH}-значный код на<br />
              <strong>{maskPhone(phoneDigits)}</strong>
            </div>
          </div>

          {step === 'code' && (
            <OtpBoxes onComplete={handleCode} loading={verifying} error={codeError} />
          )}

          <div className={`lg-field-hint${codeError ? ' err' : ''}`}>
            {codeError
              ? 'Код не подошёл. Попробуйте ещё раз.'
              : verifying
                ? 'Проверяем…'
                : 'Код придёт в чат с ботом в Telegram.'}
          </div>

          <div className="lg-resend">
            {resendIn > 0 ? (
              <span>Отправить ещё через {resendIn} с</span>
            ) : (
              <button type="button" onClick={resend} disabled={otpRequest.isPending}>
                Отправить код ещё раз
              </button>
            )}
          </div>
        </section>
      </div>

      {/* Success flash */}
      <div className={`lg-check-flash${success ? ' show' : ''}`} aria-hidden="true">
        <div className="lg-check-circle">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5L20 7" /></svg>
        </div>
      </div>

      <style>{`
        .lg-screen {
          position: absolute; inset: 0;
          background: var(--bg); color: var(--text);
          display: flex; flex-direction: column;
          padding-top: 44px;
          font-family: var(--font);
        }
        .lg-topbar {
          height: 52px; padding: 0 14px;
          display: flex; align-items: center; justify-content: space-between;
          flex-shrink: 0;
        }
        .lg-topbar-btn {
          width: 38px; height: 38px; border-radius: 999px;
          border: 0.5px solid var(--border); background: var(--surface);
          box-shadow: var(--sh-1);
          display: inline-flex; align-items: center; justify-content: center;
          color: var(--text); cursor: pointer; padding: 0;
          transition: transform 0.12s ease, background 0.15s;
          font-family: inherit;
        }
        .lg-topbar-btn:active { transform: scale(0.94); background: var(--surface-2); }
        .lg-topbar-spacer { width: 38px; }

        .lg-brand {
          display: flex; flex-direction: column; align-items: center;
          gap: 12px; padding: 4px 24px 0;
        }
        .lg-brand-mark {
          width: 56px; height: 56px; border-radius: 18px;
          background: var(--text); color: var(--bg);
          display: inline-flex; align-items: center; justify-content: center;
          box-shadow: 0 12px 28px rgba(28, 25, 23, 0.18);
        }
        .lg-brand-name {
          font-size: 14px; font-weight: 600; letter-spacing: 0.4px;
          text-transform: uppercase; color: var(--text-3);
        }

        .lg-slides { flex: 1; position: relative; overflow: hidden; }
        .lg-slide {
          position: absolute; inset: 0;
          display: flex; flex-direction: column;
          padding: 18px 28px 0;
          transition: transform 0.34s cubic-bezier(0.32, 0.72, 0.2, 1), opacity 0.24s ease;
          opacity: 0; transform: translateX(40px); pointer-events: none;
        }
        .lg-slide.active { opacity: 1; transform: translateX(0); pointer-events: auto; }
        .lg-slide.past { opacity: 0; transform: translateX(-40px); }

        .lg-heading { text-align: center; margin-top: 14px; }
        .lg-title {
          font-size: 24px; font-weight: 700; letter-spacing: -0.5px;
          line-height: 1.2; color: var(--text);
        }
        .lg-subtitle {
          margin: 10px auto 0; max-width: 300px;
          font-size: 14px; line-height: 1.45; color: var(--text-2);
        }
        .lg-subtitle strong { color: var(--text); font-weight: 600; }

        .lg-phone-row {
          margin-top: 28px; display: flex; align-items: center; gap: 8px;
          background: var(--surface); border: 1px solid var(--border);
          border-radius: 16px; padding: 4px; box-shadow: var(--sh-1);
          transition: border-color 0.15s, box-shadow 0.15s;
        }
        .lg-phone-row.focused {
          border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft);
        }
        .lg-phone-row.error {
          border-color: var(--danger); box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.12);
        }
        .lg-country {
          display: inline-flex; align-items: center; gap: 6px;
          height: 44px; padding: 0 12px 0 14px; border-radius: 12px;
          background: var(--surface-2); font-size: 16px; font-weight: 600;
          color: var(--text); font-variant-numeric: tabular-nums;
          letter-spacing: -0.2px; flex-shrink: 0;
        }
        .lg-phone-input {
          flex: 1; appearance: none; border: 0; background: transparent;
          height: 44px; padding: 0 14px 0 4px; font-size: 17px; font-weight: 500;
          color: var(--text); font-family: inherit;
          font-variant-numeric: tabular-nums; letter-spacing: 0.2px; outline: none;
        }
        .lg-phone-input::placeholder { color: var(--text-3); font-weight: 400; }

        .lg-field-hint {
          margin-top: 10px; font-size: 12.5px; line-height: 1.4;
          color: var(--text-3); text-align: center; min-height: 18px;
        }
        .lg-field-hint.err { color: var(--danger); }

        .lg-otp {
          margin-top: 30px; display: flex; gap: 8px; justify-content: center;
        }
        .lg-otp input {
          width: 44px; height: 56px; font-size: 24px; font-weight: 600;
          text-align: center; background: var(--surface); color: var(--text);
          border: 1.5px solid var(--border-strong); border-radius: 14px;
          outline: 0; font-family: inherit; font-variant-numeric: tabular-nums;
          transition: border-color 0.15s, background 0.15s;
        }
        .lg-otp input:focus { border-color: var(--accent); }
        .lg-otp input.filled { border-color: var(--accent); }
        .lg-otp.error input { border-color: var(--danger); animation: lg-shake 0.4s; }
        @keyframes lg-shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-6px); }
          75% { transform: translateX(6px); }
        }

        .lg-resend {
          margin-top: 24px; text-align: center; font-size: 13px; color: var(--text-3);
        }
        .lg-resend button {
          border: 0; background: transparent; color: var(--accent-deep);
          font-size: 14px; font-weight: 600; cursor: pointer;
          font-family: inherit; padding: 4px 6px;
        }
        .lg-resend button:disabled { opacity: 0.5; cursor: default; }

        .lg-cta-wrap {
          margin-top: auto; padding: 16px 0 26px;
          display: flex; flex-direction: column; gap: 10px;
        }
        .lg-btn {
          appearance: none; border: 0; background: var(--text); color: var(--bg);
          height: 52px; padding: 0 22px; border-radius: var(--r-pill);
          font-size: 16px; font-weight: 600; letter-spacing: -0.2px; cursor: pointer;
          display: inline-flex; align-items: center; justify-content: center; gap: 8px;
          font-family: inherit; width: 100%;
          transition: transform 0.12s ease, opacity 0.15s ease, background 0.15s;
        }
        .lg-btn:active:not(:disabled) { transform: scale(0.98); }
        .lg-btn:disabled { opacity: 0.35; cursor: not-allowed; }
        .lg-btn-accent { background: var(--accent); color: #06120c; }
        .lg-spin {
          width: 18px; height: 18px; border-radius: 999px;
          border: 2px solid rgba(6, 18, 12, 0.25); border-top-color: #06120c;
          animation: lg-spin 0.7s linear infinite;
        }
        @keyframes lg-spin { to { transform: rotate(360deg); } }

        .lg-legal {
          font-size: 11.5px; line-height: 1.45; color: var(--text-3);
          text-align: center; padding: 0 8px;
        }
        .lg-legal a {
          color: var(--text-2); text-decoration: none;
          border-bottom: 0.5px solid var(--border-strong);
        }

        .lg-check-flash {
          position: absolute; inset: 0; z-index: 40;
          display: flex; align-items: center; justify-content: center;
          background: var(--bg); opacity: 0; pointer-events: none;
          transition: opacity 0.22s ease;
        }
        .lg-check-flash.show { opacity: 1; pointer-events: auto; }
        .lg-check-circle {
          width: 84px; height: 84px; border-radius: 999px;
          background: var(--accent); color: #06120c;
          display: inline-flex; align-items: center; justify-content: center;
          box-shadow: 0 14px 40px rgba(45, 212, 164, 0.45);
          animation: lg-pop 0.34s cubic-bezier(0.32, 0.72, 0.2, 1);
        }
        @keyframes lg-pop {
          from { transform: scale(0.4); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

export default LoginScreen;
