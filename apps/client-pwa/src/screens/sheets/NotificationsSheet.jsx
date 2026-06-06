/**
 * NotificationsSheet (Phase 87 INBOX-05)
 *
 * Full-screen sub-sheet with paginated notification inbox.
 * Graduated from D-71-09 placeholder in Phase 87 — wired to real backend.
 *
 * Design contract: 87-UI-SPEC.md
 * API contract:
 *   GET  /api/v1/client/notifications?page=N → { items, total, page, pageSize, unreadCount }
 *   PATCH /api/v1/client/notifications/{id}/read → 200 NotificationItem
 *   PATCH /api/v1/client/notifications/read-all → 204
 */
import React from 'react'
import { Icon } from '@/components/Icon.jsx'
import { StatusBar } from '@/components/StatusBar.jsx'
import { PullToRefresh } from '@/components/PullToRefresh.jsx'
import { SubSheetHeader } from '@/screens/sheets/ProfileExtraSheets.jsx'
import {
  useClientNotifications,
  useMarkNotificationRead,
  useMarkAllNotificationsRead,
} from '@/data'

// ─── Feature flag (INBOX-05 kill-switch anchor — always true in Phase 87) ────
const NOTIFICATIONS_FEATURE_FLAGS = {
  notificationsInbox: true, // INBOX-05 (Phase 87): wired to GET /client/notifications
}

// ─── Relative timestamp — Intl-only (D-82-01, no date-fns) ──────────────────
function formatRelativeTime(isoString) {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 2)   return 'только что'
  if (diffMin < 60)  return `${diffMin} мин. назад`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24)    return `${diffH} ч. назад`
  const diffD = Math.floor(diffH / 24)
  if (diffD === 1)   return 'вчера'
  if (diffD < 7)     return `${diffD} дн. назад`
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric', month: 'short', timeZone: 'Europe/Moscow',
  }).format(new Date(isoString))
}

// ─── Icon/color mapping per notification kind ────────────────────────────────
function getKindMeta(kind) {
  switch (kind) {
    case 'booking_confirmed':
      return { icon: 'calendar', bg: 'var(--accent-soft)', color: 'var(--accent-deep)' }
    case 'booking_cancelled_by_client':
    case 'booking_cancelled_by_owner':
      return { icon: 'close', bg: 'var(--accent-soft)', color: 'var(--accent-deep)' }
    case 'booking_rescheduled':
      return { icon: 'history', bg: 'var(--accent-soft)', color: 'var(--accent-deep)' }
    case 'payment_succeeded':
    case 'autopay_charge_succeeded':
      return { icon: 'card', bg: 'var(--accent-soft)', color: 'var(--accent-deep)' }
    case 'autopay_charge_failed':
      return { icon: 'alertCircle', bg: 'var(--danger-soft)', color: 'var(--danger)' }
    default:
      return { icon: 'bell', bg: 'var(--accent-soft)', color: 'var(--accent-deep)' }
  }
}

// ─── NotificationRow ─────────────────────────────────────────────────────────
function NotificationRow({ item }) {
  const { icon, bg, color } = getKindMeta(item.kind)
  const isUnread = item.readAt === null

  return (
    <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
      {/* Icon container 32×32 */}
      <div style={{
        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
        background: bg, color,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon name={icon} size={16} color="currentColor" />
      </div>

      {/* Content block */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-body" style={{ fontWeight: 700, color: 'var(--text)' }}>
          {item.title}
        </div>
        <div className="t-small" style={{ marginTop: 1, color: 'var(--text-2)' }}>
          {item.body}
        </div>
        <div className="t-small" style={{ marginTop: 2, color: 'var(--text-3)' }}>
          {formatRelativeTime(item.createdAt)}
        </div>
      </div>

      {/* Unread dot — only when readAt === null */}
      {isUnread && (
        <div style={{
          width: 8, height: 8, borderRadius: 999,
          background: 'var(--accent)', flexShrink: 0, alignSelf: 'center',
        }} aria-label="непрочитано" />
      )}
    </div>
  )
}

// ─── Skeleton rows ────────────────────────────────────────────────────────────
function SkeletonRows() {
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      {[0, 1, 2, 3].map(i => (
        <div key={i} style={{ padding: '12px 16px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          <div className="sk sk-circle" style={{ width: 32, height: 32, borderRadius: 8, flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div className="sk sk-line" style={{ width: '60%', marginBottom: 8 }} />
            <div className="sk sk-line" style={{ width: '40%' }} />
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── NotificationsSheet ───────────────────────────────────────────────────────
export function NotificationsSheet({ onClose }) {
  // Feature flag gate
  if (!NOTIFICATIONS_FEATURE_FLAGS.notificationsInbox) {
    return null
  }

  const [page, setPage] = React.useState(1)
  // Local items state with optimistic read-state tracking
  const [allItems, setAllItems] = React.useState([])
  const [optimisticReadIds, setOptimisticReadIds] = React.useState(new Set())
  // Local in-sheet toast (no global Sonner in PWA — mirror ProfileExtraSheets pattern)
  const [toastMsg, setToastMsg] = React.useState(null)
  const toastTimer = React.useRef(null)

  const showToast = (msg) => {
    if (toastTimer.current) clearTimeout(toastTimer.current)
    setToastMsg(msg)
    toastTimer.current = setTimeout(() => setToastMsg(null), 2600)
  }

  const query = useClientNotifications(page)
  const markRead = useMarkNotificationRead()
  const markAllRead = useMarkAllNotificationsRead()

  const { data, isFetching, isError } = query

  // Accumulate items across pages (dedup by id)
  React.useEffect(() => {
    if (data?.items) {
      if (page === 1) {
        setAllItems(data.items)
      } else {
        setAllItems(prev => {
          const existingIds = new Set(prev.map(i => i.id))
          const newItems = data.items.filter(i => !existingIds.has(i.id))
          return [...prev, ...newItems]
        })
      }
    }
  }, [data, page])

  const unreadCount = data?.unreadCount ?? 0
  const total = data?.total ?? 0
  const hasMore = allItems.length < total

  // Mark first-page unread items as read after 800ms (fire-and-forget, optimistic)
  const markedOnOpenRef = React.useRef(false)
  React.useEffect(() => {
    if (markedOnOpenRef.current) return
    if (!data?.items || data.items.length === 0) return

    markedOnOpenRef.current = true
    const unreadItems = data.items.filter(item => item.readAt === null)
    if (unreadItems.length === 0) return

    const timer = setTimeout(() => {
      unreadItems.forEach(item => {
        // Optimistic: add to set
        setOptimisticReadIds(prev => new Set([...prev, item.id]))
        // Fire-and-forget API call
        markRead.mutate(item.id)
      })
    }, 800)

    return () => clearTimeout(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.items])

  // Effective items with optimistic read state applied
  const effectiveItems = allItems.map(item =>
    optimisticReadIds.has(item.id) ? { ...item, readAt: new Date().toISOString() } : item
  )

  const handleRefresh = async () => {
    setPage(1)
    setAllItems([])
    setOptimisticReadIds(new Set())
    markedOnOpenRef.current = false
    await query.refetch()
  }

  const handleLoadMore = () => {
    setPage(p => p + 1)
  }

  const handleMarkAll = () => {
    // Capture pre-mutation state BEFORE any setState calls so the onError closure
    // closes over the correct pre-optimistic values (CR-01 fix).
    const prevItems = allItems
    const prevReadIds = optimisticReadIds

    // Optimistic: mark all rendered items as read locally.
    // Only add IDs of items that were unread before mark-all — already-read items
    // must not inflate optimisticReadIds (CR-01: snapshot was built from effectiveItems
    // which already had optimisticReadIds applied, causing over-counting).
    const now = new Date().toISOString()
    setAllItems(prev => prev.map(item => ({ ...item, readAt: item.readAt ?? now })))
    setOptimisticReadIds(new Set(allItems.filter(i => i.readAt === null).map(i => i.id)))

    markAllRead.mutate(undefined, {
      onError: () => {
        // Rollback: restore pre-optimistic state using values captured before setState.
        setAllItems(prevItems)
        setOptimisticReadIds(prevReadIds)
        showToast('Не удалось отметить прочитанными')
      },
    })
  }

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />

      {/* Header row with mark-all action */}
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ flex: 1 }}>
          <SubSheetHeader title="Уведомления" onClose={onClose} />
        </div>
        {unreadCount > 0 && (
          <button
            className="press"
            onClick={handleMarkAll}
            style={{
              background: 'none', border: 'none', padding: '0 16px 0 0',
              color: 'var(--accent-deep)', cursor: 'pointer',
            }}
          >
            <span className="t-small" style={{ color: 'var(--accent-deep)', fontWeight: 600 }}>
              Всё прочитано
            </span>
          </button>
        )}
      </div>

      <PullToRefresh scrollPaddingTop={0} onRefresh={handleRefresh}>
        {/* Section label */}
        <div className="t-mini" style={{
          color: 'var(--text-3)', padding: '0 16px 8px',
          fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase',
        }}>
          УВЕДОМЛЕНИЯ
        </div>

        {/* Loading skeleton */}
        {isFetching && allItems.length === 0 && (
          <div style={{ padding: '0 16px 14px' }} aria-label="Загрузка уведомлений…">
            <SkeletonRows />
          </div>
        )}

        {/* Error state */}
        {isError && allItems.length === 0 && (
          <div style={{ padding: '16px 16px', textAlign: 'center' }}>
            <div className="t-small" style={{ color: 'var(--text-2)' }}>
              Не удалось загрузить уведомления. Потяните вниз, чтобы повторить.
            </div>
          </div>
        )}

        {/* Empty state */}
        {!isFetching && !isError && allItems.length === 0 && (
          <div style={{ padding: '48px 24px', textAlign: 'center' }}>
            <div style={{
              width: 60, height: 60, borderRadius: 999, margin: '0 auto 16px',
              background: 'var(--surface-2)', color: 'var(--text-3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon name="bell" size={28} color="currentColor" />
            </div>
            <div className="t-h3">Нет уведомлений</div>
            <div className="t-small" style={{ marginTop: 8, color: 'var(--text-2)' }}>
              Здесь будут появляться уведомления о записях, платежах и других событиях.
            </div>
          </div>
        )}

        {/* Notification list */}
        {effectiveItems.length > 0 && (
          <div style={{ padding: '0 16px 14px' }}>
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {effectiveItems.map((item, i) => (
                <React.Fragment key={item.id}>
                  {i > 0 && (
                    <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 60 }} />
                  )}
                  <NotificationRow item={item} />
                </React.Fragment>
              ))}
            </div>
          </div>
        )}

        {/* Load more */}
        {hasMore && (
          <div style={{ padding: '0 16px 24px', textAlign: 'center' }}>
            <button
              onClick={handleLoadMore}
              className="btn btn-ghost btn-sm press"
              disabled={isFetching}
            >
              {isFetching
                ? <span className="ptr-spin" style={{ width: 18, height: 18 }} />
                : 'Загрузить ещё'}
            </button>
          </div>
        )}

        {/* Bottom safe-area padding */}
        <div style={{ height: 32 }} />
      </PullToRefresh>

      {/* In-sheet error toast (local state — no global Sonner in PWA) */}
      {toastMsg && (
        <div style={{
          position: 'absolute', bottom: 24, left: 16, right: 16,
          background: 'var(--danger)', color: '#fff',
          borderRadius: 10, padding: '10px 14px',
          fontSize: 13, fontWeight: 600, textAlign: 'center',
          zIndex: 10, boxShadow: 'var(--sh-2)',
        }}>
          {toastMsg}
        </div>
      )}
    </div>
  )
}
