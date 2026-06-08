/**
 * ReferralLandingScreen — public deep-link landing for /i/:code (REFER-02).
 *
 * Route: /i/:code (public, outside RequireAuth — see App.jsx)
 * Resolves the referral code via GET /api/v1/i/<code>.
 * On valid:  stores code in sessionStorage['clubcore:pendingReferral'], navigates to /login.
 * On invalid: shows neutral "Добро пожаловать" landing, stores no code, navigates to /login.
 * The pending code is captured post-auth in OnboardingScreen (IDOR-safe, principal = referee).
 *
 * Brand string: «Sportzal» (D-62-02 placeholder — per CONTEXT; reference prototype strings are NOT used).
 * Styling: chrome-stripped full-screen (position:absolute; inset:0), var(--token) colors,
 * minimal own style matching the project's OnboardingScreen pattern.
 */
import React from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useClientReferralResolve } from '@/data'

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Format welcome bonus preview copy from kopecks.
 *  The resolver returns welcomeBonusKopecks. We show free-days copy (UI-SPEC §Deep-Link Landing).
 *  If the server surfaces kopecks > 0, we show a days estimate (assuming 1000 kopecks ≈ 1 day gift).
 *  Fallback: "14 дней в подарок к первому абонементу".
 */
function formatBonusPreview(welcomeBonusKopecks) {
  // UI-SPEC: "welcome-bonus preview from resolver"; reference copy is "14 дней в подарок".
  // We use the static fallback — the resolver currently returns welcomeBonusKopecks as a raw
  // kopeck amount. Until the server exposes a days field, we display the reference copy.
  // TODO Phase 99: wire actual days from resolver response when field is added.
  void welcomeBonusKopecks
  return '14 дней в подарок к первому абонементу'
}

// ─── Spot illustration ────────────────────────────────────────────────────────

function SpotIllustration() {
  return (
    <div
      aria-hidden="true"
      style={{ position: 'relative', width: 120, height: 96, margin: '0 auto', flexShrink: 0 }}
    >
      {/* Halo */}
      <div style={{
        position: 'absolute', left: '50%', top: '50%',
        transform: 'translate(-50%, -50%)',
        width: 96, height: 96, borderRadius: '50%',
        background: 'radial-gradient(circle, color-mix(in oklab, var(--accent) 22%, transparent) 0%, transparent 70%)',
      }} />
      {/* Outer dashed ring */}
      <div style={{
        position: 'absolute', left: '50%', top: '50%',
        transform: 'translate(-50%, -50%)',
        width: 110, height: 110, borderRadius: '50%',
        border: '1.5px dashed color-mix(in oklab, var(--accent) 40%, transparent)',
        opacity: 0.3,
      }} />
      {/* Inner dashed ring */}
      <div style={{
        position: 'absolute', left: '50%', top: '50%',
        transform: 'translate(-50%, -50%)',
        width: 80, height: 80, borderRadius: '50%',
        border: '1.5px dashed color-mix(in oklab, var(--accent) 40%, transparent)',
        opacity: 0.5,
      }} />
      {/* Two person circles side by side */}
      <div style={{
        position: 'absolute', left: '50%', top: '50%',
        transform: 'translate(-50%, -50%)',
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <div style={{
          width: 26, height: 26, borderRadius: '50%',
          background: 'var(--accent-soft)',
          border: '2px solid var(--accent)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--accent-deep)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
          </svg>
        </div>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: 'var(--accent)', flexShrink: 0,
        }} />
        <div style={{
          width: 26, height: 26, borderRadius: '50%',
          background: 'var(--surface)',
          border: '1.5px dashed var(--border-strong)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
          </svg>
        </div>
      </div>
      {/* Floating chip top-right */}
      <div style={{
        position: 'absolute', width: 8, height: 8, right: 14, top: 10,
        background: 'var(--accent-deep)', borderRadius: 4,
        animation: 'rf-float 3.4s ease-in-out infinite',
      }} />
      {/* Floating chip bottom-left */}
      <div style={{
        position: 'absolute', width: 6, height: 6, left: 10, bottom: 14,
        background: 'var(--accent)', borderRadius: '50%',
        animation: 'rf-float 3.4s ease-in-out infinite',
        animationDelay: '1.1s',
      }} />
    </div>
  )
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '0 32px' }}>
      <div style={{ width: 120, height: 96, borderRadius: 16, background: 'var(--border)', opacity: 0.5 }} />
      <div style={{ width: 220, height: 24, borderRadius: 8, background: 'var(--border)', opacity: 0.5 }} />
      <div style={{ width: 180, height: 16, borderRadius: 6, background: 'var(--border)', opacity: 0.35 }} />
      <div style={{ width: '100%', maxWidth: 300, height: 54, borderRadius: 18, background: 'var(--border)', opacity: 0.35, marginTop: 8 }} />
    </div>
  )
}

// ─── Main screen ──────────────────────────────────────────────────────────────

export function ReferralLandingScreen() {
  const { code } = useParams()
  const navigate = useNavigate()
  const resolveQuery = useClientReferralResolve(code ?? '')

  const isLoading = resolveQuery.isLoading
  const data = resolveQuery.data

  // Determine state: valid landing vs neutral landing.
  // Treat resolve errors as "invalid" — show neutral landing (anti-enumeration, no error page).
  const isValid = !isLoading && !!data && data.valid === true
  const referrerFirstName = isValid ? (data.referrerFirstName ?? null) : null
  const welcomeBonusKopecks = isValid ? (data.welcomeBonusKopecks ?? 0) : 0

  function handleJoin() {
    if (isValid && code) {
      sessionStorage.setItem('clubcore:pendingReferral', code)
    }
    navigate('/login', { replace: true })
  }

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background: 'var(--bg)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '0 28px 40px',
        textAlign: 'center',
        overflowY: 'auto',
      }}
    >
      {/* Floating animation keyframes */}
      <style>{`
        @keyframes rf-float {
          0%, 100% { transform: translateY(0px) rotate(0deg); }
          50% { transform: translateY(-5px) rotate(8deg); }
        }
        @media (prefers-reduced-motion: reduce) {
          @keyframes rf-float { 0%, 100% { transform: none; } }
        }
      `}</style>

      {isLoading ? (
        <LoadingSkeleton />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0, width: '100%', maxWidth: 340 }}>
          {/* Spot illustration */}
          <SpotIllustration />

          {/* Heading */}
          <h1 style={{
            marginTop: 20,
            fontSize: 24,
            fontWeight: 750,
            letterSpacing: -0.6,
            lineHeight: 1.18,
            color: 'var(--text)',
            textWrap: 'balance',
          }}>
            {isValid && referrerFirstName
              ? `${referrerFirstName} зовёт вас в «Sportzal»`
              : 'Добро пожаловать в «Sportzal»'}
          </h1>

          {/* Body — valid: bonus preview; invalid: generic sub */}
          <p style={{
            marginTop: 12,
            fontSize: 14.5,
            lineHeight: 1.5,
            color: 'var(--text-2)',
            textWrap: 'pretty',
            maxWidth: 280,
          }}>
            {isValid
              ? formatBonusPreview(welcomeBonusKopecks)
              : 'Запишитесь на тренировки, следите за прогрессом и управляйте абонементом.'}
          </p>

          {/* Bonus badge (valid only) */}
          {isValid && (
            <div style={{
              marginTop: 16,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 16px',
              borderRadius: 999,
              background: 'var(--accent-soft)',
              color: 'var(--accent-deep)',
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
              <span style={{ fontSize: 13, fontWeight: 650, letterSpacing: -0.1 }}>
                Подарок новому участнику
              </span>
            </div>
          )}

          {/* CTA button */}
          <button
            className="btn btn-accent"
            style={{ marginTop: 28, width: '100%', height: 54 }}
            onClick={handleJoin}
          >
            Присоединиться
          </button>
        </div>
      )}
    </div>
  )
}
