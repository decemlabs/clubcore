/**
 * Trainings tab — real PT-packages via usePtPackagesByClient (Phase 101-04).
 *
 * Per-tab inline error/empty states (UI-SPEC §Surface 1):
 *   - loading: Skeleton rows
 *   - error: inline <PageError onRetry/> (NOT full-page)
 *   - empty: inline EmptyState (no icon tile) «Нет тренировок» / «Персональные тренировки появятся здесь.»
 *   - data: real PtPackageData rows (planSnapshot.name, sessionsRemaining, status)
 *
 * Phase 107-02 PTPKG-01/02: added lifecycle actions
 *   - «Продать пакет» button in card header (can(role,'create','pt-packages') — both roles)
 *   - Per-row kebab (⋯) menu:
 *       «Вернуть оплату» — both roles (refund not in OWNER_ONLY)
 *       «Отменить пакет» — owner only via can(role,'cancel','pt-packages')
 */
import { useState } from 'react'
import { usePtPackagesByClient } from '@/features/pt-packages/api'
import type { PtPackageData } from '@/features/pt-packages/schemas'
import { useSession } from '@/features/auth/api'
import { can } from '@/shared/session/can'
import { formatKopecks, formatDateRu } from '@/lib/format'
import { PageError } from '@/components/feedback/PageState'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { MoreHorizontal, Plus } from '@/components/icons'
import { cn } from '@/lib/cn'
import { Card, CardHead } from './shared'
import { PtPackageSellModal } from '@/components/modals/PtPackageSellModal'
import {
  PtPackageCancelDialog,
  PtPackageRefundDialog,
} from '@/components/modals/PtPackageActionDialogs'

const STATUS_LABEL: Record<string, string> = {
  active: 'Активный',
  exhausted: 'Исчерпан',
  expired: 'Истёк',
  cancelled: 'Отменён',
}

const STATUS_TONE: Record<string, string> = {
  active: 'bg-primary-soft text-primary-deep dark:text-primary',
  exhausted: 'bg-surface-3 text-fg-muted',
  expired: 'bg-surface-3 text-fg-muted',
  cancelled: 'bg-danger-soft text-danger',
}

const ADD_BTN =
  'inline-flex h-9 items-center gap-1.5 rounded-full border-[0.5px] border-border bg-surface px-3.5 text-[13px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

function PtPackageRow({
  item,
  role,
  onCancel,
  onRefund,
}: {
  item: PtPackageData
  role: string
  onCancel: (item: PtPackageData) => void
  onRefund: (item: PtPackageData) => void
}) {
  const tone = STATUS_TONE[item.status] ?? 'bg-surface-3 text-fg-muted'
  const statusLabel = STATUS_LABEL[item.status] ?? item.status

  return (
    <div className="grid grid-cols-[1fr_auto_auto] items-center gap-3 border-t-[0.5px] border-border px-4 py-3 first:border-t-0 sm:px-5">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <div className="truncate text-[13.5px] font-semibold tracking-[-0.1px]">
            {item.planSnapshot.name}
          </div>
          <span
            className={cn('shrink-0 rounded-full px-[7px] py-px text-[11px] font-semibold', tone)}
          >
            {statusLabel}
          </span>
        </div>
        <div className="mt-0.5 text-[11.5px] tabular-nums text-fg-subtle">
          Занятий: {item.sessionsRemaining} из {item.sessionsTotal}
          {' · '}
          {formatDateRu(item.createdAt, 'd MMM yyyy')}
        </div>
      </div>
      <div className="shrink-0 text-sm font-bold tabular-nums tracking-[-0.2px]">
        {formatKopecks(item.amountKopecks)}
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label="Действия с пакетом"
            className="h-8 w-8 rounded-lg inline-flex items-center justify-center text-fg-subtle hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <MoreHorizontal className="size-[15px]" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[160px]">
          <DropdownMenuItem onSelect={() => onRefund(item)}>Вернуть оплату</DropdownMenuItem>
          {can(role as Parameters<typeof can>[0], 'cancel', 'pt-packages') && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-danger focus:text-danger"
                onSelect={() => onCancel(item)}
              >
                Отменить пакет
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

export function TrainingsTab({ clientId }: { clientId: string }) {
  const { data, isPending, isError, refetch } = usePtPackagesByClient(clientId)
  const session = useSession()
  const role = session.data?.role ?? 'reception'

  const [sellOpen, setSellOpen] = useState(false)
  const [cancelTarget, setCancelTarget] = useState<PtPackageData | null>(null)
  const [refundTarget, setRefundTarget] = useState<PtPackageData | null>(null)

  const sellButton = can(role, 'create', 'pt-packages') ? (
    <button type="button" className={ADD_BTN} onClick={() => setSellOpen(true)}>
      <Plus className="size-[14px]" />
      Продать пакет
    </button>
  ) : null

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

  return (
    <>
      {items.length === 0 ? (
        <Card>
          <CardHead title="Пакеты тренировок" action={sellButton} />
          <EmptyState
            className="py-12"
            title="Нет тренировок"
            message="Персональные тренировки появятся здесь."
          />
        </Card>
      ) : (
        <Card>
          <CardHead title="Пакеты тренировок" sub={`${items.length} пакет(ов)`} action={sellButton} />
          <div className="border-t-[0.5px] border-border">
            {items.map((item) => (
              <PtPackageRow
                key={item.id}
                item={item}
                role={role}
                onCancel={(i) => setCancelTarget(i)}
                onRefund={(i) => setRefundTarget(i)}
              />
            ))}
          </div>
        </Card>
      )}

      <PtPackageSellModal
        open={sellOpen}
        onOpenChange={setSellOpen}
        clientId={clientId}
      />

      {cancelTarget && (
        <PtPackageCancelDialog
          open
          onOpenChange={() => setCancelTarget(null)}
          item={cancelTarget}
        />
      )}

      {refundTarget && (
        <PtPackageRefundDialog
          open
          onOpenChange={() => setRefundTarget(null)}
          item={refundTarget}
        />
      )}
    </>
  )
}
