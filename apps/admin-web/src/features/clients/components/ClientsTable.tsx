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
  const columns: ColumnDef<Client>[] = [
    { accessorKey: 'fullName', header: 'ФИО' },
    { accessorKey: 'phone', header: 'Телефон' },
    {
      accessorKey: 'email',
      header: 'Email',
      cell: ({ row }) => (
        <span className="text-muted-foreground max-w-[16ch] truncate">
          {row.original.email ?? '—'}
        </span>
      ),
    },
    {
      accessorKey: 'createdAt',
      header: 'Дата регистрации',
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
              aria-label="Редактировать клиента"
              title="Редактировать клиента"
              onClick={(e) => { e.stopPropagation(); onEdit(client) }}
            >
              <Pencil className="size-4" />
            </Button>
            <RoleGate action="delete" resource="clients">
              <Button
                variant="ghost"
                size="icon"
                className="text-destructive h-9 w-9"
                aria-label="Удалить клиента"
                title="Удалить клиента"
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
        <h2 className="text-lg font-semibold">Не удалось загрузить клиентов</h2>
        <p className="text-muted-foreground text-sm">Проверьте соединение или обновите страницу.</p>
        <Button onClick={onRetry}>Повторить загрузку</Button>
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
        <h2 className="text-lg font-semibold">Клиентов пока нет</h2>
        <p className="text-muted-foreground text-sm">
          Добавьте первого клиента, нажав «Новый клиент».
        </p>
        <Button onClick={onCreateFromEmpty}>Новый клиент</Button>
      </div>
    )
  }
  if (data.items.length === 0) {
    return (
      <div className="space-y-2 rounded-md border p-6 text-center">
        <h2 className="text-lg font-semibold">Ничего не найдено</h2>
        <p className="text-muted-foreground text-sm">
          Попробуйте изменить запрос или очистить фильтры.
        </p>
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
