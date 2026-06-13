/**
 * Activity tab — real client visits via useClientVisits (Phase 101-04).
 *
 * Per-tab inline error/empty states (UI-SPEC §Surface 1):
 *   - loading: Skeleton rows
 *   - error: inline <PageError onRetry/> (NOT full-page)
 *   - empty: inline EmptyState (no icon tile) «Нет активности» / «Визиты клиента появятся здесь.»
 *   - data: real VisitData rows (checkedInAt, gymDate, channel)
 *
 * T-101-12-IDOR: 403/404 on useClientVisits collapses to per-tab inline error,
 * no cross-client render possible.
 * T-101-14-PII-ERR: error rendered via PageError curated copy, no raw internals.
 */
import { useClientVisits } from '@/features/visits/api'
import { formatDateRu, formatTime } from '@/lib/format'
import { PageError } from '@/components/feedback/PageState'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import { Card } from './shared'

function VisitRow({ item }: { item: { id: string; checkedInAt: string; gymDate: string; channel: string; checkedInBy?: string | null } }) {
  const channelLabel = (ch: string) => {
    if (ch === 'qr') return 'QR-код'
    if (ch === 'manual') return 'Вручную'
    if (ch === 'app') return 'Приложение'
    return ch
  }
  return (
    <div className="grid grid-cols-[50px_1fr_auto] items-center gap-3 border-t-[0.5px] border-border px-4 py-3 first:border-t-0 sm:px-5">
      <div className="text-xs font-semibold tabular-nums tracking-[-0.1px] text-fg-muted">
        {formatTime(item.checkedInAt)}
      </div>
      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold tracking-[-0.1px]">
          {formatDateRu(item.gymDate, 'd MMMM yyyy')}
        </div>
        <div className="mt-0.5 truncate text-[11.5px] text-fg-subtle">
          {channelLabel(item.channel)}
          {item.checkedInBy ? ` · ${item.checkedInBy}` : null}
        </div>
      </div>
      <div className="text-[11.5px] text-fg-subtle">
        {formatDateRu(item.checkedInAt, 'd MMM')}
      </div>
    </div>
  )
}

export function ActivityTab({ clientId }: { clientId: string }) {
  const { data, isPending, isError, refetch } = useClientVisits(clientId)

  if (isPending) {
    return (
      <Card className="px-4 py-4 sm:px-5">
        <Skeleton className="mb-2 h-10 w-full" />
        <Skeleton className="mb-2 h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </Card>
    )
  }

  if (isError) {
    return (
      <Card>
        <PageError onRetry={() => void refetch()} />
      </Card>
    )
  }

  const items = data?.items ?? []

  if (items.length === 0) {
    return (
      <Card>
        <EmptyState
          className="py-12"
          title="Нет активности"
          message="Визиты клиента появятся здесь."
        />
      </Card>
    )
  }

  return (
    <Card className="pb-2">
      {items.map((item) => (
        <VisitRow key={item.id} item={item} />
      ))}
    </Card>
  )
}
