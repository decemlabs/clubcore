import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Button } from '@/shared/ui/button'
import { Skeleton } from '@/shared/ui/skeleton'
import { t } from '@/shared/i18n'
import { Route } from '@/routes/_protected/trainers'
import { useTrainersList } from '../api/hooks'
import { ActiveFilterPill } from './ActiveFilterPill'
import { TrainersTable } from './TrainersTable'
import { TrainerFormDialog } from './TrainerFormDialog'
import { DeleteTrainerAlertDialog } from './DeleteTrainerAlertDialog'
import type { Trainer } from '@/entities/trainer'

export function TrainersPage() {
  const search = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })

  const [formOpen, setFormOpen] = useState(false)
  const [editingTrainer, setEditingTrainer] = useState<Trainer | undefined>(undefined)
  const [deletingTrainer, setDeletingTrainer] = useState<Trainer | null>(null)

  const query = useTrainersList(search)
  const data = query.data

  const openCreate = () => {
    setEditingTrainer(undefined)
    setFormOpen(true)
  }

  const openEdit = (trainer: Trainer) => {
    setEditingTrainer(trainer)
    setFormOpen(true)
  }

  const openDelete = (trainer: Trainer) => {
    setDeletingTrainer(trainer)
  }

  const handleFilterChange = (value: 'true' | 'false' | undefined) => {
    void navigate({
      search: (prev) => ({ ...prev, active: value, page: 1 }),
    })
  }

  const handlePaginationChange = (page: number, pageSize: number) => {
    void navigate({
      search: (prev) => ({ ...prev, page, pageSize }),
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t('trainers.heading')}</h1>
        <Button size="sm" onClick={openCreate}>
          {t('trainers.actions.create')}
        </Button>
      </div>

      <ActiveFilterPill value={search.active} onChange={handleFilterChange} />

      {query.isError && (
        <div className="space-y-3 rounded-md border p-6 text-center">
          <h2 className="text-lg font-semibold">{t('trainers.errorState.heading')}</h2>
          <Button onClick={() => void query.refetch()}>{t('common.retryLoad')}</Button>
        </div>
      )}

      {query.isLoading && (
        <div className="space-y-3 rounded-md border p-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex gap-4">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-12" />
            </div>
          ))}
        </div>
      )}

      {query.isSuccess && data && data.total === 0 && !search.active && (
        <div className="space-y-3 rounded-md border p-6 text-center">
          <h2 className="text-lg font-semibold">{t('trainers.empty.heading')}</h2>
          <p className="text-muted-foreground text-sm">{t('trainers.empty.body')}</p>
          <Button size="sm" onClick={openCreate}>
            {t('trainers.actions.create')}
          </Button>
        </div>
      )}

      {query.isSuccess && data && data.total === 0 && search.active && (
        <div className="space-y-3 rounded-md border p-6 text-center">
          <h2 className="text-lg font-semibold">{t('trainers.noResults.heading')}</h2>
          <p className="text-muted-foreground text-sm">{t('trainers.noResults.body')}</p>
        </div>
      )}

      {query.isSuccess && data && data.total > 0 && (
        <TrainersTable
          data={data}
          onPaginationChange={handlePaginationChange}
          onEdit={openEdit}
          onDelete={openDelete}
        />
      )}

      <TrainerFormDialog
        open={formOpen}
        onClose={() => {
          setFormOpen(false)
          setEditingTrainer(undefined)
        }}
        trainer={editingTrainer}
      />

      {deletingTrainer && (
        <DeleteTrainerAlertDialog
          open={!!deletingTrainer}
          onClose={() => setDeletingTrainer(null)}
          trainer={deletingTrainer}
        />
      )}
    </div>
  )
}
