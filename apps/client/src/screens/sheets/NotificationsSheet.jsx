/**
 * NotificationsSheet (Phase 87 INBOX-05) — integrated design.
 *
 * Visual design ported from the user-provided NotificationsScreen.jsx
 * (quick task 260606-szy): segmented Все/Новые filter, grouped Сегодня/Вчера/Ранее
 * list, swipe + long-press gestures, pull-to-refresh, toast, empty state, animations.
 *
 * Integration deltas from the standalone mockup:
 *   - Device frame / fake status bar removed (lives inside the app shell).
 *   - Own :root / body.dark token blocks removed → uses the app's shared design tokens.
 *   - All CSS scoped under `.notif-screen` so it never clobbers the app's global
 *     .card/.seg/.press/.scroller/.t-* classes.
 *   - Mock data replaced with the real API via the @/data swap seam:
 *       useClientNotifications / useMarkNotificationRead / useMarkAllNotificationsRead.
 *   - Gestures mapped to the supported API (no delete / mark-unread endpoints exist):
 *       swipe-left  → mark read (accent "Прочитать" action)
 *       long-press  → "Отметить прочитанным"
 *       card tap    → mark read
 *       header "Прочитать" → mark all read
 *   - Group + relative time derived client-side from createdAt (Europe/Moscow, Intl-only).
 *
 * API contract:
 *   GET   /api/v1/client/notifications?page=N → { items, total, page, pageSize, unreadCount }
 *   PATCH /api/v1/client/notifications/{id}/read → 200 NotificationItem
 *   PATCH /api/v1/client/notifications/read-all → 204
 */
import { useCallback, useEffect, useRef, useState, Fragment } from 'react'
import {
  useClientNotifications,
  useMarkNotificationRead,
  useMarkAllNotificationsRead,
} from '@/data'

// ─── Feature flag (INBOX-05 kill-switch anchor) ──────────────────────────────
const NOTIFICATIONS_FEATURE_FLAGS = {
  notificationsInbox: true,
}

/* ---------- Scoped styles (design verbatim; tokens/frame removed) ---------- */
const CSS = `
.notif-screen { position: absolute; inset: 0; z-index: 220; background: var(--bg);
  display: flex; flex-direction: column; font-family: var(--font);
  animation: nfx-up 0.32s cubic-bezier(0.32,0.72,0.2,1); }
@keyframes nfx-up { from { transform: translateY(14px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

.notif-screen .t-num { font-variant-numeric: tabular-nums; }
.notif-screen .t-mini { font-size: 11px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; color: var(--text-3); }
.notif-screen .t-small { font-size: 13px; font-weight: 400; line-height: 1.4; color: var(--text-2); }
.notif-screen .t-h3 { font-size: 17px; font-weight: 600; letter-spacing: -0.2px; line-height: 1.25; color: var(--text); }

/* Header */
.notif-screen .nav {
  position: relative; flex-shrink: 0;
  padding: 50px 12px 8px;
  display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 6px;
}
.notif-screen .nav > .icon-btn:first-child { justify-self: start; }
.notif-screen .nav-title { display: flex; align-items: center; justify-content: center; font-size: 15px; white-space: nowrap; }
.notif-screen .icon-btn {
  width: 36px; height: 36px; border-radius: 999px; border: 0;
  background: var(--surface); cursor: pointer; padding: 0;
  display: flex; align-items: center; justify-content: center;
}
.notif-screen .nav-right { display: flex; align-items: center; gap: 2px; justify-self: end; }
.notif-screen .nav-action {
  border: 0; background: transparent; font-family: inherit;
  font-size: 13px; font-weight: 600; padding: 6px 8px; cursor: pointer;
  color: var(--text); border-radius: 999px; white-space: nowrap;
}
.notif-screen .nav-action:disabled { color: var(--text-3); cursor: default; }

/* Segmented control */
.notif-screen .seg { display: flex; gap: 2px; padding: 3px; background: var(--surface-2); border: 0.5px solid var(--border); border-radius: 999px; }
.notif-screen .seg-item {
  appearance: none; border: 0; background: transparent; cursor: pointer;
  height: 32px; border-radius: 999px;
  font-family: inherit; font-size: 12.5px; font-weight: 600; color: var(--text-2);
  transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}
.notif-screen .seg-item.active { background: var(--text); color: var(--bg); box-shadow: 0 1px 4px rgba(0,0,0,0.18); }

/* Scroll body */
.notif-screen .scroller { flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; position: relative; }
.notif-screen .scroller::-webkit-scrollbar { display: none; }

/* Pull to refresh */
.notif-screen .ptr { position: absolute; top: 0; left: 0; right: 0; height: 46px; display: flex; align-items: center; justify-content: center; opacity: 0; pointer-events: none; z-index: 0; }
.notif-screen .ptr svg { color: var(--text-3); }
.notif-screen .ptr.spin svg { animation: nfx-spin 0.7s linear infinite; }
@keyframes nfx-spin { to { transform: rotate(360deg); } }

.notif-screen .card { background: var(--surface); border: 0.5px solid var(--border); border-radius: var(--r-lg); box-shadow: var(--sh-1); }
.notif-screen .press { transition: transform 0.1s ease, background 0.15s ease; cursor: pointer; }
.notif-screen .press:active { transform: scale(0.985); }

/* Notification list */
.notif-screen .list { position: relative; display: flex; flex-direction: column; padding: 0 16px 24px; }
.notif-screen .group-head { padding: 11px 4px 6px; display: flex; align-items: center; gap: 8px; }
.notif-screen .group-head .gh-count { color: var(--text-3); font-weight: 600; }

.notif-screen .swipe { position: relative; border-radius: 16px; overflow: hidden; margin-bottom: 6px; }
.notif-screen .swipe-action {
  position: absolute; inset: 0; background: transparent;
  display: flex; align-items: center; justify-content: flex-end;
  gap: 7px; padding-right: 22px;
  color: var(--on-accent); font-size: 13.5px; font-weight: 700;
  opacity: 0; transition: opacity 0.15s ease;
}
.notif-screen .swipe.armed .swipe-action { background: var(--accent); opacity: 1; }
.notif-screen .swipe-card {
  position: relative; z-index: 1; display: block; width: 100%; text-align: left;
  border-radius: 16px; background: var(--surface-2); border: 0.5px solid var(--border);
  color: var(--text); padding: 11px 13px; cursor: pointer; touch-action: pan-y;
  transition: transform 0.26s cubic-bezier(0.32,0.72,0.2,1);
  -webkit-user-select: none; user-select: none;
}
.notif-screen .swipe-card.unread { background: var(--surface); border-color: var(--border-strong); }

.notif-screen .n-row { display: flex; gap: 11px; align-items: flex-start; }
.notif-screen .n-ic { width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0; margin-top: 1px; display: flex; align-items: center; justify-content: center; }
.notif-screen .n-main { flex: 1; min-width: 0; }
.notif-screen .n-top { display: flex; align-items: center; gap: 7px; }
.notif-screen .n-title { flex: 1; min-width: 0; font-size: 14.5px; font-weight: 600; letter-spacing: -0.2px; line-height: 1.3; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.notif-screen .n-dot { width: 7px; height: 7px; border-radius: 999px; background: var(--accent); flex-shrink: 0; }
.notif-screen .n-body { margin-top: 2px; font-size: 12.5px; line-height: 1.35; color: var(--text-2); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.notif-screen .n-time { font-size: 11px; font-weight: 600; letter-spacing: 0.2px; color: var(--text-3); flex-shrink: 0; }

.notif-screen .empty { margin: 4px 0; padding: 40px 24px; display: flex; flex-direction: column; align-items: center; text-align: center; gap: 8px; }
.notif-screen .empty-ic { width: 56px; height: 56px; border-radius: 16px; margin-bottom: 6px; background: var(--accent-soft); display: flex; align-items: center; justify-content: center; }

.notif-screen .fade-up { animation: nfx-fade 0.32s cubic-bezier(0.32,0.72,0.2,1) both; }
@keyframes nfx-fade { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.notif-screen .sk-card { height: 64px; border-radius: 16px; margin-bottom: 6px; background: linear-gradient(90deg, var(--surface-2) 0%, var(--surface) 50%, var(--surface-2) 100%); background-size: 200% 100%; animation: nfx-sk 1.2s ease-in-out infinite; }
@keyframes nfx-sk { from { background-position: 200% 0; } to { background-position: -200% 0; } }

/* Long-press action sheet */
.notif-screen .sheet-backdrop { position: absolute; inset: 0; z-index: 80; background: rgba(0,0,0,0.32); opacity: 0; pointer-events: none; transition: opacity 0.25s ease; }
.notif-screen .sheet-backdrop.show { opacity: 1; pointer-events: auto; }
.notif-screen .sheet { position: absolute; left: 8px; right: 8px; bottom: 8px; z-index: 81; background: var(--surface); border: 0.5px solid var(--border); border-radius: 24px; box-shadow: var(--sh-2); padding: 8px; transform: translateY(150%); transition: transform 0.34s cubic-bezier(0.32,0.72,0.2,1); }
.notif-screen .sheet.show { transform: translateY(0); }
.notif-screen .sheet-title { padding: 12px 14px 6px; }
.notif-screen .sheet-btn { display: flex; align-items: center; gap: 12px; width: 100%; border: 0; background: transparent; font-family: inherit; font-size: 15px; font-weight: 600; color: var(--text); padding: 14px; border-radius: 14px; cursor: pointer; text-align: left; }
.notif-screen .sheet-btn:hover { background: var(--surface-2); }
.notif-screen .sheet-cancel { margin-top: 4px; justify-content: center; background: var(--surface-2); color: var(--text-2); }

/* Toast */
.notif-screen .toast { position: absolute; left: 50%; bottom: 40px; transform: translate(-50%, 16px); z-index: 90; background: var(--text); color: var(--bg); font-size: 13.5px; font-weight: 600; padding: 11px 18px; border-radius: 999px; box-shadow: 0 12px 30px rgba(0,0,0,0.28); opacity: 0; pointer-events: none; transition: opacity 0.22s ease, transform 0.28s cubic-bezier(0.32,0.72,0.2,1); white-space: nowrap; }
.notif-screen .toast.show { opacity: 1; transform: translate(-50%, 0); }
`

/* ---------- Иконки ---------- */
const ICON = {
  tag: '<path d="M3 12V4a1 1 0 011-1h8l9 9-9 9-9-9z"/><circle cx="8" cy="8" r="1.4" fill="currentColor" stroke="none"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  card: '<rect x="2.5" y="5" width="19" height="14" rx="3"/><path d="M2.5 9.5h19"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.5"/>',
  alert: '<path d="M12 3l9 16H3L12 3z"/><path d="M12 10v4M12 16.5v.5"/>',
  sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z"/>',
  check: '<path d="M5 12l5 5L20 6"/>',
}

function Ico({ name, size, color = 'currentColor', sw = 1.9 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color}
      strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round"
      dangerouslySetInnerHTML={{ __html: ICON[name] || ICON.info }} />
  )
}

/* Тон + иконка для каждого вида серверного уведомления (INBOX-03 kinds) */
const TONE_SCHEDULE = 'oklch(0.62 0.14 42)'
const TONE_ACCENT = 'oklch(0.60 0.13 162)'
const KIND_META = {
  booking_confirmed: { icon: 'calendar', tone: TONE_SCHEDULE },
  booking_cancelled_by_client: { icon: 'calendar', tone: 'var(--danger)' },
  booking_cancelled_by_owner: { icon: 'calendar', tone: 'var(--danger)' },
  booking_rescheduled: { icon: 'calendar', tone: TONE_SCHEDULE },
  payment_succeeded: { icon: 'card', tone: TONE_ACCENT },
  autopay_charge_succeeded: { icon: 'card', tone: TONE_ACCENT },
  autopay_charge_failed: { icon: 'alert', tone: 'var(--danger)' },
}
const soft = (c, p) => `color-mix(in oklab, ${c} ${p}%, var(--surface))`

/* ---------- Время / группа (Europe/Moscow, Intl-only) ---------- */
const MSK = 'Europe/Moscow'
function mskDateKey(ms) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: MSK, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(ms))
}
function bucketAndTime(iso) {
  const now = Date.now()
  const key = mskDateKey(new Date(iso).getTime())
  const todayKey = mskDateKey(now)
  const yKey = mskDateKey(now - 86400000)
  const group = key === todayKey ? 'today' : key === yKey ? 'yesterday' : 'earlier'
  let at
  if (group === 'earlier') {
    at = new Intl.DateTimeFormat('ru-RU', { timeZone: MSK, day: 'numeric', month: 'short' })
      .format(new Date(iso)).replace(/\.$/, '')
  } else {
    at = new Intl.DateTimeFormat('ru-RU', { timeZone: MSK, hour: '2-digit', minute: '2-digit', hour12: false })
      .format(new Date(iso))
  }
  return { group, at }
}

const GROUPS = [
  { key: 'today', label: 'Сегодня' },
  { key: 'yesterday', label: 'Вчера' },
  { key: 'earlier', label: 'Ранее' },
]

export function NotificationsSheet({ onClose }) {
  // IN-01 (Rules of Hooks): ALL hooks run unconditionally before any early return.
  const query = useClientNotifications(1)
  const markReadM = useMarkNotificationRead()
  const markAllM = useMarkAllNotificationsRead()

  const [filter, setFilter] = useState('all') // 'all' | 'unread'
  const [optimisticRead, setOptimisticRead] = useState(() => new Set())
  const [allRead, setAllRead] = useState(false)

  const [toastMsg, setToastMsg] = useState('')
  const [toastShow, setToastShow] = useState(false)
  const toastTimer = useRef(null)

  const [sheetItemId, setSheetItemId] = useState(null)
  const [sheetShow, setSheetShow] = useState(false)
  const [backShow, setBackShow] = useState(false)

  const scrollerRef = useRef(null)
  const listRef = useRef(null)
  const ptrRef = useRef(null)
  const activeRef = useRef(null)
  const pullRef = useRef({ pStart: null, pulling: false, loading: false, pull: 0 })

  const serverItems = query.data?.items ?? []
  const items = serverItems.map((n) => {
    const { group, at } = bucketAndTime(n.createdAt)
    const unread = n.readAt === null && !allRead && !optimisticRead.has(n.id)
    return { ...n, group, at, unread }
  })
  const itemsRef = useRef(items)
  itemsRef.current = items
  const unread = items.filter((n) => n.unread).length

  const toast = useCallback((msg) => {
    setToastMsg(msg)
    setToastShow(true)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToastShow(false), 1700)
  }, [])

  /* ── Мутации (только то, что поддерживает API: mark-read одного + всех) ── */
  const markRead = useCallback((id) => {
    setOptimisticRead((prev) => {
      const s = new Set(prev)
      s.add(id)
      return s
    })
    markReadM.mutate(id, {
      onError: () =>
        setOptimisticRead((prev) => {
          const s = new Set(prev)
          s.delete(id)
          return s
        }),
    })
  }, [markReadM])

  const markAll = useCallback(() => {
    if (unread === 0) return
    setAllRead(true)
    markAllM.mutate(undefined, { onError: () => setAllRead(false) })
  }, [unread, markAllM])

  const runCardTap = useCallback((n) => {
    if (n.unread) markRead(n.id)
  }, [markRead])

  const openSheet = useCallback((id) => {
    setSheetItemId(id)
    setBackShow(true)
    requestAnimationFrame(() => setSheetShow(true))
  }, [])
  const closeSheet = useCallback(() => {
    setSheetShow(false)
    setBackShow(false)
  }, [])

  /* ── Жесты карточки: свайп-влево → «прочитать» (без удаления — нет API) ── */
  useEffect(() => {
    const onMove = (e) => {
      const a = activeRef.current
      if (!a) return
      const dx = e.clientX - a.x0
      const dy = e.clientY - a.y0
      if (Math.abs(dx) > 6 || Math.abs(dy) > 6) {
        a.moved = true
        clearTimeout(a.timer)
      }
      if (Math.abs(dx) > Math.abs(dy)) {
        a.dx = dx
        let t = Math.min(0, dx)
        if (t < -110) t = -110
        a.wrap.classList.toggle('armed', t < 0)
        a.card.style.transform = 'translateX(' + t + 'px)'
      }
    }
    const onUp = () => {
      const a = activeRef.current
      if (!a) return
      activeRef.current = null
      clearTimeout(a.timer)
      a.card.style.transition = ''
      if (a.dx <= -70) {
        const n = itemsRef.current.find((x) => x.id === a.id)
        if (n && n.unread) markRead(a.id)
      }
      a.card.style.transform = 'translateX(0)'
      setTimeout(() => a.wrap.classList.remove('armed'), 180)
      if (!a.moved && !a.longFired) {
        const n = itemsRef.current.find((x) => x.id === a.id)
        if (n) runCardTap(n)
      }
    }
    const onCancel = () => {
      const a = activeRef.current
      if (!a) return
      activeRef.current = null
      clearTimeout(a.timer)
      a.card.style.transition = ''
      a.card.style.transform = 'translateX(0)'
      setTimeout(() => a.wrap.classList.remove('armed'), 180)
    }
    document.addEventListener('pointermove', onMove)
    document.addEventListener('pointerup', onUp)
    document.addEventListener('pointercancel', onCancel)
    return () => {
      document.removeEventListener('pointermove', onMove)
      document.removeEventListener('pointerup', onUp)
      document.removeEventListener('pointercancel', onCancel)
    }
  }, [markRead, runCardTap])

  const onCardPointerDown = (e, id) => {
    if (e.button != null && e.button !== 0) return
    const card = e.currentTarget
    const wrap = card.closest('.swipe')
    activeRef.current = {
      wrap, card, id,
      x0: e.clientX, y0: e.clientY, dx: 0, moved: false, longFired: false,
      timer: setTimeout(() => {
        const a = activeRef.current
        if (a && !a.moved) {
          a.longFired = true
          if (navigator.vibrate) navigator.vibrate(8)
          openSheet(id)
        }
      }, 450),
    }
    card.style.transition = 'none'
  }

  const onSwipeActionClick = (id) => {
    const n = itemsRef.current.find((x) => x.id === id)
    if (n && n.unread) markRead(id)
  }

  /* ── Pull to refresh → реальный refetch ── */
  const onScrollerPointerDown = (e) => {
    const p = pullRef.current
    const a = activeRef.current
    if (p.loading || (a && a.moved)) return
    const scroller = scrollerRef.current
    if (scroller && scroller.scrollTop <= 0) {
      p.pStart = { x: e.clientX, y: e.clientY }
      p.pulling = true
    }
  }
  const onScrollerPointerMove = (e) => {
    const p = pullRef.current
    if (!p.pulling || p.loading || !p.pStart) return
    const scroller = scrollerRef.current
    const listEl = listRef.current
    const ptr = ptrRef.current
    if (!scroller || !listEl || !ptr) return
    const dy = e.clientY - p.pStart.y
    const dx = e.clientX - p.pStart.x
    if (dy <= 0 || Math.abs(dx) > Math.abs(dy)) return
    if (scroller.scrollTop > 0) { p.pulling = false; return }
    const pull = Math.min(64, dy * 0.5)
    listEl.style.transition = 'none'
    listEl.style.transform = 'translateY(' + pull + 'px)'
    ptr.style.opacity = Math.min(1, pull / 46)
    const svg = ptr.querySelector('svg')
    if (svg) svg.style.transform = 'rotate(' + pull * 5 + 'deg)'
    p.pull = pull
  }
  const endPull = () => {
    const p = pullRef.current
    if (!p.pulling) return
    p.pulling = false
    const pull = p.pull || 0
    p.pull = 0
    const listEl = listRef.current
    const ptr = ptrRef.current
    if (!listEl || !ptr) return
    listEl.style.transition = 'transform 0.3s cubic-bezier(0.32,0.72,0.2,1)'
    const settle = () => {
      listEl.style.transform = 'translateY(0)'
      ptr.classList.remove('spin')
      ptr.style.opacity = 0
      p.loading = false
    }
    if (pull >= 44) {
      p.loading = true
      listEl.style.transform = 'translateY(44px)'
      ptr.classList.add('spin')
      ptr.style.opacity = 1
      const svg = ptr.querySelector('svg')
      if (svg) svg.style.transform = ''
      query.refetch().finally(() => {
        setOptimisticRead(new Set())
        setAllRead(false)
        settle()
        toast('Обновлено')
      })
    } else {
      listEl.style.transform = 'translateY(0)'
      ptr.style.opacity = 0
    }
  }

  /* ── Однократная подсказка-наджворд по свайпу ── */
  const hasItems = items.length > 0
  useEffect(() => {
    if (!hasItems) return
    if (sessionStorage.getItem('notif_swipe_hint')) return
    sessionStorage.setItem('notif_swipe_hint', '1')
    const t = setTimeout(() => {
      const first = listRef.current?.querySelector('.swipe')
      if (!first) return
      const card = first.querySelector('.swipe-card')
      first.classList.add('armed')
      card.style.transition = 'transform 0.4s cubic-bezier(0.32,0.72,0.2,1)'
      card.style.transform = 'translateX(-46px)'
      setTimeout(() => {
        card.style.transform = 'translateX(0)'
        setTimeout(() => first.classList.remove('armed'), 360)
      }, 620)
    }, 700)
    return () => clearTimeout(t)
  }, [hasItems])

  /* ── Рендер карточки ── */
  const renderCard = (n) => {
    const meta = KIND_META[n.kind] || { icon: 'info', tone: 'var(--text-3)' }
    return (
      <div className="swipe" data-id={n.id} key={n.id}>
        <div className="swipe-action" onClick={() => onSwipeActionClick(n.id)}>
          <Ico name="check" size={17} color="var(--on-accent)" sw={2.2} />
          Прочитать
        </div>
        <div
          className={'swipe-card press' + (n.unread ? ' unread' : '')}
          data-id={n.id}
          role="button"
          tabIndex={0}
          onPointerDown={(e) => onCardPointerDown(e, n.id)}
        >
          <div className="n-row">
            <div className="n-ic" style={{ background: soft(meta.tone, 16) }}>
              <Ico name={meta.icon} size={17} color={meta.tone} sw={1.9} />
            </div>
            <div className="n-main">
              <div className="n-top">
                <span className="n-title">{n.title}</span>
                {n.at && <span className="n-time t-num">{n.at}</span>}
                {n.unread && <span className="n-dot" aria-label="непрочитано" />}
              </div>
              <div className="n-body">{n.body}</div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!NOTIFICATIONS_FEATURE_FLAGS.notificationsInbox) {
    return null
  }

  const data = filter === 'unread' ? items.filter((n) => n.unread) : items
  const sheetItem = items.find((n) => n.id === sheetItemId)
  const isLoading = query.isLoading
  const isError = query.isError && !query.isFetching

  return (
    <div className="notif-screen">
      <style>{CSS}</style>

      {/* Header */}
      <div className="nav">
        <button className="icon-btn press" onClick={onClose} aria-label="Назад">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--text)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <div className="nav-title t-h3">Уведомления</div>
        <div className="nav-right">
          <button className="nav-action press" disabled={unread === 0} onClick={markAll}>
            Прочитать
          </button>
        </div>
      </div>

      {/* Filter */}
      <div style={{ padding: '6px 16px 12px' }}>
        <div className="seg" style={{ width: '100%' }}>
          <button
            className={'seg-item' + (filter === 'all' ? ' active' : '')}
            style={{ flex: 1 }}
            onClick={() => setFilter('all')}
          >
            Все · {items.length}
          </button>
          <button
            className={'seg-item' + (filter === 'unread' ? ' active' : '')}
            style={{ flex: 1 }}
            onClick={() => setFilter('unread')}
          >
            Новые{unread > 0 ? ' · ' + unread : ''}
          </button>
        </div>
      </div>

      {/* List */}
      <div
        className="scroller"
        ref={scrollerRef}
        onPointerDown={onScrollerPointerDown}
        onPointerMove={onScrollerPointerMove}
        onPointerUp={endPull}
        onPointerCancel={endPull}
        onPointerLeave={endPull}
      >
        <div className="ptr" ref={ptrRef}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="M21 12a9 9 0 1 1-6.2-8.5" />
            <path d="M21 3v6h-6" />
          </svg>
        </div>
        <div className="list" ref={listRef}>
          {isLoading ? (
            <div style={{ paddingTop: 8 }} aria-label="Загрузка уведомлений…">
              <div className="sk-card" />
              <div className="sk-card" />
              <div className="sk-card" />
            </div>
          ) : isError ? (
            <div className="card empty fade-up" style={{ padding: 0, marginTop: 8 }}>
              <div className="empty" style={{ margin: 0 }}>
                <div className="empty-ic" style={{ background: 'var(--danger-soft)' }}>
                  <Ico name="alert" size={26} color="var(--danger)" sw={1.8} />
                </div>
                <div className="t-h3" style={{ fontSize: 16 }}>Не удалось загрузить</div>
                <div className="t-small" style={{ maxWidth: 230 }}>
                  Потяните вниз, чтобы повторить.
                </div>
              </div>
            </div>
          ) : data.length === 0 ? (
            <div className="card empty fade-up" style={{ padding: 0, marginTop: 8 }}>
              <div className="empty" style={{ margin: 0 }}>
                <div className="empty-ic">
                  <Ico name="sparkle" size={26} color="var(--accent-deep)" sw={1.8} />
                </div>
                <div className="t-h3" style={{ fontSize: 16 }}>Всё прочитано</div>
                <div className="t-small" style={{ maxWidth: 230 }}>
                  Когда появятся новые уведомления — увидишь их тут.
                </div>
              </div>
            </div>
          ) : (
            <>
              {GROUPS.map((g) => {
                const inGroup = data.filter((n) => n.group === g.key)
                if (!inGroup.length) return null
                const gu = inGroup.filter((n) => n.unread).length
                return (
                  <Fragment key={g.key}>
                    <div className="group-head fade-up">
                      <span className="t-mini">{g.label}</span>
                      <span className="t-mini gh-count">
                        · {inGroup.length}{gu ? ' · ' + gu + ' нов.' : ''}
                      </span>
                    </div>
                    {inGroup.map(renderCard)}
                  </Fragment>
                )
              })}
              <div className="t-mini" style={{ textAlign: 'center', padding: '16px 0 0', color: 'var(--text-3)' }}>
                Конец списка
              </div>
            </>
          )}
        </div>
      </div>

      {/* Long-press action sheet (mark read only — no delete/unread API) */}
      <div className={'sheet-backdrop' + (backShow ? ' show' : '')} onClick={closeSheet} />
      <div className={'sheet' + (sheetShow ? ' show' : '')}>
        {sheetItem && (
          <>
            <div className="sheet-title">
              <div className="t-mini">Уведомление</div>
              <div className="t-h3" style={{ fontSize: 15, marginTop: 3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {sheetItem.title}
              </div>
            </div>
            {sheetItem.unread && (
              <button
                className="sheet-btn"
                onClick={() => { closeSheet(); markRead(sheetItem.id) }}
              >
                <Ico name="check" size={19} color="var(--text-2)" sw={2} />
                Отметить прочитанным
              </button>
            )}
            <button className="sheet-btn sheet-cancel" onClick={closeSheet}>
              Отмена
            </button>
          </>
        )}
      </div>

      <div className={'toast' + (toastShow ? ' show' : '')}>{toastMsg}</div>
    </div>
  )
}
