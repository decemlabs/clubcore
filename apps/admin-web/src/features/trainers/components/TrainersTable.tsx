import { useReactTable, getCoreRowModel, type ColumnDef } from '@tanstack/react-table'
import { Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import {
  DataGrid,
  DataGridContainer,
  DataGridTable,
  DataGridPagination,
} from '@/shared/ui/data-grid'
import { t } from '@/shared/i18n'
import { TrainerStatusBadge } from './TrainerStatusBadge'
import type { Trainer } from '@/entities/trainer'

interface Props {
  data: { items: Trainer[]; total: number; page: number; pageSize: number }
  onPaginationChange: (page: number, pageSize: number) => void
  onEdit: (trainer: Trainer) => void
  onDelete: (trainer: Trainer) => void
}

export function TrainersTable({ data, onPaginationChange, onEdit, onDelete }: Props) {
  const columns: ColumnDef<Trainer>[] = [
    {
      accessorKey: 'fullName',
      header: t('trainers.columns.fullName'),
    },
    {
      accessorKey: 'phone',
      header: t('trainers.columns.phone'),
      cell: ({ row }) => row.original.phone ?? '—',
    },
    {
      id: 'isActive',
      header: t('trainers.columns.status'),
      cell: ({ row }) => <TrainerStatusBadge isActive={row.original.isActive} />,
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const trainer = row.original
        return (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="sm"
              aria-label={t('trainers.actions.edit')}
              onClick={() => onEdit(trainer)}
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive"
              aria-label={t('trainers.actions.delete')}
              onClick={() => onDelete(trainer)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        )
      },
    },
  ]

  const table = useReactTable({
    data: data.items,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: Math.ceil(data.total / data.pageSize),
    state: {
      pagination: {
        pageIndex: data.page - 1,
        pageSize: data.pageSize,
      },
    },
    onPaginationChange: (updater) => {
      const next =
        typeof updater === 'function'
          ? updater({ pageIndex: data.page - 1, pageSize: data.pageSize })
          : updater
      onPaginationChange(next.pageIndex + 1, next.pageSize)
    },
  })

  return (
    <DataGrid table={table} recordCount={data.total} tableLayout={{ headerSticky: true }}>
      <DataGridContainer>
        <DataGridTable />
      </DataGridContainer>
      <DataGridPagination sizes={[20, 50, 100]} />
    </DataGrid>
  )
}
