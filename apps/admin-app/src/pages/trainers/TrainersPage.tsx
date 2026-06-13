/**
 * TrainersPage — Phase 102-02 TRN-01.
 *
 * Wired to real GET /api/v1/trainers (active=true).
 * Roster section only — Load, Requests, Earnings sections removed (no backend / deferred).
 * TrainerFilterTabs hidden (single-tab is noise after reduction).
 * Owner gets create + edit + delete affordances (can()-gated).
 * Reception sees read-only roster.
 */
import { useState } from 'react'
import { useTrainers, useDeleteTrainer, ApiError } from '@/features/trainers/api'
import { useSession } from '@/features/auth/api'
import { can } from '@/shared/session/can'
import type { TrainerData } from '@/features/trainers/schemas'
import { PageLoading, PageError } from '@/components/feedback/PageState'
import { EmptyState } from '@/components/feedback/EmptyState'
import { SectionHead } from '@/components/layout/SectionHead'
import { Card } from '@/components/layout/Card'
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented'
import { DataTable } from '@/components/data/DataTable'
import type { DataTableSort } from '@/components/data/DataTable'
import { Users, UserPlus } from '@/components/icons'
import { TrainersPageHead, type RosterView } from './components/TrainersPageHead'
import { RosterCard } from './components/RosterCard'
import { trainerColumns } from './components/columns'
import { TrainerFormModal } from '@/components/modals/TrainerFormModal'
import { ConfirmModal } from '@/components/modals/ConfirmModal'
import { toast } from 'sonner'

type SortKey = 'name'
type TrainerSort = { key: SortKey; dir: DataTableSort['dir'] }

const DEFAULT_DIR: Record<SortKey, DataTableSort['dir']> = {
  name: 'asc',
}

function compare(a: TrainerData, b: TrainerData, sort: TrainerSort): number {
  const m = sort.dir === 'asc' ? 1 : -1
  switch (sort.key) {
    case 'name':
      return a.fullName.localeCompare(b.fullName, 'ru') * m
  }
}

export function TrainersPage() {
  const sessionQuery = useSession()
  const role = sessionQuery.data?.role ?? 'reception'

  const { data, isPending, isError, refetch } = useTrainers({ active: true })
  const deleteTrainer = useDeleteTrainer()

  const [view, setView] = useState<RosterView>('cards')
  const [sort, setSort] = useState<TrainerSort>({ key: 'name', dir: 'asc' })

  // Modal state
  const [formOpen, setFormOpen] = useState(false)
  const [formTrainer, setFormTrainer] = useState<TrainerData | undefined>(undefined)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<TrainerData | undefined>(undefined)

  const VIEW_OPTIONS: SegmentedOption<RosterView>[] = [
    { value: 'cards', label: 'Карточки' },
    { value: 'table', label: 'Таблица' },
  ]

  if (isPending) return <PageLoading />
  if (isError || !data) return <PageError onRetry={() => void refetch()} />

  const items = data.items
  const total = data.total

  // Sort
  const sortedItems = [...items].sort((a, b) => compare(a, b, sort))

  const openCreate = () => {
    if (!can(role, 'create', 'trainers')) return
    setFormTrainer(undefined)
    setFormOpen(true)
  }

  const openEdit = (trainer: TrainerData) => {
    if (!can(role, 'edit', 'trainers')) return
    setFormTrainer(trainer)
    setFormOpen(true)
  }

  const openDelete = (trainer: TrainerData) => {
    if (!can(role, 'delete', 'trainers')) return
    setDeleteTarget(trainer)
    setConfirmOpen(true)
  }

  const handleSort = (key: string) =>
    setSort((prev) =>
      prev.key === key
        ? { key: prev.key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key: key as SortKey, dir: DEFAULT_DIR[key as SortKey] ?? 'asc' },
    )

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <TrainersPageHead
        total={total}
        view={view}
        onViewChange={setView}
        canCreate={can(role, 'create', 'trainers')}
        onCreateClick={openCreate}
      />

      {/* Команда — Roster only; Load/Requests/Earnings sections removed (no backend / deferred Phase 104) */}
      <section className="flex scroll-mt-24 flex-col gap-3.5">
        <SectionHead
          title="Команда"
          subtitle={`Тренеров: ${total}`}
          action={
            <Segmented
              variant="mini"
              options={VIEW_OPTIONS}
              value={view}
              onChange={setView}
              ariaLabel="Вид списка"
            />
          }
        />

        {items.length === 0 ? (
          <EmptyState
            icon={Users}
            title="Тренеров нет"
            message="Добавьте первого тренера в команду."
            action={
              can(role, 'create', 'trainers') ? (
                <button
                  type="button"
                  onClick={openCreate}
                  className="inline-flex h-9 items-center gap-1.5 rounded-full border-[0.5px] border-border bg-surface px-3.5 text-[13px] font-semibold transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <UserPlus className="size-[14px]" />
                  Добавить тренера
                </button>
              ) : undefined
            }
          />
        ) : view === 'cards' ? (
          <div className="@container">
            <div className="grid grid-cols-1 gap-3.5 @min-[640px]:grid-cols-2 @min-[1000px]:grid-cols-3">
              {sortedItems.map((t) => (
                <RosterCard
                  key={t.id}
                  trainer={t}
                  canEdit={can(role, 'edit', 'trainers')}
                  canDelete={can(role, 'delete', 'trainers')}
                  onEdit={openEdit}
                  onDelete={openDelete}
                />
              ))}
            </div>
          </div>
        ) : (
          <Card as="section" className="@container">
            <div className="hidden overflow-x-auto @min-[640px]:block">
              <DataTable
                data={sortedItems}
                columns={trainerColumns({
                  canEdit: can(role, 'edit', 'trainers'),
                  canDelete: can(role, 'delete', 'trainers'),
                  onEdit: openEdit,
                  onDelete: openDelete,
                })}
                getRowId={(t) => t.id}
                sort={sort}
                onSort={handleSort}
              />
            </div>
            <div className="grid gap-3.5 p-4 @min-[640px]:hidden">
              {sortedItems.map((t) => (
                <RosterCard
                  key={t.id}
                  trainer={t}
                  canEdit={can(role, 'edit', 'trainers')}
                  canDelete={can(role, 'delete', 'trainers')}
                  onEdit={openEdit}
                  onDelete={openDelete}
                />
              ))}
            </div>
          </Card>
        )}
      </section>

      {/* TrainerFormModal — edit or create */}
      <TrainerFormModal
        open={formOpen}
        onOpenChange={setFormOpen}
        trainer={formTrainer}
        onSuccess={() => void refetch()}
      />

      {/* Confirm delete */}
      <ConfirmModal
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        payload={
          deleteTarget
            ? {
                title: 'Удалить тренера?',
                message: (
                  <>
                    «{deleteTarget.fullName}» будет удалён из системы. Это действие нельзя отменить.
                  </>
                ),
                tone: 'danger',
                confirmLabel: 'Удалить',
                cancelLabel: 'Отмена',
                onConfirm: async () => {
                  try {
                    await deleteTrainer.mutateAsync(deleteTarget.id)
                    toast.success('Тренер удалён')
                    void refetch()
                  } catch (err) {
                    if (err instanceof ApiError && err.code === 'trainer_in_use') {
                      toast.error('Нельзя удалить', {
                        description: 'У тренера есть активные слоты или брони.',
                      })
                    }
                    // Rethrow to keep modal open on error (ConfirmModal pattern)
                    throw err
                  }
                },
              }
            : undefined
        }
      />
    </div>
  )
}
