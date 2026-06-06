/**
 * GymInfoSheet (Phase 86 GYM-01 — redesigned «О зале», quick 260606-uxo)
 *
 * Full-screen sub-sheet rendering live gym data from GET /api/v1/client/gym,
 * styled with the «О зале» (AboutGymScreen) design. Hybrid:
 *   • Real data: name/tagline/address/city/metro/hours/amenities/rules/contacts/social;
 *     open-closed + today index derived from hours + Europe/Moscow clock.
 *   • Working actions: Маршрут (Yandex Maps), Позвонить (tel:), Адрес (clipboard copy).
 *   • Decor (no API): live-occupancy widget, «Сегодня в зале» staff block, map illustration.
 *
 * No device frame / fake status bar — lives in the app shell sheet (onClose).
 * Bespoke CSS scoped under `.aboutgym`; global .card/.press/.fade-up/.t-* reused.
 *
 * Threat mitigations:
 *   T-86-09: Social/maps URLs built via fixed prefixes; external links use rel="noopener noreferrer"
 *   T-86-10: Generic error copy — no raw error/status echoed to UI
 */
import React from 'react'
import { Icon } from '@/components/Icon.jsx'
import { StatusBar } from '@/components/StatusBar.jsx'
import { PullToRefresh } from '@/components/PullToRefresh.jsx'
import { useClientGymInfo } from '@/data'

// ─── Bespoke «О зале» CSS (scoped under .aboutgym; keyframes ag-* to avoid clashes) ─
const AG_CSS = `
.aboutgym .appbar{padding:8px 16px 10px;display:flex;align-items:center;}
.aboutgym .back-btn{width:40px;height:40px;border-radius:999px;border:0.5px solid var(--border);background:var(--surface);cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:var(--sh-1);}
.aboutgym .mapview{position:relative;height:200px;overflow:hidden;margin:4px 16px 0;border-radius:20px;border:0.5px solid var(--border);box-shadow:var(--sh-2);--map-bg:#e4e7e1;--map-road:#fcfcfa;--map-road-2:#edeee9;--map-block:#dadcd2;--map-park:#cae0c3;}
body.dark .aboutgym .mapview{--map-bg:#191d18;--map-road:#2c322b;--map-road-2:#232820;--map-block:#21261e;--map-park:#1f3125;}
.aboutgym .map-svg{position:absolute;inset:0;width:100%;height:100%;}
.aboutgym .map-label{position:absolute;left:50%;top:50%;transform:translate(-50%,calc(-50% - 44px));z-index:4;white-space:nowrap;background:var(--surface);color:var(--text);font-size:12px;font-weight:600;letter-spacing:-0.1px;padding:7px 12px;border-radius:999px;box-shadow:0 6px 18px rgba(0,0,0,0.18);border:0.5px solid var(--border);}
.aboutgym .map-label::after{content:"";position:absolute;left:50%;bottom:-5px;transform:translateX(-50%) rotate(45deg);width:10px;height:10px;background:var(--surface);border-right:0.5px solid var(--border);border-bottom:0.5px solid var(--border);}
.aboutgym .pin-ping{transform-origin:center;animation:ag-pin-ping 2.4s cubic-bezier(0,0,0.2,1) infinite;}
@keyframes ag-pin-ping{0%{transform:translate(-50%,-50%) scale(0.5);opacity:0.5;}80%,100%{transform:translate(-50%,-50%) scale(2.8);opacity:0;}}
.aboutgym .sec{font-size:16px;font-weight:600;letter-spacing:-0.3px;color:var(--text);padding:20px 20px 8px;}
.aboutgym .qa{cursor:pointer;padding:14px 8px;background:var(--surface);color:var(--text);border-radius:var(--r-lg);border:0.5px solid var(--border);display:flex;flex-direction:column;align-items:center;gap:6px;transition:background 0.16s,color 0.16s,transform 0.1s ease;font-family:inherit;}
.aboutgym .qa:active{transform:scale(0.97);}
.aboutgym .qa.hot{background:var(--accent);color:#06120c;border-color:transparent;}
.aboutgym .qa .lbl{font-size:12px;font-weight:600;letter-spacing:-0.1px;}
.aboutgym .acc-list{margin-top:4px;background:var(--surface);border:0.5px solid var(--border);border-radius:var(--r-lg);overflow:hidden;}
.aboutgym .occ-bar{height:8px;border-radius:999px;background:var(--surface-2);overflow:hidden;}
.aboutgym .occ-fill{height:100%;width:0;border-radius:999px;background:linear-gradient(90deg,var(--accent),var(--accent-deep));transition:width 1.1s cubic-bezier(0.32,0.72,0.2,1);}
.aboutgym .live-pulse{width:7px;height:7px;border-radius:999px;background:var(--accent-deep);position:relative;}
.aboutgym .live-pulse::after{content:"";position:absolute;inset:0;border-radius:999px;background:var(--accent-deep);animation:ag-live-ping 1.8s cubic-bezier(0,0,0.2,1) infinite;}
@keyframes ag-live-ping{70%,100%{transform:scale(2.8);opacity:0;}}
.aboutgym .mchip{position:absolute;border-radius:4px;background:var(--accent);z-index:5;box-shadow:0 2px 6px rgba(0,0,0,0.15);}
.aboutgym .mchip.m1{width:10px;height:10px;right:16px;top:14px;transform:rotate(16deg);background:var(--accent-deep);}
.aboutgym .mchip.m2{width:7px;height:7px;right:36px;top:32px;border-radius:50%;animation-delay:0.8s;}
.aboutgym .route-time{position:absolute;left:13%;top:60%;z-index:5;display:inline-flex;align-items:center;gap:5px;background:var(--surface);color:var(--text);font-size:11px;font-weight:700;letter-spacing:-0.1px;padding:4px 9px 4px 8px;border-radius:999px;box-shadow:0 4px 12px rgba(0,0,0,0.16);border:0.5px solid var(--border);}
.aboutgym .amen{transition:transform 0.14s ease,border-color 0.16s ease;}
.aboutgym .amen:hover{transform:translateY(-2px);border-color:var(--border-strong);}
@media (prefers-reduced-motion: no-preference){
  .aboutgym .reveal{opacity:0;animation:ag-reveal 0.55s cubic-bezier(0.22,0.7,0.2,1) both;animation-delay:var(--d,0s);}
  .aboutgym .pin-drop{animation:ag-pin-drop 0.8s cubic-bezier(0.3,1.5,0.4,1) both;animation-delay:0.2s;}
  .aboutgym .route-anim{animation:ag-route-march 0.9s linear infinite;}
  .aboutgym .svg-ping{transform-box:fill-box;transform-origin:center;animation:ag-svg-ping 2.2s cubic-bezier(0,0,0.2,1) infinite;}
  .aboutgym .amen{opacity:0;animation:ag-pop-in 0.5s cubic-bezier(0.3,1.4,0.4,1) both;animation-delay:var(--d,0s);}
  .aboutgym .mchip{animation:ag-spot-float 3.6s ease-in-out infinite;}
}
@keyframes ag-reveal{from{opacity:0;transform:translateY(14px);}to{opacity:1;transform:translateY(0);}}
@keyframes ag-pin-drop{0%{transform:translate(-50%,calc(-50% - 60px));opacity:0;}70%{transform:translate(-50%,calc(-50% + 3px));opacity:1;}100%{transform:translate(-50%,calc(-50% - 9px));}}
@keyframes ag-route-march{to{stroke-dashoffset:-14;}}
@keyframes ag-svg-ping{0%{transform:scale(0.55);opacity:0.55;}80%,100%{transform:scale(2.8);opacity:0;}}
@keyframes ag-pop-in{0%{opacity:0;transform:scale(0.85) translateY(8px);}60%{transform:scale(1.02);}100%{opacity:1;transform:scale(1) translateY(0);}}
@keyframes ag-spot-float{0%,100%{transform:translateY(0) rotate(0);}50%{transform:translateY(-6px) rotate(12deg);}}
`

// ─── Decor (no API) ────────────────────────────────────────────────────────────
const OCC_TARGET = 23
const OCC_WIDTH = '45%'
const STAFF = { admin: 'Маша', trainers: 4, classes: 6 } // decor — no backend
const WALK_MIN = 5 // decor

// ─── Europe/Moscow "today" + open/closed (UI-SPEC §Hours) ───────────────────────
function getMoscowNow() {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: 'Europe/Moscow', hour: 'numeric', minute: 'numeric', weekday: 'short', hour12: false,
  }).formatToParts(new Date())
  const weekdayMap = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 }
  const todayIdx = weekdayMap[parts.find((p) => p.type === 'weekday')?.value] ?? 0
  const hour = parseInt(parts.find((p) => p.type === 'hour')?.value ?? '0', 10)
  const minute = parseInt(parts.find((p) => p.type === 'minute')?.value ?? '0', 10)
  return { todayIdx, nowMinutes: hour * 60 + minute }
}
const parseHHMM = (hhmm) => {
  const [h, m] = String(hhmm).split(':')
  return parseInt(h ?? '0', 10) * 60 + parseInt(m ?? '0', 10)
}

// ─── URL builders (fixed prefixes — T-86-09) ────────────────────────────────────
const telHref = (p) => 'tel:' + String(p).replace(/[^+\d]/g, '')
const socialHref = (s) =>
  s.kind === 'tg'
    ? 'https://t.me/' + encodeURIComponent(s.handle.replace(/^@/, ''))
    : 'https://instagram.com/' + encodeURIComponent(s.handle.replace(/^@/, ''))

// ─── Error state ────────────────────────────────────────────────────────────────
function GymInfoError() {
  return (
    <div style={{ padding: '40px 24px', textAlign: 'center' }}>
      <div style={{ width: 64, height: 64, borderRadius: 999, margin: '0 auto 16px', background: 'var(--danger-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon name="alertCircle" size={40} color="var(--danger)" />
      </div>
      <div className="t-h3">Не удалось загрузить информацию о зале</div>
      <div className="t-small" style={{ color: 'var(--text-2)', marginTop: 8 }}>Потяните вниз, чтобы попробовать снова.</div>
    </div>
  )
}

// ─── GymInfoSheet ─────────────────────────────────────────────────────────────
export function GymInfoSheet({ onClose }) {
  const gymInfoQuery = useClientGymInfo()
  const data = gymInfoQuery.data

  const [hoursOpen, setHoursOpen] = React.useState(false)
  const [rulesOpen, setRulesOpen] = React.useState(false)
  const [copyHot, setCopyHot] = React.useState(false)
  const [banner, setBanner] = React.useState(null) // { iconName, text, nonce }
  const bannerTimer = React.useRef(null)
  const copyTimer = React.useRef(null)
  const nonceRef = React.useRef(0)

  // Live occupancy (decor count-up + bar)
  const [occCount, setOccCount] = React.useState(0)
  const [occWidth, setOccWidth] = React.useState('0%')

  React.useEffect(() => {
    if (!data) return
    const reduce = typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false
    if (reduce) { setOccCount(OCC_TARGET); setOccWidth(OCC_WIDTH); return }
    const rafs = []
    rafs.push(requestAnimationFrame(() => {
      rafs.push(requestAnimationFrame(() => {
        setOccWidth(OCC_WIDTH)
        let start = null
        const tick = (now) => {
          if (start === null) start = now
          const p = Math.min(1, (now - start) / 1000)
          setOccCount(Math.round(OCC_TARGET * (1 - Math.pow(1 - p, 3))))
          if (p < 1) rafs.push(requestAnimationFrame(tick))
        }
        rafs.push(requestAnimationFrame(tick))
      }))
    }))
    return () => rafs.forEach((id) => cancelAnimationFrame(id))
  }, [data])

  const showBanner = React.useCallback((iconName, text) => {
    nonceRef.current += 1
    setBanner({ iconName, text, nonce: nonceRef.current })
    clearTimeout(bannerTimer.current)
    bannerTimer.current = setTimeout(() => setBanner(null), 2000)
  }, [])

  const addrText = data ? `${data.city ? data.city + ', ' : ''}${data.address}` : ''
  const onRoute = () => {
    window.open('https://yandex.ru/maps/?text=' + encodeURIComponent(addrText), '_blank', 'noopener')
    showBanner('navigation', `${WALK_MIN} мин пешком от тебя`)
  }
  const onCall = () => {
    if (data?.phone) { window.location.href = telHref(data.phone); showBanner('phone', `Звоним: ${data.phone}`) }
  }
  const onCopy = () => {
    if (navigator.clipboard) navigator.clipboard.writeText(addrText).catch(() => {})
    setCopyHot(true)
    showBanner('check', 'Адрес скопирован — открой Карты')
    clearTimeout(copyTimer.current)
    copyTimer.current = setTimeout(() => setCopyHot(false), 1600)
  }

  const handleRefresh = async () => { await gymInfoQuery.refetch() }

  // Live "today" + hours
  const { todayIdx, nowMinutes } = getMoscowNow()
  const hours = data?.hours ?? []
  const todayRow = todayIdx < hours.length ? hours[todayIdx] : null
  const todayHrs = todayRow ? `${todayRow.open}–${todayRow.close}` : ''
  const isOpenNow = todayRow ? (nowMinutes >= parseHHMM(todayRow.open) && nowMinutes < parseHHMM(todayRow.close)) : false

  const StaffRow = ({ iconName, label, value, sub }) => (
    <div style={{ padding: '14px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ width: 36, height: 36, borderRadius: 10, background: 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <Icon name={iconName} size={20} color="var(--text-2)" />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-mini" style={{ color: 'var(--text-3)', fontWeight: 600 }}>{label}</div>
        <div className="t-h3" style={{ marginTop: 2, fontSize: 16 }}>{value}</div>
        {sub && <div className="t-small" style={{ marginTop: 1 }}>{sub}</div>}
      </div>
    </div>
  )
  const Divider = () => <div style={{ height: 0.5, background: 'var(--border)', margin: '0 14px' }} />

  const ContactRow = ({ iconName, label, value, href, newtab }) => (
    <a
      href={href}
      {...(newtab ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      className="press"
      style={{ textDecoration: 'none', width: '100%', padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}
    >
      <div style={{ width: 32, height: 32, borderRadius: 10, background: 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <Icon name={iconName} size={16} color="var(--text)" />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-mini" style={{ color: 'var(--text-3)' }}>{label}</div>
        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text)', marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</div>
      </div>
      <Icon name="chevronRight" size={14} color="var(--text-3)" />
    </a>
  )

  return (
    <div style={{ position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)', display: 'flex', flexDirection: 'column', animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)' }}>
      <style>{AG_CSS}</style>
      <StatusBar />
      <PullToRefresh scrollPaddingTop={0} onRefresh={handleRefresh}>
        <div className="aboutgym">
          <div className="appbar">
            <button className="back-btn" onClick={onClose} aria-label="Назад">
              <Icon name="chevronLeft" size={22} color="var(--text)" strokeWidth={2.2} />
            </button>
          </div>

          {gymInfoQuery.isLoading && (
            <div className="t-small" style={{ color: 'var(--text-3)', textAlign: 'center', padding: 40 }}>Загрузка информации о зале…</div>
          )}
          {gymInfoQuery.isError && <GymInfoError />}

          {data && (
            <>
              {/* Map illustration (decor) */}
              <div className="mapview">
                <svg className="map-svg" viewBox="0 0 390 260" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
                  <rect width="390" height="260" style={{ fill: 'var(--map-bg)' }} />
                  <rect x="232" y="150" width="130" height="100" rx="6" style={{ fill: 'var(--map-park)' }} />
                  <rect x="-12" y="-12" width="122" height="96" rx="5" style={{ fill: 'var(--map-block)' }} />
                  <rect x="300" y="-12" width="110" height="92" rx="5" style={{ fill: 'var(--map-block)' }} />
                  <rect x="-12" y="172" width="150" height="110" rx="5" style={{ fill: 'var(--map-block)' }} />
                  <g style={{ stroke: 'var(--map-road-2)', strokeWidth: 22, strokeLinecap: 'round', fill: 'none' }}>
                    <path d="M-20 120 H410" /><path d="M150 -20 V280" />
                  </g>
                  <g style={{ stroke: 'var(--map-road)', strokeWidth: 14, strokeLinecap: 'round', fill: 'none' }}>
                    <path d="M-20 120 H410" /><path d="M150 -20 V280" /><path d="M-30 -20 L300 300" />
                  </g>
                  <g style={{ stroke: 'var(--map-road)', strokeWidth: 7, strokeLinecap: 'round', fill: 'none' }}>
                    <path d="M-20 56 H410" /><path d="M-20 200 H410" /><path d="M70 -20 V280" /><path d="M280 -20 V280" />
                  </g>
                  <path d="M70 206 Q120 178 150 152 T196 132" fill="none" className="route-anim" style={{ stroke: 'var(--accent-deep)', strokeWidth: 3.5, strokeLinecap: 'round', strokeDasharray: '5 9' }} />
                  <circle cx="70" cy="206" r="7" className="svg-ping" style={{ fill: 'var(--accent-deep)' }} />
                  <circle cx="70" cy="206" r="6" style={{ fill: 'var(--accent-deep)' }} />
                  <circle cx="70" cy="206" r="6" fill="none" style={{ stroke: 'var(--map-road)', strokeWidth: 2.5 }} />
                </svg>
                <svg className="pin-ping" width="60" height="60" viewBox="0 0 60 60" style={{ position: 'absolute', left: '50%', top: '50%', zIndex: 3 }}>
                  <circle cx="30" cy="30" r="13" style={{ fill: 'var(--accent)' }} />
                </svg>
                <svg width="34" height="42" viewBox="0 0 34 42" className="pin-drop" style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,calc(-50% - 9px))', zIndex: 4, filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.25))' }}>
                  <path d="M17 1C8.7 1 2 7.7 2 16c0 9.5 12 22 14.2 24.2a1.1 1.1 0 001.6 0C20 38 32 25.5 32 16 32 7.7 25.3 1 17 1z" style={{ fill: 'var(--accent-deep)' }} />
                  <circle cx="17" cy="16" r="6" fill="#fff" />
                </svg>
                {data.address && <div className="map-label">{data.address}</div>}
                <span className="mchip m1" />
                <span className="mchip m2" />
                <div className="route-time">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--accent-deep)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M3 11l18-8-8 18-2-8-8-2z" /></svg>
                  {WALK_MIN} мин пешком
                </div>
              </div>

              {/* Name / address */}
              <div className="reveal" style={{ '--d': '.04s', padding: '18px 20px 8px', position: 'relative' }}>
                {data.tagline && <div className="t-mini" style={{ color: 'var(--text-3)' }}>{data.tagline}</div>}
                <div className="t-display" style={{ marginTop: 4, letterSpacing: '-0.8px', fontSize: 28 }}>{data.name}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                  <span style={{ display: 'inline-flex' }}><Icon name="mapPin" size={14} color="var(--text-3)" /></span>
                  <div className="t-small" style={{ color: 'var(--text-2)' }}>{data.metro ? `${data.address} · ${data.metro}` : data.address}</div>
                </div>
              </div>

              {/* Quick actions */}
              <div className="reveal" style={{ '--d': '.09s', padding: '12px 16px 8px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                <button className="qa" onClick={onRoute}>
                  <span><Icon name="navigation" size={20} color="var(--text)" strokeWidth={1.9} /></span>
                  <div className="lbl">Маршрут</div>
                </button>
                <button className="qa" onClick={onCall}>
                  <span><Icon name="phone" size={20} color="var(--text)" strokeWidth={1.9} /></span>
                  <div className="lbl">Позвонить</div>
                </button>
                <button className={'qa' + (copyHot ? ' hot' : '')} onClick={onCopy}>
                  <span><Icon name="copy" size={20} color={copyHot ? '#06120c' : 'var(--text)'} strokeWidth={1.9} /></span>
                  <div className="lbl">{copyHot ? 'Скопировано' : 'Адрес'}</div>
                </button>
              </div>

              {banner && (
                <div style={{ padding: '0 16px 8px' }}>
                  <div key={banner.nonce} className="fade-up" style={{ background: 'var(--text)', color: 'var(--bg)', padding: '10px 14px', borderRadius: 12, display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, fontWeight: 500 }}>
                    <Icon name={banner.iconName} size={16} color="var(--bg)" strokeWidth={2.2} />
                    <span>{banner.text}</span>
                  </div>
                </div>
              )}

              {/* Live occupancy (decor) */}
              <div className="reveal" style={{ '--d': '.14s', padding: '8px 16px' }}>
                <div className="card" style={{ padding: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="live-pulse" />
                      <span className="t-mini" style={{ color: 'var(--accent-deep)', letterSpacing: '0.5px' }}>Сейчас в зале</span>
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-2)' }}>Средняя загрузка</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, marginTop: 10 }}>
                    <span className="t-num" style={{ fontSize: 38, fontWeight: 800, letterSpacing: '-1.5px', lineHeight: 0.9, color: 'var(--text)' }}>{occCount}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-3)', paddingBottom: 5 }}>человек тренируется</span>
                  </div>
                  <div className="occ-bar" style={{ marginTop: 14 }}>
                    <div className="occ-fill" style={{ width: occWidth }} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 7 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-3)' }}>Свободно · хорошее время зайти</span>
                    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-deep)' }}>{OCC_WIDTH}</span>
                  </div>
                </div>
              </div>

              {/* Hours */}
              {hours.length > 0 && (
                <div className="reveal" style={{ '--d': '.19s', padding: '8px 16px' }}>
                  <button className="card press" onClick={() => setHoursOpen((v) => !v)} style={{ width: '100%', padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12, background: 'var(--surface)', border: '0.5px solid var(--border)', cursor: 'pointer', textAlign: 'left' }}>
                    <div style={{ width: 36, height: 36, borderRadius: 10, background: 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Icon name="clock" size={18} color="var(--text)" />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div className="t-h3" style={{ fontSize: 15 }}>Часы работы</div>
                      <div className="t-small" style={{ marginTop: 1 }}>
                        {isOpenNow ? `Сейчас открыто · до ${todayRow.close}` : todayRow ? `Закрыто · сегодня ${todayHrs}` : 'Расписание ниже'}
                      </div>
                    </div>
                    <div style={{ transition: 'transform 0.18s', transform: hoursOpen ? 'rotate(180deg)' : 'rotate(0)' }}>
                      <Icon name="chevronDown" size={16} color="var(--text-3)" />
                    </div>
                  </button>
                  {hoursOpen && (
                    <div className="acc-list fade-up">
                      {hours.map((h, i) => {
                        const today = i === todayIdx
                        return (
                          <div key={h.d} style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: i < hours.length - 1 ? '0.5px solid var(--border)' : undefined, background: today ? 'var(--surface-2)' : 'transparent' }}>
                            <div style={{ fontSize: 14, fontWeight: today ? 700 : 500, color: today ? 'var(--text)' : 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 8 }}>
                              {h.d}
                              {today && <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 999, background: 'var(--accent)', color: '#06120c', fontWeight: 700, letterSpacing: '0.3px' }}>СЕГОДНЯ</span>}
                            </div>
                            <div className="t-num" style={{ fontSize: 14, color: today ? 'var(--text)' : 'var(--text-2)', fontWeight: today ? 600 : 500 }}>{h.open}–{h.close}</div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Amenities */}
              {data.amenities && data.amenities.length > 0 && (
                <>
                  <div className="sec reveal" style={{ '--d': '.24s' }}>Что есть в зале</div>
                  <div style={{ padding: '0 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    {data.amenities.map((a, i) => (
                      <div key={a.label} className="card amen" style={{ '--d': `${(0.26 + i * 0.05).toFixed(2)}s`, padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ width: 32, height: 32, borderRadius: 10, background: 'var(--accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                          <Icon name={a.icon} size={16} color="var(--accent-deep)" />
                        </div>
                        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>{a.label}</div>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {/* Staff today (decor) */}
              <div className="sec reveal" style={{ '--d': '.3s' }}>Сегодня в зале</div>
              <div className="reveal" style={{ '--d': '.31s', padding: '0 16px' }}>
                <div className="card" style={{ padding: 4 }}>
                  <StaffRow iconName="user" label="Администратор" value={STAFF.admin} sub="Подходи на ресепшн с любым вопросом" />
                  <Divider />
                  <StaffRow iconName="flame" label="Тренеры на смене" value={`${STAFF.trainers}`} sub="Можешь записаться или взять тренировку" />
                  <Divider />
                  <StaffRow iconName="calendar" label="Групповых занятий" value={`${STAFF.classes}`} sub="С 7:00 до 21:00" />
                </div>
              </div>

              {/* Contacts */}
              {(data.phone || data.email || (data.social && data.social.length > 0)) && (
                <>
                  <div className="sec reveal" style={{ '--d': '.34s' }}>Связаться</div>
                  <div className="reveal" style={{ '--d': '.35s', padding: '0 16px' }}>
                    <div className="card" style={{ padding: 4 }}>
                      {data.phone && <ContactRow iconName="phone" label="Телефон" value={data.phone} href={telHref(data.phone)} />}
                      {data.email && (<>{data.phone && <Divider />}<ContactRow iconName="chat" label="Email" value={data.email} href={'mailto:' + data.email} /></>)}
                      {(data.social ?? []).map((s) => (
                        <React.Fragment key={s.kind}>
                          <Divider />
                          <ContactRow iconName={s.kind === 'tg' ? 'telegram' : 'instagram'} label={s.label} value={s.handle} href={socialHref(s)} newtab />
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {/* Rules */}
              {data.rules && data.rules.length > 0 && (
                <>
                  <div className="sec reveal" style={{ '--d': '.38s' }}>Правила зала</div>
                  <div style={{ padding: '0 16px 24px' }}>
                    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                      <button onClick={() => setRulesOpen((v) => !v)} style={{ width: '100%', padding: '14px 16px', border: 0, cursor: 'pointer', background: 'transparent', textAlign: 'left', display: 'flex', alignItems: 'center', gap: 12, fontFamily: 'inherit' }}>
                        <div style={{ width: 32, height: 32, borderRadius: 10, background: 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                          <Icon name="info" size={16} color="var(--text)" />
                        </div>
                        <div style={{ flex: 1, fontSize: 14, fontWeight: 500, color: 'var(--text)' }}>
                          {rulesOpen ? 'Свернуть' : `Все ${data.rules.length} правил зала`}
                        </div>
                        <div style={{ transition: 'transform 0.18s', transform: rulesOpen ? 'rotate(180deg)' : 'rotate(0)' }}>
                          <Icon name="chevronDown" size={16} color="var(--text-3)" />
                        </div>
                      </button>
                      {rulesOpen && (
                        <div className="fade-up" style={{ padding: '0 16px 14px' }}>
                          <div style={{ borderTop: '0.5px solid var(--border)', paddingTop: 12, display: 'flex', flexDirection: 'column', gap: 12 }}>
                            {data.rules.map((r, i) => (
                              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                                <div style={{ flexShrink: 0, width: 22, height: 22, borderRadius: 999, background: 'var(--surface-2)', color: 'var(--text-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, fontVariantNumeric: 'tabular-nums', marginTop: 1 }}>{i + 1}</div>
                                <div style={{ fontSize: 13.5, color: 'var(--text-2)', lineHeight: 1.5, flex: 1 }}>{r}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}

              <div style={{ height: 32 }} />
            </>
          )}
        </div>
      </PullToRefresh>
    </div>
  )
}
