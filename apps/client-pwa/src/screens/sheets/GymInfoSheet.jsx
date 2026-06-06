/**
 * GymInfoSheet (Phase 86 GYM-01)
 *
 * Full-screen sub-sheet rendering live gym data from GET /api/v1/client/gym.
 * Read-only — no mutations, no user input.
 *
 * Design contract: 86-UI-SPEC.md
 * API contract: GET /api/v1/client/gym (Plan 02)
 * Photos: frontend-only static (from gym.js shape) — NOT from API (CONTEXT.md decision)
 * Open/closed badge: client-side derivation from hours + Europe/Moscow clock (UI-SPEC §Hours)
 *
 * Threat mitigations:
 *   T-86-09: Social URLs built via fixed prefixes; external links use rel="noopener noreferrer"
 *   T-86-10: Generic error copy — no raw error/status echoed to UI
 */
import React from 'react'
import { Icon } from '@/components/Icon.jsx'
import { StatusBar } from '@/components/StatusBar.jsx'
import { PullToRefresh } from '@/components/PullToRefresh.jsx'
import { SubSheetHeader } from '@/screens/sheets/ProfileExtraSheets.jsx'
import { useClientGymInfo } from '@/data'

// ─── Static decorative photos (frontend-only — NOT from API) ─────────────────
// Source shape from data/gym.js; photos are not stored in the DB (CONTEXT.md).
const STATIC_PHOTOS = [
  { bg: '#3f4444', icon: 'dumbbell', tag: 'Зал' },
  { bg: '#2c5e3f', icon: 'run',      tag: 'Кардио' },
  { bg: '#7c5e3f', icon: 'sauna',    tag: 'Сауна' },
  { bg: '#5a4d3a', icon: 'locker',   tag: 'Раздевалка' },
  { bg: '#4a3f5e', icon: 'yoga',     tag: 'Студия' },
]

// ─── Open/closed badge helpers ───────────────────────────────────────────────

/**
 * Parse "HH:MM" → total minutes.
 */
function parseHHMM(hhmm) {
  const parts = hhmm.split(':')
  return parseInt(parts[0] ?? '0', 10) * 60 + parseInt(parts[1] ?? '0', 10)
}

/**
 * Derive today's index (Mon=0 … Sun=6) from a Europe/Moscow Date.
 * Uses Intl to get the correct day regardless of browser timezone.
 */
function getMoscowNow() {
  const formatter = new Intl.DateTimeFormat('en', {
    timeZone: 'Europe/Moscow',
    hour: 'numeric',
    minute: 'numeric',
    weekday: 'short',
    hour12: false,
  })
  const parts = formatter.formatToParts(new Date())
  const weekdayMap = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 }
  const weekdayStr = (parts.find(p => p.type === 'weekday')?.value) ?? 'Mon'
  const todayIdx = weekdayMap[weekdayStr] ?? 0
  const hour = parseInt((parts.find(p => p.type === 'hour')?.value) ?? '0', 10)
  const minute = parseInt((parts.find(p => p.type === 'minute')?.value) ?? '0', 10)
  const nowMinutes = hour * 60 + minute
  return { todayIdx, nowMinutes }
}

/**
 * Compute open/closed status for the today row.
 * Returns { isOpen, todayRow, nextOpenTime }
 *   nextOpenTime = the time to show in the secondary line (today open or tomorrow open).
 */
function getOpenStatus(hours) {
  if (!hours || hours.length === 0) return null
  const { todayIdx, nowMinutes } = getMoscowNow()
  const todayRow = hours[todayIdx] ?? hours[0]
  const openMinutes = parseHHMM(todayRow.open)
  const closeMinutes = parseHHMM(todayRow.close)
  const isOpen = nowMinutes >= openMinutes && nowMinutes < closeMinutes

  let nextOpenTime = todayRow.open
  if (!isOpen && nowMinutes >= closeMinutes) {
    // Closed for the night — show tomorrow's open time
    const tomorrowIdx = (todayIdx + 1) % 7
    const tomorrowRow = hours[tomorrowIdx] ?? hours[0]
    nextOpenTime = tomorrowRow.open
  }

  return { isOpen, todayRow, todayIdx, nextOpenTime, closeMinutes, openMinutes, nowMinutes }
}

// ─── Hairline divider ─────────────────────────────────────────────────────────
function Hairline({ marginLeft = 0 }) {
  return <div style={{ height: 0.5, background: 'var(--border)', marginLeft }} />
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

// ─── Social URL derivation ────────────────────────────────────────────────────
function socialUrl(item) {
  const handle = item.handle.replace('@', '')
  if (item.kind === 'tg') return `https://t.me/${handle}`
  if (item.kind === 'ig') return `https://instagram.com/${handle}`
  return '#'
}

function socialIconName(kind) {
  if (kind === 'tg') return 'telegram'
  if (kind === 'ig') return 'instagram'
  return 'link'
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────
function GymInfoSkeleton() {
  return (
    <div aria-label="Загрузка информации о зале…">
      {/* Hero skeleton */}
      <div className="card" style={{ padding: 16, margin: '8px 16px 0' }}>
        <div className="sk sk-line" style={{ width: '60%' }} />
        <div className="sk sk-line" style={{ width: '40%', marginTop: 8 }} />
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <span className="chip sk" style={{ width: 120, height: 28, display: 'inline-block', borderRadius: 999 }} />
          <span className="chip sk" style={{ width: 100, height: 28, display: 'inline-block', borderRadius: 999 }} />
        </div>
      </div>

      {/* Photo strip skeleton */}
      <div style={{ padding: '12px 0 4px', overflow: 'hidden' }}>
        <div style={{ display: 'flex', gap: 8, padding: '0 16px' }}>
          {[0, 1, 2, 3, 4].map(i => (
            <div key={i} className="sk" style={{
              width: 88, height: 80, borderRadius: 'var(--r-lg)', flexShrink: 0,
            }} />
          ))}
        </div>
      </div>

      {/* Hours skeleton */}
      <SectionLabel>ЧАСЫ РАБОТЫ</SectionLabel>
      <div className="card" style={{ margin: '0 16px 0', padding: 16 }}>
        {[80, 60, 70, 55].map((w, i) => (
          <div key={i} className="sk sk-line" style={{ width: `${w}%`, marginBottom: i < 3 ? 12 : 0 }} />
        ))}
      </div>

      {/* Amenities skeleton */}
      <SectionLabel>УДОБСТВА</SectionLabel>
      <div className="card" style={{ margin: '0 16px 0', padding: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
          {[0, 1, 2, 3, 4, 5, 6, 7].map(i => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '8px 4px' }}>
              <div className="sk" style={{ width: 32, height: 32, borderRadius: 8 }} />
            </div>
          ))}
        </div>
      </div>

      {/* Rules skeleton */}
      <SectionLabel>ПРАВИЛА</SectionLabel>
      <div className="card" style={{ margin: '0 16px 0', padding: 16 }}>
        {[75, 60, 80].map((w, i) => (
          <div key={i} className="sk sk-line" style={{ width: `${w}%`, marginBottom: i < 2 ? 12 : 0 }} />
        ))}
      </div>

      {/* Contacts skeleton */}
      <SectionLabel>КОНТАКТЫ</SectionLabel>
      <div className="card" style={{ margin: '0 16px 0', padding: 16 }}>
        {[60, 55, 50].map((w, i) => (
          <div key={i} className="sk sk-line" style={{ width: `${w}%`, marginBottom: i < 2 ? 12 : 0 }} />
        ))}
      </div>
    </div>
  )
}

// ─── Error state ──────────────────────────────────────────────────────────────
function GymInfoError() {
  return (
    <div style={{ padding: '40px 24px', textAlign: 'center' }}>
      <div style={{
        width: 64, height: 64, borderRadius: 999, margin: '0 auto 16px',
        background: 'var(--danger-soft)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon name="alertCircle" size={40} color="var(--danger)" />
      </div>
      <div className="t-h3">Не удалось загрузить информацию о зале</div>
      <div className="t-small" style={{ color: 'var(--text-2)', marginTop: 8 }}>
        Потяните вниз, чтобы попробовать снова.
      </div>
    </div>
  )
}

// ─── GymInfoSheet ─────────────────────────────────────────────────────────────
export function GymInfoSheet({ onClose }) {
  const gymInfoQuery = useClientGymInfo()

  const handleRefresh = async () => {
    await gymInfoQuery.refetch()
  }

  const data = gymInfoQuery.data
  const status = data ? getOpenStatus(data.hours) : null

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />
      <SubSheetHeader title="Информация о зале" onClose={onClose} />

      <PullToRefresh scrollPaddingTop={0} onRefresh={handleRefresh}>

        {/* ── Loading state ─────────────────────────────────────────────── */}
        {gymInfoQuery.isLoading && <GymInfoSkeleton />}

        {/* ── Error state ───────────────────────────────────────────────── */}
        {gymInfoQuery.isError && <GymInfoError />}

        {/* ── Loaded state ─────────────────────────────────────────────── */}
        {data && (
          <div>

            {/* [1] Hero card */}
            <div className="card" style={{ padding: 16, margin: '8px 16px 0' }}>
              <div className="t-h2" style={{ color: 'var(--text)' }}>{data.name}</div>
              {data.tagline && (
                <div className="t-body" style={{ color: 'var(--text-2)', marginTop: 4 }}>{data.tagline}</div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 8 }}>
                <span className="chip" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <Icon name="mapPin" size={16} color="var(--text-2)" />
                  {data.address}
                </span>
                {data.metro && (
                  <span className="chip" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <Icon name="navigation" size={16} color="var(--text-2)" />
                    {data.metro}
                  </span>
                )}
              </div>
            </div>

            {/* [2] Photo strip — frontend-only static decor */}
            <div style={{
              padding: '12px 0 4px',
              overflowX: 'auto',
              scrollbarWidth: 'none',
            }}>
              <div style={{ display: 'flex', gap: 8, padding: '0 16px' }}>
                {STATIC_PHOTOS.map((photo, i) => (
                  <div key={i} style={{
                    width: 88, height: 80,
                    borderRadius: 'var(--r-lg)',
                    flexShrink: 0,
                    background: photo.bg,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 4,
                  }}>
                    <Icon name={photo.icon} size={20} color="rgba(255,255,255,0.85)" />
                    <span className="t-mini" style={{
                      color: 'rgba(255,255,255,0.85)',
                      letterSpacing: '0.3px',
                    }}>
                      {photo.tag}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* [3] Hours section */}
            {data.hours && data.hours.length > 0 && status && (
              <>
                <SectionLabel>ЧАСЫ РАБОТЫ</SectionLabel>
                <div className="card" style={{ padding: 0, margin: '0 16px 0', overflow: 'hidden' }}>
                  {/* Today row */}
                  <div style={{
                    padding: '12px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                  }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                        <span className="t-h3">{status.todayRow.d}</span>
                        <span className="t-small" style={{ color: 'var(--text-3)' }}>сегодня</span>
                      </div>
                      <div className="t-small" style={{ color: 'var(--text-3)', marginTop: 2 }}>
                        {status.isOpen
                          ? `до ${status.todayRow.close}`
                          : status.nowMinutes < status.openMinutes
                            ? `откроется в ${status.todayRow.open}`
                            : `откроется в ${status.nextOpenTime}`
                        }
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                      <span className="t-body" style={{ fontVariantNumeric: 'tabular-nums' }}>
                        {status.todayRow.open} – {status.todayRow.close}
                      </span>
                      <span className={`chip ${status.isOpen ? 'chip-accent' : 'chip-danger'}`}>
                        {status.isOpen ? 'Сейчас открыто' : 'Закрыто'}
                      </span>
                    </div>
                  </div>

                  <Hairline />

                  {/* Remaining 6 days in order after today */}
                  {data.hours
                    .map((row, origIdx) => ({ row, origIdx }))
                    .filter(({ origIdx }) => origIdx !== status.todayIdx)
                    .sort((a, b) => {
                      const ai = (a.origIdx - status.todayIdx + 7) % 7
                      const bi = (b.origIdx - status.todayIdx + 7) % 7
                      return ai - bi
                    })
                    .map(({ row }, i, arr) => (
                      <React.Fragment key={row.d}>
                        <div style={{
                          padding: '12px 16px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 12,
                        }}>
                          <span className="t-small" style={{ width: 28, color: 'var(--text-2)' }}>{row.d}</span>
                          <span className="t-small" style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text)' }}>
                            {row.open} – {row.close}
                          </span>
                        </div>
                        {i < arr.length - 1 && <Hairline marginLeft={56} />}
                      </React.Fragment>
                    ))
                  }
                </div>
              </>
            )}

            {/* [4] Amenities grid */}
            {data.amenities && data.amenities.length > 0 && (
              <>
                <SectionLabel>УДОБСТВА</SectionLabel>
                <div className="card" style={{ padding: 12, margin: '0 16px 0' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                    {data.amenities.map((amenity, i) => (
                      <div key={i} style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: 8,
                        padding: '8px 4px',
                      }}>
                        <div style={{
                          width: 32, height: 32, borderRadius: 8,
                          background: 'var(--accent-soft)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          <Icon name={amenity.icon} size={16} color="var(--accent-deep)" />
                        </div>
                        <span className="t-mini" style={{
                          color: 'var(--text-2)',
                          textAlign: 'center',
                          lineHeight: 1.2,
                        }}>
                          {amenity.label}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* [5] Rules list */}
            {data.rules && data.rules.length > 0 && (
              <>
                <SectionLabel>ПРАВИЛА</SectionLabel>
                <div className="card" style={{ padding: 0, margin: '0 16px 0', overflow: 'hidden' }}>
                  {data.rules.map((rule, i) => (
                    <React.Fragment key={i}>
                      {i > 0 && <Hairline marginLeft={52} />}
                      <div style={{
                        padding: '12px 16px',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 12,
                      }}>
                        <div style={{
                          width: 24, height: 24, borderRadius: 999, flexShrink: 0,
                          background: 'var(--surface-2)',
                          border: '0.5px solid var(--border)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          <span className="t-mini" style={{ color: 'var(--text-3)' }}>{i + 1}</span>
                        </div>
                        <span className="t-body" style={{ flex: 1, lineHeight: 1.5, color: 'var(--text)' }}>
                          {rule}
                        </span>
                      </div>
                    </React.Fragment>
                  ))}
                </div>
              </>
            )}

            {/* [6] Contacts section */}
            {(data.phone || data.email) && (
              <>
                <SectionLabel>КОНТАКТЫ</SectionLabel>
                <div className="card" style={{ padding: 0, margin: '0 16px 0' }}>
                  {data.phone && (
                    <>
                      <a
                        href={`tel:${data.phone}`}
                        style={{
                          padding: '12px 16px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 12,
                          textDecoration: 'none',
                          color: 'inherit',
                        }}
                      >
                        <div style={{
                          width: 32, height: 32, borderRadius: 8,
                          background: 'var(--surface-2)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          <Icon name="phone" size={16} color="var(--text-2)" />
                        </div>
                        <div style={{ flex: 1 }}>
                          <div className="t-h3">{data.phone}</div>
                          <div className="t-small" style={{ color: 'var(--text-3)' }}>Позвонить</div>
                        </div>
                        <Icon name="chevronRight" size={16} color="var(--text-3)" />
                      </a>
                      {data.email && <Hairline />}
                    </>
                  )}
                  {data.email && (
                    <a
                      href={`mailto:${data.email}`}
                      style={{
                        padding: '12px 16px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        textDecoration: 'none',
                        color: 'inherit',
                      }}
                    >
                      <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: 'var(--surface-2)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                        <Icon name="mail" size={16} color="var(--text-2)" />
                      </div>
                      <div style={{ flex: 1 }}>
                        <div className="t-h3">{data.email}</div>
                        <div className="t-small" style={{ color: 'var(--text-3)' }}>Написать</div>
                      </div>
                      <Icon name="chevronRight" size={16} color="var(--text-3)" />
                    </a>
                  )}
                </div>
              </>
            )}

            {/* [7] Social links — rendered ONLY if present */}
            {data.social && data.social.length > 0 && (
              <>
                <SectionLabel>МЫ В СОЦСЕТЯХ</SectionLabel>
                <div className="card" style={{ padding: 0, margin: '0 16px 0' }}>
                  {data.social.map((item, i) => (
                    <React.Fragment key={item.kind}>
                      {i > 0 && <Hairline />}
                      <a
                        href={socialUrl(item)}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          padding: '12px 16px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 12,
                          textDecoration: 'none',
                          color: 'inherit',
                        }}
                      >
                        <div style={{
                          width: 32, height: 32, borderRadius: 8,
                          background: 'var(--surface-2)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          <Icon name={socialIconName(item.kind)} size={16} color="var(--text-2)" />
                        </div>
                        <div style={{ flex: 1 }}>
                          <div className="t-h3">{item.label}</div>
                          <div className="t-small" style={{ color: 'var(--text-3)' }}>{item.handle}</div>
                        </div>
                        <Icon name="chevronRight" size={16} color="var(--text-3)" />
                      </a>
                    </React.Fragment>
                  ))}
                </div>
              </>
            )}

            {/* Bottom safe-area padding */}
            <div style={{ height: 32 }} />
          </div>
        )}

      </PullToRefresh>
    </div>
  )
}
