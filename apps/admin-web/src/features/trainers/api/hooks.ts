import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { trainersKeys } from './keys'
import { services } from '@/shared/api/services'
import type { CreateTrainerInput, UpdateTrainerInput } from '../model/schema'
import type { TrainerId } from '@/entities/trainer'

export function useTrainersList(search: { active?: string; page: number; pageSize: number }) {
  return useQuery({
    queryKey: trainersKeys.list(search),
    queryFn: () =>
      services.trainers.list({
        active:
          search.active === 'true' ? true : search.active === 'false' ? false : undefined,
        page: search.page,
        pageSize: search.pageSize,
      }),
    staleTime: 30_000,
  })
}

export function useTrainer(id: TrainerId) {
  return useQuery({
    queryKey: trainersKeys.detail(id),
    queryFn: () => services.trainers.get(id),
    enabled: !!id,
    staleTime: 30_000,
  })
}

export function useCreateTrainer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateTrainerInput) => services.trainers.create(input),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: trainersKeys.all })
    },
  })
}

export function useUpdateTrainer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: TrainerId; input: UpdateTrainerInput }) =>
      services.trainers.update(id, input),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: trainersKeys.all })
    },
  })
}

export function useDeleteTrainer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: TrainerId) => services.trainers.delete(id),
    onSuccess: () => {
      // Note: invalidate on success only — 409 trainer_in_use must stay visible in AlertDialog
      void qc.invalidateQueries({ queryKey: trainersKeys.all })
    },
  })
}
