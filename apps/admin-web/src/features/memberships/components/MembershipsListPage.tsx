import { useMemo, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useQueries } from '@tanstack/react-query'
import { useReactTable, getCoreRowModel, type ColumnDef } from '@tanstack/react-table'
import { Route as MembershipsRoute } from '@/routes/_protected/memberships'
import { services } from '@/shared/api/services'
import type { ClientId } from '@/entities/client'
import { Button } from '@/shared/ui/button'
import { Alert, AlertDescription } from '@/shared/ui/alert'
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
import { StatusBadge } from './StatusBadge'
import type { Membership, MembershipId } from '@/entities/membership'

export function MembershipsListPage() {
  const search = MembershipsRoute.useSearch()
  const navigate = useNavigate({ from: MembershipsRoute.fullPath })
  const [cancelId, setCancelId] = useState<MembershipId | null>(null)

  const query = useMembershipsList({
    page: search.page,
    pageSize: search.pageSize,
    status: search.status,
    expiring: search.expiring,
    within: search.within,
  })

  const data = query.data

  // WR-19: fetch client names for the visible page so the operator can identify
  // membership owners. Backend MembershipResponse has no clientName snapshot;
  // until it does, we issue parallel useQueries against services.clients.get
  // for each unique clientId on this page. Cache key matches features/clients
  // clientsKeys.detail() shape so a future visit to /clients/$id shares cache.
  // services container access (not features/clients import) respects the
  // "features must not import other features" rule.
  const uniqueClientIds = useMemo(() => {
    const ids = new Set<string>()
    for (const m of data?.items ?? []) ids.add(m.clientId)
    return Array.from(ids)
  }, [data?.items])
  const clientQueries = useQueries({
    queries: uniqueClientIds.map((id) => ({
      queryKey: ['clients', 'detail', id] as const,
      queryFn: () => services.clients.get(id as ClientId),
      staleTime: 30_000,
    })),
  })
  const clientNameById = useMemo(() => {
    const map = new Map<string, string>()
    uniqueClientIds.forEach((id, i) => {
      const c = clientQueries[i]?.data
      if (c) map.set(id, c.fullName)
    })
    return map
  }, [uniqueClientIds, clientQueries])

  const columns: ColumnDef<Membership>[] = [
    {
      accessorKey: 'clientId',
      header: t('memberships.columns.client'),
      cell: ({ row }) => {
        const id = row.original.clientId
        const name = clientNameById.get(id)
        if (name) return <span className="text-sm">{name}</span>
        return (
          <span className="text-muted-foreground font-mono text-xs">{id.slice(0, 8)}…</span>
        )
      },
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
        <div className="flex items-center gap-2">
          <Button
            variant={search.status === 'frozen' ? 'secondary' : 'outline'}
            size="sm"
            onClick={() =>
              void navigate({
                search: (prev) => ({
                  ...prev,
                  status: prev.status === 'frozen' ? undefined : 'frozen',
                  expiring: false,
                  page: 1,
                }),
              })
            }
          >
            {t('memberships.status.frozen')}
          </Button>
          <Button
            variant={search.expiring ? 'secondary' : 'outline'}
            size="sm"
            onClick={() =>
              void navigate({
                search: (prev) => ({
                  ...prev,
                  expiring: !prev.expiring,
                  status: undefined,
                  page: 1,
                }),
              })
            }
          >
            {t('memberships.filter.expiring')}
          </Button>
        </div>
      </div>

      {/* WR-16: explicit notice while expiring=true so the operator
          understands why pagination is hidden and what subset is shown. */}
      {search.expiring && (
        <Alert>
          <AlertDescription>
            {t('memberships.filterNotice.expiringSubsetOfPage')}
          </AlertDescription>
        </Alert>
      )}

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
