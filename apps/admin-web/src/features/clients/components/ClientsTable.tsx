import { useReactTable, getCoreRowModel, type ColumnDef } from '@tanstack/react-table'
import { useNavigate } from '@tanstack/react-router'
import { Pencil, Trash2 } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { ru } from 'date-fns/locale'
import {
  DataGrid,
  DataGridContainer,
  DataGridPagination,
  DataGridTable,
} from '@/shared/ui/data-grid'
import { Button } from '@/shared/ui/button'
import { RoleGate } from '@/shared/session/RoleGate'
import { t } from '@/shared/i18n'
import { ClientsTableSkeleton } from './ClientsTableSkeleton'
import { Route as ClientsRoute } from '@/routes/_protected/clients'
import type { Client, Pagination as PaginationT } from '@/entities/client'
import type { UseQueryResult } from '@tanstack/react-query'

interface Props {
  query: UseQueryResult<PaginationT<Client>>
  search: { q?: string; page: number; pageSize: number }
  onEdit: (c: Client) => void
  onDelete: (c: Client) => void
  onRetry: () => void
  onCreateFromEmpty: () => void
}

export function ClientsTable({ query, search, onEdit, onDelete, onRetry, onCreateFromEmpty }: Props) {
  const navigate = useNavigate({ from: ClientsRoute.fullPath })
  const data = query.data

  // Always call useReactTable unconditionally (React Hooks rules)
  const editLabel = t('clients.actions.edit')
  const deleteLabel = t('clients.actions.delete')
  const columns: ColumnDef<Client>[] = [
    { accessorKey: 'fullName', header: t('clients.columns.fullName') },
    { accessorKey: 'phone', header: t('clients.columns.phone') },
    {
      accessorKey: 'email',
      header: t('clients.columns.email'),
      cell: ({ row }) => (
        <span className="text-muted-foreground max-w-[16ch] truncate">
          {row.original.email ?? '—'}
        </span>
      ),
    },
    {
      accessorKey: 'createdAt',
      header: t('clients.columns.createdAt'),
      cell: ({ row }) => format(parseISO(row.original.createdAt), 'dd.MM.yyyy', { locale: ru }),
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const client = row.original
        return (
          <div className="flex items-center justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9"
              aria-label={editLabel}
              title={editLabel}
              onClick={(e) => { e.stopPropagation(); onEdit(client) }}
            >
              <Pencil className="size-4" />
            </Button>
            <RoleGate action="delete" resource="clients">
              <Button
                variant="ghost"
                size="icon"
                className="text-destructive h-9 w-9"
                aria-label={deleteLabel}
                title={deleteLabel}
                onClick={(e) => { e.stopPropagation(); onDelete(client) }}
              >
                <Trash2 className="size-4" />
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

  if (query.isError) {
    return (
      <div className="space-y-3 rounded-md border p-6 text-center">
        <h2 className="text-lg font-semibold">{t('clients.errorState.heading')}</h2>
        <p className="text-muted-foreground text-sm">{t('clients.errorState.body')}</p>
        <Button onClick={onRetry}>{t('clients.errorState.retry')}</Button>
      </div>
    )
  }

  if (!data) {
    // WARNING #9 fix + RESEARCH Open Question #2 RESOLVED: render skeleton rows matching the
    // canonical CLAUDE.md List template (empty/loading/error) and UI-SPEC skeleton-rows reference.
    return <ClientsTableSkeleton />
  }

  if (data.total === 0 && !search.q) {
    return (
      <div className="space-y-3 rounded-md border p-6 text-center">
        <h2 className="text-lg font-semibold">{t('clients.empty.heading')}</h2>
        <p className="text-muted-foreground text-sm">{t('clients.empty.body')}</p>
        <Button onClick={onCreateFromEmpty}>{t('clients.actions.create')}</Button>
      </div>
    )
  }
  if (data.items.length === 0) {
    return (
      <div className="space-y-2 rounded-md border p-6 text-center">
        <h2 className="text-lg font-semibold">{t('clients.noResults.heading')}</h2>
        <p className="text-muted-foreground text-sm">{t('clients.noResults.body')}</p>
      </div>
    )
  }

  // D-22-5: row click navigates to the client detail page.
  // DataGrid applies cursor-pointer + hover:bg-muted/40 automatically when onRowClick is set.
  const handleRowClick = (client: Client) => {
    void navigate({ to: '/clients/$clientId', params: { clientId: client.id } })
  }

  return (
    <DataGrid
      table={table}
      recordCount={data.total}
      tableLayout={{ headerSticky: true }}
      onRowClick={handleRowClick}
    >
      <DataGridContainer>
        <DataGridTable />
      </DataGridContainer>
      <DataGridPagination sizes={[20, 50, 100]} />
    </DataGrid>
  )
}
