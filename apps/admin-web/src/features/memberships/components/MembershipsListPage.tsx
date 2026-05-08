import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useReactTable, getCoreRowModel, type ColumnDef } from '@tanstack/react-table'
import { Route as MembershipsRoute } from '@/routes/_protected/memberships'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import {
  DataGrid,
  DataGridContainer,
  DataGridTable,
  DataGridPagination,
} from '@/shared/ui/data-grid'
import { RoleGate } from '@/shared/session/RoleGate'
import { Skeleton } from '@/shared/ui/skeleton'
import { t } from '@/shared/i18n'
import { formatDate } from '@/shared/i18n/date'
import { formatMoney } from '@/shared/lib/money'
import { useMembershipsList } from '../api/hooks'
import { CancelMembershipDialog } from './CancelMembershipDialog'
import type { Membership, MembershipId } from '@/entities/membership'

function StatusBadge({ status }: { status: Membership['status'] }) {
  if (status === 'active') return <Badge variant="default">{t('memberships.status.active')}</Badge>
  if (status === 'expired')
    return <Badge variant="secondary">{t('memberships.status.expired')}</Badge>
  return <Badge variant="outline">{t('memberships.status.cancelled')}</Badge>
}

export function MembershipsListPage() {
  const search = MembershipsRoute.useSearch()
  const navigate = useNavigate({ from: MembershipsRoute.fullPath })
  const [cancelId, setCancelId] = useState<MembershipId | null>(null)

  const query = useMembershipsList({
    page: search.page,
    pageSize: search.pageSize,
    expiring: search.expiring,
  })

  const data = query.data

  const columns: ColumnDef<Membership>[] = [
    {
      accessorKey: 'clientId',
      header: t('memberships.columns.client'),
      cell: ({ row }) => (
        <span className="text-muted-foreground font-mono text-xs">
          {row.original.clientId.slice(0, 8)}…
        </span>
      ),
    },
    { accessorKey: 'planNameSnapshot', header: t('memberships.columns.plan') },
    {
      id: 'period',
      header: t('memberships.columns.period'),
      cell: ({ row }) => {
        const m = row.original
        return (
          <span className="text-muted-foreground text-sm">
            {formatDate(m.startDate)}–{formatDate(m.endDate)}
          </span>
        )
      },
    },
    {
      accessorKey: 'priceKopecksSnapshot',
      header: t('memberships.columns.price'),
      cell: ({ row }) => formatMoney(row.original.priceKopecksSnapshot),
    },
    {
      id: 'status',
      header: t('memberships.columns.status'),
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const m = row.original
        return (
          <div className="flex justify-end">
            <RoleGate action="cancel" resource="memberships">
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive"
                onClick={() => setCancelId(m.id)}
                disabled={m.status !== 'active'}
              >
                {t('memberships.actions.cancel')}
              </Button>
            </RoleGate>
          </div>
        )
      },
    },
  ]

  const table = useReactTable({
    data: data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: data ? Math.ceil(data.total / data.pageSize) : 0,
    state: {
      pagination: {
        pageIndex: data ? data.page - 1 : 0,
        pageSize: data?.pageSize ?? search.pageSize,
      },
    },
    onPaginationChange: (updater) => {
      if (!data) return
      const next =
        typeof updater === 'function'
          ? updater({ pageIndex: data.page - 1, pageSize: data.pageSize })
          : updater
      void navigate({
        search: (prev) => ({
          ...prev,
          page: next.pageIndex + 1,
          pageSize: next.pageSize,
        }),
      })
    },
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t('memberships.heading')}</h1>
        <Button
          variant={search.expiring ? 'secondary' : 'outline'}
          size="sm"
          onClick={() =>
            void navigate({
              search: (prev) => ({ ...prev, expiring: !prev.expiring, page: 1 }),
            })
          }
        >
          {t('memberships.filter.expiring')}
        </Button>
      </div>

      {query.isError && (
        <div className="space-y-3 rounded-md border p-6 text-center">
          <h2 className="text-lg font-semibold">{t('memberships.error.heading')}</h2>
          <p className="text-muted-foreground text-sm">{t('memberships.error.body')}</p>
          <Button onClick={() => void query.refetch()}>{t('common.retryLoad')}</Button>
        </div>
      )}

      {query.isLoading && (
        <div className="space-y-3 rounded-md border p-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex gap-4">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </div>
      )}

      {query.isSuccess && data && data.total === 0 && (
        <div className="space-y-3 rounded-md border p-6 text-center">
          {search.expiring ? (
            <p className="text-muted-foreground text-sm">
              {t('memberships.emptyExpiring.heading')}
            </p>
          ) : (
            <>
              <h2 className="text-lg font-semibold">{t('memberships.empty.heading')}</h2>
              <p className="text-muted-foreground text-sm">{t('memberships.empty.body')}</p>
            </>
          )}
        </div>
      )}

      {query.isSuccess && data && data.total > 0 && (
        <DataGrid table={table} recordCount={data.total} tableLayout={{ headerSticky: true }}>
          <DataGridContainer>
            <DataGridTable />
          </DataGridContainer>
          {/* BLK-06: pagination is meaningless while expiring=true — both http
              and mock impls return a single unpaginated page in that branch
              because the backend has no ?expiring=true filter yet. */}
          {!search.expiring && <DataGridPagination sizes={[20, 50, 100]} />}
        </DataGrid>
      )}

      {cancelId && (
        <CancelMembershipDialog
          open={!!cancelId}
          onClose={() => setCancelId(null)}
          membershipId={cancelId}
        />
      )}
    </div>
  )
}
