/**
 * LoginScreen (Plan 71-07).
 *
 * Two-step real OTP login flow:
 *  1. Phone step — input + "Получить код" → POST /api/v1/client/otp/request
 *  2. Code step — 4-box OTP input → POST /api/v1/client/otp/verify
 *     On success: calls useAuth().login() then navigate('/home', { replace: true })
 *     On wrong/expired code: shows "Код не подошёл" inline + clears boxes
 *
 * OTP paths are CLIENT_AUTH_EXEMPT — a 401/422 from verify is a wrong-code error,
 * never a session_expired trigger (anti-oracle, T-68-22).
 *
 * JSX file — allowJs ramp; no TS lint. Russian i18n convention.
 */
import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useOtpRequest, useOtpVerify } from '@/data'
import { useAuth } from '@/context/AuthContext.jsx'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatPhone(raw) {
  // Minimal formatting: accept digits/spaces/dashes/+
  return raw.trim()
}

// ---------------------------------------------------------------------------
// OTP 4-box input (reuses visual pattern from SmsVerifySheet in flows.jsx)
// ---------------------------------------------------------------------------

function OtpBoxes({ onComplete, loading, error }) {
  const [digits, setDigits] = useState(['', '', '', ''])
  const refs = [useRef(), useRef(), useRef(), useRef()]

  useEffect(() => {
    refs[0].current?.focus()
  }, [])

  // Reset boxes when parent clears on error
  useEffect(() => {
    if (error) {
      setDigits(['', '', '', ''])
      setTimeout(() => refs[0].current?.focus(), 50)
    }
  }, [error])

  function setDigit(i, v) {
    const cleaned = v.replace(/\D/g, '').slice(-1)
    const next = [...digits]
    next[i] = cleaned
    setDigits(next)
    if (cleaned && i < 3) refs[i + 1].current?.focus()
    const full = next.join('')
    if (full.length === 4) {
      onComplete(full)
    }
  }

  function onKey(i, e) {
    if (e.key === 'Backspace' && !digits[i] && i > 0) refs[i - 1].current?.focus()
  }

  return (
    <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 36 }}>
      {digits.map((d, i) => (
        <input
          key={i}
          ref={refs[i]}
          value={d}
          onChange={e => setDigit(i, e.target.value)}
          onKeyDown={e => onKey(i, e)}
          inputMode="numeric"
          maxLength={1}
          disabled={loading}
          style={{
            width: 56, height: 64,
            fontSize: 28, fontWeight: 600, textAlign: 'center',
            background: 'var(--surface)', color: 'var(--text)',
            border: `1.5px solid ${error ? 'var(--danger)' : d ? 'var(--accent)' : 'var(--border-strong)'}`,
            borderRadius: 14, outline: 0, fontFamily: 'inherit',
            animation: error ? 'shake 0.4s' : 'none',
            opacity: loading ? 0.5 : 1,
          }}
        />
      ))}
      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-6px); }
          75% { transform: translateX(6px); }
        }
      `}</style>
    </div>
  )
}

// ---------------------------------------------------------------------------
// LoginScreen
// ---------------------------------------------------------------------------

export function LoginScreen() {
  const navigate = useNavigate()
  const { login } = useAuth()

  const [step, setStep] = useState('phone') // 'phone' | 'code'
  const [phone, setPhone] = useState('')
  const [phoneError, setPhoneError] = useState(null)
  const [codeError, setCodeError] = useState(false)
  const [verifying, setVerifying] = useState(false)

  const otpRequest = useOtpRequest()
  const otpVerify = useOtpVerify()

  async function handleRequestCode(e) {
    e.preventDefault()
    setPhoneError(null)
    const formatted = formatPhone(phone)
    if (!formatted) {
      setPhoneError('Введи номер телефона')
      return
    }
    try {
      await otpRequest.mutateAsync({ phone: formatted })
      // Anti-oracle: always 202, never reveals if phone is registered
      setStep('code')
    } catch {
      // Surface network errors inline
      setPhoneError('Ошибка сети. Попробуй ещё раз')
    }
  }

  async function handleCode(code) {
    if (verifying) return
    setCodeError(false)
    setVerifying(true)
    try {
      await otpVerify.mutateAsync({ phone: formatPhone(phone), code })
      // OTP verified — cookies now set; update auth context
      await login()
      navigate('/home', { replace: true })
    } catch {
      // Wrong/expired code — 401/422 from verify path is NOT session_expired
      setCodeError(true)
      setTimeout(() => setCodeError(false), 800)
    } finally {
      setVerifying(false)
    }
  }

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 230, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Status bar spacer */}
      <div style={{ height: 54 }} />

      {/* Logo / brand area */}
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        padding: '32px 0 0',
      }}>
        <div style={{
          width: 64, height: 64, borderRadius: 18,
          background: 'var(--accent)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', marginBottom: 16,
        }}>
          <span style={{ fontSize: 32 }}>🏋️</span>
        </div>
        <div className="t-h1" style={{ fontSize: 24, textAlign: 'center' }}>
          Войди в аккаунт
        </div>
      </div>

      {/* Content area */}
      <div style={{ flex: 1, padding: '0 24px', display: 'flex', flexDirection: 'column' }}>
        {step === 'phone' ? (
          <form onSubmit={handleRequestCode} style={{ marginTop: 32 }}>
            <div className="t-body" style={{ color: 'var(--text-2)', marginBottom: 20, textAlign: 'center' }}>
              Введи номер телефона, привязанный к аккаунту
            </div>

            <div style={{ marginBottom: 8 }}>
              <input
                type="tel"
                value={phone}
                onChange={e => { setPhone(e.target.value); setPhoneError(null) }}
                placeholder="+7 999 000-00-00"
                inputMode="tel"
                autoComplete="tel"
                style={{
                  width: '100%', height: 52, borderRadius: 14,
                  border: `1.5px solid ${phoneError ? 'var(--danger)' : 'var(--border-strong)'}`,
                  background: 'var(--surface)', color: 'var(--text)',
                  fontSize: 17, padding: '0 16px', outline: 0,
                  fontFamily: 'inherit', boxSizing: 'border-box',
                }}
              />
            </div>

            {phoneError && (
              <div className="t-small" style={{ color: 'var(--danger)', marginBottom: 12, textAlign: 'center' }}>
                {phoneError}
              </div>
            )}

            <div className="t-small" style={{ color: 'var(--text-3)', textAlign: 'center', marginBottom: 24, lineHeight: 1.5 }}>
              Если номер привязан, придёт код в Telegram
            </div>

            <button
              type="submit"
              disabled={otpRequest.isPending || !phone.trim()}
              style={{
                width: '100%', height: 52, borderRadius: 14, border: 0,
                background: 'var(--accent)', color: '#fff',
                fontSize: 16, fontWeight: 600, cursor: 'pointer',
                fontFamily: 'inherit', opacity: (otpRequest.isPending || !phone.trim()) ? 0.5 : 1,
              }}
            >
              {otpRequest.isPending ? 'Отправляем…' : 'Получить код'}
            </button>
          </form>
        ) : (
          <div style={{ marginTop: 32 }}>
            <div className="t-h1" style={{ fontSize: 22, textAlign: 'center' }}>
              Введи код из Telegram
            </div>
            <div className="t-body" style={{ color: 'var(--text-2)', textAlign: 'center', marginTop: 8 }}>
              Отправили код на{' '}
              <span style={{ color: 'var(--text)', fontWeight: 600 }}>{phone}</span>
            </div>

            <OtpBoxes
              onComplete={handleCode}
              loading={verifying}
              error={codeError}
            />

            {codeError && (
              <div className="t-small" style={{ color: 'var(--danger)', textAlign: 'center', marginTop: 14 }}>
                Код не подошёл, попробуй ещё раз
              </div>
            )}

            {verifying && (
              <div className="t-small" style={{ color: 'var(--text-3)', textAlign: 'center', marginTop: 14 }}>
                Проверяем…
              </div>
            )}

            <div style={{ marginTop: 32, display: 'flex', justifyContent: 'center' }}>
              <button
                onClick={() => setStep('phone')}
                style={{
                  border: 0, background: 'transparent', color: 'var(--accent-deep)',
                  fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                }}
              >
                Изменить номер
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default LoginScreen
