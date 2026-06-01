/**
 * OnboardingScreen — 4-step profile questionnaire for new («newbie») clients.
 *
 * Route: /onboarding (lazy, under RequireAuth — see App.jsx)
 * D-04: Shown to newbies on first login (auto-redirect from HomeScreen).
 *       Also re-enterable via onboarding-strip «Профиль» step.
 * D-05: Both «Готово!» and «Пропустить» set onboarding_completed_at so the
 *       auto-redirect never fires again.
 * D-08: Finish fires ONE atomic PATCH including onboardingCompleted: true.
 *       Skip fires a SEPARATE minimal PATCH with ONLY { onboardingCompleted: true }.
 *
 * Styling: all colors via var(--token); only #06120c permitted hex (accent-btn text).
 * UI-SPEC: Phase 999.5 — Screen 1: OnboardingScreen.
 */
import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon.jsx'
import { StatusBar } from '@/components/StatusBar.jsx'
import { useUpdateClientProfile, useCompleteOnboarding } from '@/data'

// ─── Goal config — D-07: strict 4-code enum ──────────────────────────────────
const GOALS = [
  { code: 'lose_weight', name: 'Похудение',    desc: 'Сжечь лишнее',   icon: 'flame'     },
  { code: 'gain_mass',   name: 'Набор массы',  desc: 'Силовой рост',   icon: 'barbell'   },
  { code: 'tone',        name: 'Тонус',        desc: 'Подтянуть тело', icon: 'lightning' },
  { code: 'maintain',    name: 'Поддержать',   desc: 'Быть в форме',   icon: 'heart'     },
]

const GOAL_NAME = Object.fromEntries(GOALS.map(g => [g.code, g.name]))

// ─── Spot illustration scenes ─────────────────────────────────────────────────

function SpotScene({ step }) {
  const scene = (() => {
    if (step === 0) return (
      // Scene 0 — member card / profile
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: '100%' }}>
        <div style={{
          width: 26, height: 26, borderRadius: '50%',
          background: 'var(--accent)', flexShrink: 0,
          boxShadow: 'inset 0 0 0 3px color-mix(in oklab, var(--accent-deep) 50%, transparent)',
        }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
          <div style={{ height: 5, borderRadius: 999, background: 'var(--border-strong)' }} />
          <div style={{ height: 5, borderRadius: 999, background: 'var(--border)', width: '58%' }} />
        </div>
      </div>
    )
    if (step === 1) return (
      // Scene 1 — bullseye target
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <div style={{
          width: 42, height: 42, borderRadius: '50%',
          background: 'var(--accent-soft)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            width: 26, height: 26, borderRadius: '50%',
            background: 'color-mix(in oklab, var(--accent) 60%, var(--surface))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{ width: 11, height: 11, borderRadius: '50%', background: 'var(--accent-deep)' }} />
          </div>
        </div>
      </div>
    )
    if (step === 2) return (
      // Scene 2 — ruler / measure bars
      <div style={{
        display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
        height: '100%', paddingBottom: 2,
      }}>
        {[40, 64, 100, 40, 64, 40, 40].map((h, i) => (
          <div key={i} style={{
            width: i === 2 ? 4 : 3, borderRadius: 3,
            background: i === 2 ? 'var(--accent)' : 'var(--border-strong)',
            height: `${h}%`,
          }} />
        ))}
      </div>
    )
    // Scene 3 — checklist
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7, justifyContent: 'center', height: '100%' }}>
        {[true, true, false].map((done, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 14, height: 14, borderRadius: '50%', flexShrink: 0,
              background: done ? 'var(--accent)' : 'transparent',
              border: done ? 'none' : '1.5px solid var(--border-strong)',
              color: '#06120c',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {done && (
                <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12l5 5L20 7" />
                </svg>
              )}
            </div>
            <div style={{
              flex: 1, height: 5, borderRadius: 999,
              background: done ? 'var(--border-strong)' : 'var(--border)',
              width: done ? '100%' : '70%',
            }} />
          </div>
        ))}
      </div>
    )
  })()

  return (
    <div
      aria-hidden="true"
      style={{ position: 'relative', width: 128, height: 96, margin: '2px 0 0', flexShrink: 0 }}
    >
      {/* Halo */}
      <div style={{
        position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
        width: 90, height: 90, borderRadius: '50%',
        background: 'radial-gradient(circle, color-mix(in oklab, var(--accent) 20%, transparent) 0%, transparent 64%)',
      }} />
      {/* Ring 2 (larger) */}
      <div style={{
        position: 'absolute', left: -4, top: '50%', transform: 'translateY(-50%)',
        width: 118, height: 118, borderRadius: '50%',
        border: '1.5px dashed color-mix(in oklab, var(--accent) 42%, transparent)',
        opacity: 0.24,
      }} />
      {/* Ring 1 */}
      <div style={{
        position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
        width: 90, height: 90, borderRadius: '50%',
        border: '1.5px dashed color-mix(in oklab, var(--accent) 42%, transparent)',
        opacity: 0.5,
      }} />
      {/* Floating decoration chips */}
      <div style={{
        position: 'absolute', width: 9, height: 9, right: 30, top: 8,
        background: 'var(--accent-deep)', borderRadius: 4, transform: 'rotate(16deg)',
        animation: 'spot-float 3.4s ease-in-out infinite',
        zIndex: 1,
      }} />
      <div style={{
        position: 'absolute', width: 7, height: 7, right: 12, bottom: 20,
        background: 'var(--accent)', borderRadius: '50%',
        animation: 'spot-float 3.4s ease-in-out infinite',
        animationDelay: '0.7s', zIndex: 1,
      }} />
      <div style={{
        position: 'absolute', width: 6, height: 6, left: 4, top: 16,
        background: 'var(--accent-deep)', borderRadius: '50%',
        animation: 'spot-float 3.4s ease-in-out infinite',
        animationDelay: '1.2s', zIndex: 1,
      }} />
      {/* Central scene card */}
      <div style={{
        position: 'absolute', left: 55, top: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 2,
      }}>
        <div style={{
          width: 76, height: 62,
          background: 'var(--surface)',
          border: '0.5px solid var(--border)',
          borderRadius: 15,
          boxShadow: '0 10px 24px rgba(28,25,23,0.12), 0 2px 5px rgba(28,25,23,0.05)',
          padding: '10px 11px',
          transform: 'rotate(-4deg)',
          transformOrigin: 'center',
          animation: 'scene-in 0.46s cubic-bezier(0.32, 1.6, 0.32, 1) both',
        }}>
          {scene}
        </div>
      </div>
    </div>
  )
}

// ─── Slider with filled track ─────────────────────────────────────────────────

function MetricSlider({ id, label, unit, min, max, value, onChange }) {
  const pct = ((value - min) / (max - min)) * 100
  const trackStyle = {
    background: `linear-gradient(to right, var(--accent) 0% ${pct}%, var(--border-strong) ${pct}% 100%)`,
  }

  return (
    <div style={{
      background: 'var(--surface)',
      border: '0.5px solid var(--border)',
      borderRadius: 'var(--r-lg)',
      boxShadow: 'var(--sh-2)',
      padding: '18px 18px 20px',
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-2)', letterSpacing: -0.1 }}>
          {label}
        </span>
        <span style={{ fontVariantNumeric: 'tabular-nums', fontSize: 30, fontWeight: 700, letterSpacing: -1, color: 'var(--text)' }}>
          {value}<span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-3)', marginLeft: 3, letterSpacing: 0 }}>{unit}</span>
        </span>
      </div>
      <div style={{ marginTop: 14, position: 'relative' }}>
        <input
          id={id}
          aria-label={label}
          type="range"
          min={min}
          max={max}
          step={1}
          value={value}
          onChange={e => onChange(Number(e.target.value))}
          style={{
            WebkitAppearance: 'none',
            appearance: 'none',
            width: '100%',
            height: 8,
            borderRadius: 999,
            outline: 'none',
            margin: 0,
            cursor: 'pointer',
            ...trackStyle,
          }}
        />
      </div>
      <div style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', fontSize: 11.5, color: 'var(--text-3)', fontVariantNumeric: 'tabular-nums' }}>
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  )
}

// ─── Main screen ──────────────────────────────────────────────────────────────

export function OnboardingScreen() {
  const [idx, setIdx] = React.useState(0)
  const [name, setName] = React.useState('')
  const [goal, setGoal] = React.useState(null)          // null | 'lose_weight' | 'gain_mass' | 'tone' | 'maintain'
  const [height, setHeight] = React.useState(175)
  const [weight, setWeight] = React.useState(70)
  const [done, setDone] = React.useState(false)         // «Готово!» overlay
  const [returnToReview, setReturnToReview] = React.useState(false)
  const [nameFocused, setNameFocused] = React.useState(false)
  const [submitError, setSubmitError] = React.useState(null)
  const [skipError, setSkipError] = React.useState(null)

  const navigate = useNavigate()
  const updateProfile = useUpdateClientProfile()
  const completeOnboarding = useCompleteOnboarding()

  const LAST = 3

  // ── Slide transition classes ────────────────────────────────────────────────
  function slideStyle(i) {
    const base = {
      position: 'absolute',
      inset: 0,
      display: 'flex',
      flexDirection: 'column',
      padding: '14px 28px 0',
      transition: 'transform 0.34s cubic-bezier(0.32, 0.72, 0.2, 1), opacity 0.24s ease',
      pointerEvents: i === idx ? 'auto' : 'none',
    }
    if (i === idx) return { ...base, opacity: 1, transform: 'translateX(0)' }
    if (i < idx)   return { ...base, opacity: 0, transform: 'translateX(-36px)' }
    return { ...base, opacity: 0, transform: 'translateX(36px)' }
  }

  // ── Navigation ──────────────────────────────────────────────────────────────
  function goNext() {
    if (returnToReview) {
      setReturnToReview(false)
      setIdx(LAST)
    } else {
      setIdx(i => Math.min(LAST, i + 1))
    }
  }

  function goBack() {
    setReturnToReview(false)
    setIdx(i => Math.max(0, i - 1))
  }

  function goToStep(step) {
    setReturnToReview(true)
    setIdx(step)
  }

  // ── Finish (D-08): ONE atomic PATCH with profile + flag ─────────────────────
  async function handleFinish() {
    setSubmitError(null)
    try {
      await updateProfile.mutateAsync({
        firstName: name.trim() || undefined,
        goal: goal ?? undefined,
        heightCm: height,
        weightKg: weight,
        onboardingCompleted: true,   // D-08: MUST include — omitting causes auto-redirect loop
      })
      setDone(true)
    } catch (_e) {
      setSubmitError('Произошла ошибка. Попробуйте снова.')
    }
  }

  // ── Skip (D-05/D-08): ONLY the flag, no profile data ──────────────────────
  // WR-05 (Phase 999.5): navigate ONLY on success. If the PATCH that stamps
  // onboarding_completed_at fails, navigating to /home re-fires the auto-redirect
  // gate (still !onboardingCompletedAt) and bounces the user back here — an
  // unobservable loop. Surface a visible error and keep the user on the screen to retry.
  async function handleSkip() {
    setSkipError(null)
    try {
      await completeOnboarding.mutateAsync()
      navigate('/home', { replace: true })
    } catch (_e) {
      setSkipError('Не удалось пропустить. Попробуйте снова.')
    }
  }

  const isFinishing = updateProfile.isPending
  const isSkipping = completeOnboarding.isPending

  // ── CTA label per step ──────────────────────────────────────────────────────
  const ctaLabel = idx === LAST ? 'Перейти в «Мой зал»' : idx === 2 ? 'Почти готово' : 'Дальше'
  const ctaDisabled = idx === 1 && goal === null

  // ── Progress segments (3 segments = 3 reviewable steps; step 3 is review) ──
  const segFill = [idx >= 1, idx >= 2, idx >= 3]

  const displayName = name.trim()

  return (
    <div className="page" style={{ background: 'var(--bg)', position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      <StatusBar />

      {/* ── Top bar: back | progress (3 segs) | skip ─────────────────────── */}
      <div style={{
        height: 56, padding: '0 16px',
        display: 'flex', alignItems: 'center', gap: 12,
        flexShrink: 0,
      }}>
        {/* Back button — hidden on step 0 */}
        <button
          className="topbar-btn"
          onClick={goBack}
          aria-label="Назад"
          hidden={idx === 0}
          style={{ width: 36, height: 36, padding: 0, border: '0.5px solid var(--border)' }}
        >
          <Icon name="chevronLeft" size={18} color="var(--text)" strokeWidth={2.2} />
        </button>

        {/* Progress bar — 3 segments */}
        <div style={{ flex: 1, display: 'flex', gap: 6 }}>
          {segFill.map((filled, i) => (
            <div key={i} style={{
              flex: 1, height: 5, borderRadius: 999,
              background: 'var(--border-strong)',
              overflow: 'hidden',
            }}>
              <div style={{
                height: '100%',
                width: filled ? '100%' : '0%',
                background: 'var(--accent)',
                borderRadius: 999,
                transition: 'width 0.4s cubic-bezier(0.32, 0.72, 0.2, 1)',
              }} />
            </div>
          ))}
        </div>

        {/* Skip button */}
        <button
          onClick={handleSkip}
          disabled={isSkipping}
          style={{
            border: 0, background: 'transparent',
            color: 'var(--text-3)', fontSize: 14, fontWeight: 600,
            cursor: isSkipping ? 'not-allowed' : 'pointer',
            padding: '6px 4px', flexShrink: 0,
            opacity: isSkipping ? 0.5 : 1,
            fontFamily: 'inherit',
          }}
        >
          {idx === LAST ? 'Заполню позже' : 'Пропустить'}
        </button>
      </div>

      {/* WR-05: skip-failure error — keeps the user on screen with a retry */}
      {skipError && (
        <div style={{ fontSize: 12.5, color: 'var(--danger)', textAlign: 'center', padding: '0 16px 4px' }}>
          {skipError}
        </div>
      )}

      {/* ── Slides ───────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>

        {/* STEP 0 — Имя */}
        <section
          aria-hidden={idx !== 0}
          style={slideStyle(0)}
        >
          <SpotScene step={0} />
          <div style={{ marginTop: 16, fontSize: 25, fontWeight: 700, letterSpacing: -0.5, lineHeight: 1.18, textWrap: 'balance' }}>
            Как тебя зовут?
          </div>
          <div style={{ marginTop: 9, fontSize: 14.5, lineHeight: 1.5, color: 'var(--text-2)', textWrap: 'pretty', maxWidth: 300 }}>
            Так мы будем обращаться к тебе в зале и в приложении.
          </div>

          <div
            className={`field${nameFocused ? ' focused' : ''}`}
            style={{
              marginTop: 26, display: 'flex', alignItems: 'center', gap: 8,
              padding: '0 16px', height: 58, boxShadow: 'var(--sh-1)',
            }}
          >
            <input
              type="text"
              autoComplete="given-name"
              placeholder="Имя"
              maxLength={24}
              value={name}
              onChange={e => setName(e.target.value)}
              onFocus={() => setNameFocused(true)}
              onBlur={() => setNameFocused(false)}
              onKeyDown={e => { if (e.key === 'Enter') goNext() }}
              style={{
                flex: 1, appearance: 'none', border: 0, background: 'transparent',
                height: '100%', padding: 0,
                fontFamily: 'inherit', fontSize: 18, fontWeight: 500,
                color: 'var(--text)', outline: 'none', letterSpacing: -0.2,
              }}
            />
          </div>

          <div style={{ marginTop: 'auto', padding: '16px 0 26px' }}>
            <button
              className="btn btn-accent"
              style={{ width: '100%', height: 54 }}
              onClick={goNext}
            >
              Дальше
            </button>
          </div>
        </section>

        {/* STEP 1 — Цель */}
        <section
          aria-hidden={idx !== 1}
          style={slideStyle(1)}
        >
          <SpotScene step={1} />
          <div style={{ marginTop: 16, fontSize: 25, fontWeight: 700, letterSpacing: -0.5, lineHeight: 1.18, textWrap: 'balance' }}>
            Какая цель?
          </div>
          <div style={{ marginTop: 9, fontSize: 14.5, lineHeight: 1.5, color: 'var(--text-2)', textWrap: 'pretty', maxWidth: 300 }}>
            Подберём программу и подсказки под неё. Можно поменять потом.
          </div>

          <div style={{ marginTop: 24, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {GOALS.map(g => {
              const sel = goal === g.code
              return (
                <button
                  key={g.code}
                  type="button"
                  aria-pressed={sel}
                  onClick={() => setGoal(g.code)}
                  style={{
                    position: 'relative',
                    background: sel
                      ? 'color-mix(in oklab, var(--accent-soft) 55%, var(--surface))'
                      : 'var(--surface)',
                    border: `1.5px solid ${sel ? 'var(--accent)' : 'var(--border)'}`,
                    borderRadius: 18,
                    padding: '16px 14px 15px',
                    textAlign: 'left',
                    cursor: 'pointer',
                    boxShadow: 'var(--sh-1)',
                    transition: 'transform 0.12s ease, border-color 0.15s, background 0.15s',
                    fontFamily: 'inherit',
                  }}
                >
                  {/* Goal icon box */}
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    width: 40, height: 40, borderRadius: 12,
                    background: sel ? 'var(--accent)' : 'var(--surface-2)',
                    color: sel ? '#06120c' : 'var(--text-2)',
                    transition: 'background 0.15s, color 0.15s',
                  }}>
                    <Icon name={g.icon} size={22} color="currentColor" strokeWidth={2} />
                  </span>
                  {/* Name */}
                  <span style={{
                    display: 'block', marginTop: 12,
                    fontSize: 15, fontWeight: 650, letterSpacing: -0.2,
                    color: 'var(--text)',
                  }}>
                    {g.name}
                  </span>
                  {/* Desc */}
                  <span style={{
                    display: 'block', marginTop: 3,
                    fontSize: 12, lineHeight: 1.35, color: 'var(--text-3)',
                  }}>
                    {g.desc}
                  </span>
                  {/* Check circle */}
                  <span style={{
                    position: 'absolute', top: 13, right: 13,
                    width: 20, height: 20, borderRadius: 999,
                    background: 'var(--accent)', color: '#06120c',
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    opacity: sel ? 1 : 0,
                    transform: sel ? 'scale(1)' : 'scale(0.5)',
                    transition: 'opacity 0.15s, transform 0.18s cubic-bezier(0.32, 1.6, 0.32, 1)',
                  }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12l5 5L20 7" />
                    </svg>
                  </span>
                </button>
              )
            })}
          </div>

          <div style={{ marginTop: 'auto', padding: '16px 0 26px' }}>
            <button
              className="btn btn-accent"
              style={{ width: '100%', height: 54, opacity: ctaDisabled ? 0.35 : 1, cursor: ctaDisabled ? 'not-allowed' : 'pointer' }}
              disabled={ctaDisabled}
              onClick={goNext}
            >
              Дальше
            </button>
          </div>
        </section>

        {/* STEP 2 — Рост и вес */}
        <section
          aria-hidden={idx !== 2}
          style={slideStyle(2)}
        >
          <SpotScene step={2} />
          <div style={{ marginTop: 16, fontSize: 25, fontWeight: 700, letterSpacing: -0.5, lineHeight: 1.18, textWrap: 'balance' }}>
            Рост и вес
          </div>
          <div style={{ marginTop: 9, fontSize: 14.5, lineHeight: 1.5, color: 'var(--text-2)', textWrap: 'pretty', maxWidth: 300 }}>
            Нужны, чтобы считать нагрузку и прогресс. Точность необязательна.
          </div>

          <div style={{ marginTop: 22 }}>
            <MetricSlider
              id="height"
              label="Рост"
              unit="см"
              min={140}
              max={210}
              value={height}
              onChange={setHeight}
            />
          </div>
          <div style={{ marginTop: 14 }}>
            <MetricSlider
              id="weight"
              label="Вес"
              unit="кг"
              min={40}
              max={150}
              value={weight}
              onChange={setWeight}
            />
          </div>

          <div style={{ marginTop: 'auto', padding: '16px 0 26px' }}>
            <button
              className="btn btn-accent"
              style={{ width: '100%', height: 54 }}
              onClick={goNext}
            >
              Почти готово
            </button>
          </div>
        </section>

        {/* STEP 3 — Проверка */}
        <section
          aria-hidden={idx !== 3}
          style={slideStyle(3)}
        >
          <SpotScene step={3} />
          <div style={{ marginTop: 16, fontSize: 25, fontWeight: 700, letterSpacing: -0.5, lineHeight: 1.18, textWrap: 'balance' }}>
            Всё верно?
          </div>
          <div style={{ marginTop: 9, fontSize: 14.5, lineHeight: 1.5, color: 'var(--text-2)', textWrap: 'pretty', maxWidth: 300 }}>
            Мы заполнили твои настройки. Нажми на строку, чтобы поправить.
          </div>

          {/* Review card */}
          <div style={{
            marginTop: 24,
            background: 'var(--surface)',
            border: '0.5px solid var(--border)',
            borderRadius: 'var(--r-lg)',
            boxShadow: 'var(--sh-2)',
            overflow: 'hidden',
          }}>
            {[
              { label: 'Имя',       icon: 'idCard', val: displayName || 'Без имени', step: 0 },
              { label: 'Цель',      icon: 'flag',   val: goal ? GOAL_NAME[goal] : 'Не выбрана', step: 1 },
              { label: 'Параметры', icon: 'ruler',  val: `${height} см · ${weight} кг`, step: 2 },
            ].map((row, i) => (
              <button
                key={row.label}
                type="button"
                onClick={() => goToStep(row.step)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 14,
                  padding: '15px 18px', width: '100%',
                  background: 'transparent',
                  border: 'none',
                  borderTop: i > 0 ? '0.5px solid var(--border)' : 'none',
                  cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit',
                  color: 'var(--text)',
                  transition: 'background 0.15s',
                }}
              >
                {/* Row icon */}
                <span style={{
                  width: 34, height: 34, borderRadius: 10,
                  background: 'var(--accent-soft)', color: 'var(--accent-deep)',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  <Icon name={row.icon} size={19} color="currentColor" strokeWidth={1.75} />
                </span>
                {/* Labels */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: 'var(--text-3)', fontWeight: 500 }}>
                    {row.label}
                  </div>
                  <div style={{
                    fontSize: 16, fontWeight: 600, color: 'var(--text)',
                    letterSpacing: -0.2, marginTop: 1,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {row.val}
                  </div>
                </div>
                {/* Edit chevron */}
                <span style={{ color: 'var(--text-3)', flexShrink: 0 }}>
                  <Icon name="chevronRight" size={16} color="currentColor" strokeWidth={2} />
                </span>
              </button>
            ))}
          </div>

          <div style={{ marginTop: 'auto', padding: '16px 0 26px' }}>
            {submitError && (
              <div style={{ fontSize: 12.5, color: 'var(--danger)', textAlign: 'center', marginBottom: 8 }}>
                {submitError}
              </div>
            )}
            <button
              className="btn btn-accent"
              style={{ width: '100%', height: 54 }}
              onClick={handleFinish}
              disabled={isFinishing}
            >
              {isFinishing
                ? <span style={{
                    width: 18, height: 18, borderRadius: 999,
                    border: '2px solid rgba(6,18,12,0.25)', borderTopColor: '#06120c',
                    animation: 'ptr-spin 0.7s linear infinite',
                    display: 'inline-block',
                  }} />
                : 'Перейти в «Мой зал»'}
            </button>
          </div>
        </section>
      </div>

      {/* ── «Готово!» overlay ─────────────────────────────────────────────── */}
      <div
        aria-hidden={!done}
        style={{
          position: 'absolute', inset: 0, zIndex: 40,
          background: [
            'radial-gradient(120% 70% at 50% -10%, color-mix(in oklab, var(--accent) 38%, transparent) 0%, transparent 55%)',
            'var(--bg)',
          ].join(', '),
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: 16, padding: '0 40px', textAlign: 'center',
          opacity: done ? 1 : 0,
          pointerEvents: done ? 'auto' : 'none',
          transition: 'opacity 0.26s ease',
        }}
      >
        {/* Circle with checkmark */}
        <div style={{
          width: 92, height: 92, borderRadius: 999,
          background: 'var(--accent)', color: '#06120c',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: [
            '0 0 0 12px color-mix(in oklab, var(--accent) 20%, transparent)',
            '0 16px 44px rgba(45,212,164,0.45)',
          ].join(', '),
          animation: done ? 'pop 0.45s cubic-bezier(0.32, 1.6, 0.32, 1) both' : 'none',
        }}>
          <Icon name="check" size={44} strokeWidth={2.6} color="#06120c" />
        </div>
        {/* Title */}
        <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: -0.4 }}>
          {displayName ? `Готово, ${displayName}!` : 'Готово!'}
        </div>
        {/* Subtitle */}
        <div style={{ fontSize: 14.5, color: 'var(--text-2)', lineHeight: 1.45, maxWidth: 280 }}>
          Настройки заполнены — открываем твою главную.
        </div>
        {/* CTA */}
        <button
          className="btn btn-accent"
          style={{ marginTop: 8, width: '100%', maxWidth: 280, height: 54 }}
          onClick={() => navigate('/home', { replace: true })}
        >
          Поехали
        </button>
      </div>
    </div>
  )
}
