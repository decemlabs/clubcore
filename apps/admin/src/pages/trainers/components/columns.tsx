/**
 * columns.tsx — Phase 102-02 TRN-01.
 *
 * DataTable columns wired to real TrainerData fields.
 * Edit/delete affordances gated via props from TrainersPage.
 */
import { cn } from '@/lib/cn'
import { Initials } from '@/components/ui/initials'
import { Pencil, Trash2 } from '@/components/icons'
import type { ColumnDef } from '@/components/data/DataTable'
import type { TrainerData } from '@/features/trainers/schemas'
import { getInitials } from '@/lib/format'

const HIDE = {
  specialization: '@max-[760px]:hidden',
  status: '@max-[600px]:hidden',
  actions: '',
} as const

interface ColumnsConfig {
  canEdit: boolean
  canDelete: boolean
  onEdit: (trainer: TrainerData) => void
  onDelete: (trainer: TrainerData) => void
}

/** Колонки таблицы тренеров (режим «Таблица») — фабрика с owner-only affordances. */
export function trainerColumns({
  canEdit,
  canDelete,
  onEdit,
  onDelete,
}: ColumnsConfig): ColumnDef<TrainerData>[] {
  const cols: ColumnDef<TrainerData>[] = [
    {
      id: 'name',
      header: 'Тренер',
      sortKey: 'name',
      cell: (t) => (
        <div className="flex min-w-0 items-center gap-3">
          {t.photoUrl ? (
            <img
              src={t.photoUrl}
              alt={t.fullName}
              className="size-9 rounded-xl object-cover"
            />
          ) : (
            <Initials
              initials={getInitials(t.fullName)}
              color="linear-gradient(135deg,#8b5cf6,#ec4899)"
              className="size-9 rounded-xl text-[12px]"
            />
          )}
          <div className="min-w-0">
            <div className="truncate text-[13px] font-semibold tracking-[-0.1px] text-fg">
              {t.fullName}
            </div>
            <div className="truncate text-[11.5px] text-fg-subtle">{t.specialization ?? '—'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'specialization',
      header: 'Специализация',
      headClassName: HIDE.specialization,
      cellClassName: cn(HIDE.specialization, 'text-[12.5px] text-fg-muted'),
      cell: (t) => t.specialization ?? '—',
    },
    {
      id: 'status',
      header: 'Статус',
      headClassName: HIDE.status,
      cellClassName: HIDE.status,
      cell: (t) => (
        <span
          className={cn(
            'rounded-full px-[9px] py-[3px] text-[10.5px] font-bold uppercase tracking-[0.3px]',
            t.isActive
              ? 'bg-primary-soft text-primary-deep dark:text-primary'
              : 'bg-surface-3 text-fg-muted',
          )}
        >
          {t.isActive ? 'Активна' : 'Неактивна'}
        </span>
      ),
    },
  ]

  if (canEdit || canDelete) {
    cols.push({
      id: 'actions',
      header: '',
      headClassName: 'w-[80px]',
      cellClassName: 'w-[80px] text-right',
      cell: (t) => (
        <div className="flex items-center justify-end gap-1">
          {canEdit && (
            <button
              type="button"
              aria-label="Редактировать тренера"
              onClick={(e) => {
                e.stopPropagation()
                onEdit(t)
              }}
              className="grid size-[30px] place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Pencil className="size-[15px]" />
            </button>
          )}
          {canDelete && (
            <button
              type="button"
              aria-label="Удалить тренера"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(t)
              }}
              className="grid size-[30px] place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-danger-soft hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Trash2 className="size-[15px]" />
            </button>
          )}
        </div>
      ),
    })
  }

  return cols
}
