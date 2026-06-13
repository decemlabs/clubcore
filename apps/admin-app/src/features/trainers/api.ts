import { useQuery } from '@tanstack/react-query';
import { mockResponse } from '@/api/client';
import { trainersPageData } from '@/mocks/trainers';
import { trainerDetail } from '@/mocks/trainer-detail';
import type { TrainersPageData } from './types';
import type { TrainerDetail } from './detail';

/** Ключи запросов тренеров (стабильные, для инвалидации). */
export const trainersKeys = {
  all: ['trainers'] as const,
  list: ['trainers', 'list'] as const,
  detail: (id: string) => ['trainers', 'detail', id] as const,
};

/**
 * Данные страницы «Тренеры» (сводка, KPI, вкладки, ростер, загрузка, выручка, заявки).
 * Пока резолвит мок; при появлении backend меняется только queryFn — страница не трогается.
 */
export function useTrainers() {
  return useQuery({
    queryKey: trainersKeys.list,
    queryFn: () => mockResponse<TrainersPageData>(trainersPageData),
  });
}

/**
 * Детальный профиль тренера по id. Пока один подробный мок — резолвим его
 * независимо от id; при появлении backend queryFn получит id.
 */
export function useTrainer(id: string) {
  return useQuery({
    queryKey: trainersKeys.detail(id),
    queryFn: () => mockResponse<TrainerDetail>(trainerDetail),
  });
}
