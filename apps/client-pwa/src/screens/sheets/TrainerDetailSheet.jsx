/**
 * TrainerDetailSheet (Phase 88 TRNR-04)
 *
 * Full-screen sub-sheet rendering live trainer profile from GET /api/v1/client/trainers/{id}.
 * Read-only except for the "Записаться" CTA (outbound navigation — no mutations inside).
 *
 * Design contract: 88-UI-SPEC.md
 * API contract: GET /api/v1/client/trainers/{trainer_id} (Plan 02)
 *
 * Threat mitigations:
 *   T-88-03: photo_url XSS — scheme allow-list (http/https only via new URL parse);
 *            javascript:/data:/other → initials Avatar fallback; img onError → Avatar fallback
 *   T-88-09: swap-seam import only (ESLint no-restricted-paths gate passed after de-list)
 */
import React, { useState } from 'react'
import { StatusBar } from '@/components/StatusBar.jsx'
import { PullToRefresh } from '@/components/PullToRefresh.jsx'
import { SubSheetHeader } from '@/screens/sheets/ProfileExtraSheets.jsx'
import { Icon } from '@/components/Icon.jsx'
import { Avatar } from '@/components/Avatar.jsx'
import { useClientTrainerDetail } from '@/data'

// ─── Feature flag (documentation anchor — kill-switch per Phase 86/87 precedent) ─
const TRAINER_DETAIL_FEATURE_FLAGS = {
  trainerProfile: true, // TRNR-04 (Phase 88): wired to GET /client/trainers/{id}
}
void TRAINER_DETAIL_FEATURE_FLAGS

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Derive two-letter initials from a full name.
 * "Аня Соколова" → "АС"
 * Mirrors BookScreen.jsx getInitials helper.
 */
function getInitials(name) {
  const parts = (name ?? '').split(' ')
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase()
}

/**
 * Returns true if the URL is safe to use as an <img src>.
 * Only http: and https: schemes are allowed (T-88-03 XSS guard).
 */
function isSafePhotoUrl(url) {
  if (!url) return false
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

// ─── Section label ────────────────────────────────────────────────────────────
function SectionLabel({ children }) {
  return (
    <div className="t-mini" style={{
      padding: '16px 16px 8px',
      color: 'var(--text-3)',
      fontWeight: 700,
      letterSpacing: 0.5,
      textTransform: 'uppercase',
    }}>
      {children}
    </div>
  )
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────
function TrainerDetailSkeleton() {
  return (
    <div aria-label="Загрузка профиля тренера…">
      {/* Hero skeleton */}
      <div style={{
        padding: '24px 16px 16px',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
      }}>
        <div className="sk sk-circle" style={{ width: 80, height: 80, borderRadius: '50%' }} />
        <div className="sk sk-line" style={{ width: 140, height: 18, margin: '8px auto 0' }} />
        <div className="sk sk-line" style={{ width: 100, height: 14, margin: '4px auto 0' }} />
      </div>

      {/* Bio section skeleton */}
      <div className="sk sk-line" style={{ width: 80, margin: '16px 16px 8px' }} />
      <div className="card" style={{ padding: '12px 16px', margin: '0 16px' }}>
        <div className="sk sk-line" style={{ width: '100%', marginBottom: 8 }} />
        <div className="sk sk-line" style={{ width: '80%', marginBottom: 8 }} />
        <div className="sk sk-line" style={{ width: '60%' }} />
      </div>
    </div>
  )
}

// ─── Error state ──────────────────────────────────────────────────────────────
function TrainerDetailError() {
  return (
    <div style={{ padding: '40px 24px', textAlign: 'center' }}>
      <div style={{
        width: 56, height: 56, borderRadius: 999, margin: '0 auto 16px',
        background: 'var(--surface-2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon name="alertCircle" size={32} color="var(--text-3)" />
      </div>
      <div className="t-small" style={{ color: 'var(--text-2)' }}>
        Не удалось загрузить профиль тренера. Потяните вниз, чтобы повторить.
      </div>
    </div>
  )
}

// ─── TrainerDetailSheet ───────────────────────────────────────────────────────
export function TrainerDetailSheet({ trainer, onClose, onBook, onCheckout: _onCheckout }) {
  const query = useClientTrainerDetail(trainer?.id ?? null)
  const data = query.data

  // XSS-safe photo rendering state: track if the img onError fired
  const [photoError, setPhotoError] = useState(false)

  const handleRefresh = async () => {
    setPhotoError(false)
    await query.refetch()
  }

  // Derive Avatar fallback values from the trainer prop (pre-API data from TRAINERS list)
  const avatarInitials = data ? getInitials(data.fullName) : (trainer ? getInitials(trainer.name ?? '') : '?')
  const avatarBg = trainer?.bg ?? 'var(--surface-2)'
  const avatarColor = trainer?.color ?? 'var(--text-3)'

  // XSS guard: only use photoUrl as img src when it passes the scheme allow-list
  // AND the img hasn't fired onError (T-88-03)
  const safePhotoUrl = data?.photoUrl && isSafePhotoUrl(data.photoUrl) && !photoError
    ? data.photoUrl
    : null

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />
      <SubSheetHeader title="Тренер" onClose={onClose} />

      <PullToRefresh scrollPaddingTop={0} onRefresh={handleRefresh}>

        {/* ── Loading state ───────────────────────────────────────────────── */}
        {query.isLoading && <TrainerDetailSkeleton />}

        {/* ── Error state ─────────────────────────────────────────────────── */}
        {query.isError && <TrainerDetailError />}

        {/* ── Loaded state ────────────────────────────────────────────────── */}
        {data && (
          <div>
            {/* [1] Hero block */}
            <div style={{
              padding: '24px 16px 16px',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
            }}>
              {safePhotoUrl ? (
                <img
                  src={safePhotoUrl}
                  width={80}
                  height={80}
                  style={{ borderRadius: '50%', objectFit: 'cover' }}
                  alt={data.fullName}
                  onError={() => setPhotoError(true)}
                />
              ) : (
                <Avatar
                  initials={avatarInitials}
                  bg={avatarBg}
                  color={avatarColor}
                  size={80}
                />
              )}

              <div className="t-h2" style={{ color: 'var(--text)', textAlign: 'center' }}>
                {data.fullName}
              </div>

              {data.specialization && (
                <div className="t-body" style={{ color: 'var(--text-2)', textAlign: 'center' }}>
                  {data.specialization}
                </div>
              )}
            </div>

            {/* [2] Bio section */}
            <SectionLabel>БИОГРАФИЯ</SectionLabel>
            <div className="card" style={{ padding: '12px 16px', margin: '0 16px' }}>
              {data.bio ? (
                <div className="t-body" style={{ color: 'var(--text-2)', lineHeight: 1.6 }}>
                  {data.bio}
                </div>
              ) : (
                <div className="t-small" style={{ color: 'var(--text-3)' }}>
                  Информация скоро появится.
                </div>
              )}
            </div>

            {/* Bottom safe-area padding */}
            <div style={{ height: 32 }} />
          </div>
        )}

      </PullToRefresh>

      {/* ── Sticky CTA bar (always visible, even during loading/error) ────── */}
      <div style={{ flexShrink: 0 }}>
        {/* Gradient fade above bar */}
        <div style={{
          height: 24,
          background: 'linear-gradient(to top, var(--bg) 60%, transparent)',
          pointerEvents: 'none',
        }} />
        <div style={{
          padding: '8px 16px 32px',
          background: 'var(--bg)',
        }}>
          <button
            className="btn btn-accent"
            style={{ width: '100%' }}
            onClick={onBook}
            disabled={!onBook}
          >
            Записаться
          </button>
        </div>
      </div>
    </div>
  )
}
