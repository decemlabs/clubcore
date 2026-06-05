/**
 * LoyaltySheet (Phase 82 LOYL-01 / LOYL-02)
 *
 * Exports:
 *   LoyaltyBalanceCard — compact card for ProfileScreen (behind clubBonuses flag)
 *   BonusHistorySheet  — full-screen sub-sheet with paginated bonus history
 *
 * Design contract: 82-UI-SPEC.md
 * API contract: GET /api/v1/client/loyalty/balance + /history (Plan 02)
 * Money: always via formatMoney — never divide kopecks manually.
 * Signs: derived from signed amountKopecks (+accrual / −redemption U+2212).
 */
import React from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Icon } from '@/components/Icon.jsx'
import { StatusBar } from '@/components/StatusBar.jsx'
import { PullToRefresh } from '@/components/PullToRefresh.jsx'
import { SubSheetHeader } from '@/screens/sheets/ProfileExtraSheets.jsx'
import { useClientLoyaltyBalance, useClientLoyaltyHistory } from '@/data'
import { clientPortalKeys } from '@/lib/clientQueries'
import { formatMoney } from '@/utils/format.js'

// ─── Date formatter — ISO datetime → Russian long date (no date-fns, D-82-01) ─
// Uses Intl.DateTimeFormat with ru locale, timezone Europe/Moscow.
// Accepts full ISO datetime strings (e.g. "2026-06-01T10:00:00Z").
function formatBonusDate(isoString) {
  if (!isoString) return ''
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone: 'Europe/Moscow',
    }).format(new Date(isoString))
  } catch {
    return isoString
  }
}

// ─── Type label map ───────────────────────────────────────────────────────────
const ENTRY_TYPE_LABELS = {
  welcome: 'Приветственный бонус',
  owner_grant: 'Бонус от зала',
  redemption: 'Списание за оплату',
}

// ─── BonusRow — single ledger entry ──────────────────────────────────────────
function BonusRow({ item }) {
  const isAccrual = item.amountKopecks > 0
  return (
    <div style={{ padding: '12px 16px', display: 'flex', gap: 12, alignItems: 'center' }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
        background: isAccrual ? 'var(--accent-soft)' : 'var(--danger-soft)',
        color: isAccrual ? 'var(--accent-deep)' : 'var(--danger)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon name={isAccrual ? 'gift' : 'arrowUp'} size={16} color="currentColor" />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-small" style={{ color: 'var(--text)', fontWeight: 700 }}>
          {ENTRY_TYPE_LABELS[item.type] ?? item.type}
        </div>
        <div className="t-small" style={{ marginTop: 1, color: 'var(--text-2)' }}>
          {formatBonusDate(item.createdAt)}
        </div>
      </div>
      <div style={{ fontSize: 13, fontWeight: 700, color: isAccrual ? 'var(--accent-deep)' : 'var(--danger)' }}>
        {isAccrual ? '+' : '−'}{formatMoney(Math.abs(item.amountKopecks))}
      </div>
    </div>
  )
}

// ─── LoyaltyBalanceCard ───────────────────────────────────────────────────────
// Renders on the Profile tab behind the clubBonuses feature flag.
// Hides silently on error (matches CardSheet pattern).
export function LoyaltyBalanceCard({ onOpen }) {
  const { data, isLoading, isError } = useClientLoyaltyBalance()

  if (isError) return null

  return (
    <div
      className="card press"
      onClick={onOpen}
      style={{ padding: 16, cursor: 'pointer' }}
      aria-label="Бонусный счёт"
    >
      {/* Top row: icon + label + chevron */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8, flexShrink: 0,
          background: 'var(--accent-soft)', color: 'var(--accent-deep)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name="gift" size={16} color="currentColor" />
        </div>
        <span className="t-body" style={{ fontWeight: 700, flex: 1 }}>Бонусный счёт</span>
        <Icon name="chevronRight" size={18} color="var(--text-3)" />
      </div>

      {/* Balance row */}
      <div style={{ marginTop: 12 }}>
        <div className="t-mini" style={{
          color: 'var(--text-3)', fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase',
        }}>
          Доступно бонусов
        </div>
        {isLoading ? (
          <div className="sk sk-line" style={{ width: '40%', marginTop: 6 }} aria-label="Загрузка бонусов…" />
        ) : (
          <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.6px', color: 'var(--text)', marginTop: 4 }}>
            {formatMoney(data?.balanceKopecks ?? 0)}
          </div>
        )}
      </div>

      {/* Tap hint */}
      {!isLoading && (
        <div className="t-small" style={{ color: 'var(--text-2)', marginTop: 6 }}>
          История начислений
        </div>
      )}
    </div>
  )
}

// ─── BonusHistorySheet ────────────────────────────────────────────────────────
// Full-screen sub-sheet mirroring VisitHistorySheet (z-index 220, sheet-up anim).
export function BonusHistorySheet({ onClose }) {
  const queryClient = useQueryClient()
  const [page, setPage] = React.useState(1)
  const [allItems, setAllItems] = React.useState([])

  const balanceQuery = useClientLoyaltyBalance()
  const historyQuery = useClientLoyaltyHistory(page)

  const { data: balanceData } = balanceQuery
  const { data: historyData, isFetching: isFetchingHistory, isError: isHistoryError } = historyQuery

  // Accumulate items across pages
  React.useEffect(() => {
    if (historyData?.items) {
      if (page === 1) {
        setAllItems(historyData.items)
      } else {
        setAllItems(prev => {
          const existingIds = new Set(prev.map(i => i.id))
          const newItems = historyData.items.filter(i => !existingIds.has(i.id))
          return [...prev, ...newItems]
        })
      }
    }
  }, [historyData, page])

  const total = historyData?.total ?? 0
  const hasMore = allItems.length < total

  const handleRefresh = async () => {
    // Reset to page 1 and invalidate the loyalty-history key family so the
    // refresh refetches page 1 regardless of which page the user was on —
    // calling historyQuery.refetch() would fire on the stale page>1 key (WR-02).
    setPage(1)
    setAllItems([])
    await Promise.all([
      balanceQuery.refetch(),
      queryClient.invalidateQueries({ queryKey: [...clientPortalKeys.all, 'loyalty-history'] }),
    ])
  }

  const handleLoadMore = () => {
    setPage(p => p + 1)
  }

  // Group items by month for display (Intl-based, no date-fns)
  const groups = React.useMemo(() => {
    if (allItems.length === 0) return []
    const map = new Map()
    allItems.forEach(item => {
      let monthKey = ''
      try {
        monthKey = new Intl.DateTimeFormat('ru-RU', {
          month: 'long',
          year: 'numeric',
          timeZone: 'Europe/Moscow',
        }).format(new Date(item.createdAt))
      } catch {
        monthKey = item.createdAt.slice(0, 7)
      }
      if (!map.has(monthKey)) map.set(monthKey, [])
      map.get(monthKey).push(item)
    })
    return Array.from(map.entries()).map(([label, items]) => ({ label, items }))
  }, [allItems])

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />
      <SubSheetHeader title="История бонусов" onClose={onClose} />

      <PullToRefresh scrollPaddingTop={0} onRefresh={handleRefresh}>
        {/* Current balance summary card */}
        <div style={{ padding: '8px 16px 14px' }}>
          <div className="card" style={{ padding: 16 }}>
            <div className="t-mini" style={{
              color: 'var(--text-3)', fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase',
            }}>
              Текущий баланс
            </div>
            {balanceQuery.isLoading ? (
              <div className="sk sk-line" style={{ width: '35%', marginTop: 8 }} />
            ) : (
              <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.6px', color: 'var(--text)', marginTop: 4 }}>
                {formatMoney(balanceData?.balanceKopecks ?? 0)}
              </div>
            )}
          </div>
        </div>

        {/* Section label */}
        <div className="t-mini" style={{
          color: 'var(--text-3)', padding: '0 20px 8px',
          fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase',
        }}>
          Операции
        </div>

        {/* Loading skeleton */}
        {isFetchingHistory && allItems.length === 0 && (
          <div style={{ padding: '0 16px 14px' }}>
            <div className="card" style={{ padding: 16 }}>
              {[80, 60, 70, 50].map((w, i) => (
                <div key={i} className="sk sk-line" style={{ width: `${w}%`, marginBottom: i < 3 ? 12 : 0 }} />
              ))}
            </div>
          </div>
        )}

        {/* History error */}
        {isHistoryError && allItems.length === 0 && (
          <div style={{ padding: '16px 16px', textAlign: 'center' }}>
            <div className="t-small" style={{ color: 'var(--text-2)' }}>
              Не удалось загрузить историю. Потяни вниз, чтобы повторить.
            </div>
          </div>
        )}

        {/* Empty state */}
        {!isFetchingHistory && !isHistoryError && allItems.length === 0 && (
          <div style={{ padding: '40px 24px', textAlign: 'center' }}>
            <div style={{
              width: 60, height: 60, borderRadius: 999, margin: '0 auto 16px',
              background: 'var(--surface-2)', color: 'var(--text-3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon name="gift" size={28} color="currentColor" />
            </div>
            <div className="t-h3" style={{ fontSize: 16 }}>Бонусов пока нет</div>
            <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)' }}>
              После первой активности здесь появится история начислений.
            </div>
          </div>
        )}

        {/* Grouped history list */}
        {groups.map(g => (
          <div key={g.label} style={{ padding: '0 16px 14px' }}>
            <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>
              {g.label}
            </div>
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {g.items.map((item, i) => (
                <React.Fragment key={item.id}>
                  {i > 0 && (
                    <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 44 }} />
                  )}
                  <BonusRow item={item} />
                </React.Fragment>
              ))}
            </div>
          </div>
        ))}

        {/* Load more */}
        {hasMore && (
          <div style={{ padding: '0 16px 24px', textAlign: 'center' }}>
            <button
              onClick={handleLoadMore}
              className="btn btn-ghost btn-sm press"
              disabled={isFetchingHistory}
            >
              {isFetchingHistory
                ? <span className="ptr-spin" style={{ width: 18, height: 18 }} />
                : 'Загрузить ещё'}
            </button>
          </div>
        )}
      </PullToRefresh>
    </div>
  )
}
