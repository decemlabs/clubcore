import { useMemo, useState } from 'react';
// TODO Phase 102-03: replace mock with useTrainerSlots (real schedule read layer)
import { useQuery } from '@tanstack/react-query';
import { scheduleData } from '@/mocks/schedule';
import type { ScheduleData } from '@/features/schedule/types';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { useModals } from '@/components/modals/modals-context';
import { Plus } from '@/components/icons';
import { SchedulePageHead, type CalView } from './components/SchedulePageHead';
import { ScheduleToolbar, type ScheduleFilters } from './components/ScheduleToolbar';
import { WeekCalendar } from './components/WeekCalendar';

/** Interim mock hook — will be replaced in Phase 102-03 with real calendar read-merge. */
function useSchedule() {
  return useQuery({
    queryKey: ['schedule', 'week', 'mock'],
    // Simulate network delay without importing @/api/client in a page (import boundary)
    queryFn: (): Promise<ScheduleData> =>
      new Promise((resolve) => setTimeout(() => resolve(scheduleData), 120)),
  });
}

export function SchedulePage() {
  const { data, isPending, isError, refetch } = useSchedule();
  const { open } = useModals();

  const [view, setView] = useState<CalView>('week');
  const [filters, setFilters] = useState<ScheduleFilters>({
    trainer: 'all',
    type: 'all',
    hall: 'all',
  });

  const filtered = useMemo(() => {
    if (!data) return null;
    const events = data.events.filter(
      (e) =>
        (filters.trainer === 'all' || e.trainer === filters.trainer) &&
        (filters.type === 'all' || e.kind === filters.type) &&
        (filters.hall === 'all' || String(e.hall) === filters.hall),
    );
    return { ...data, events };
  }, [data, filters]);

  if (isPending) return <PageLoading />;
  if (isError || !data || !filtered) return <PageError onRetry={() => void refetch()} />;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <SchedulePageHead data={data} view={view} onViewChange={setView} />

      <ScheduleToolbar
        data={data}
        filters={filters}
        onChange={(patch) => setFilters((p) => ({ ...p, ...patch }))}
      />

      <WeekCalendar
        data={filtered}
        onEventClick={() => open('session', { session: { screen: 'detail' } })}
      />

      {/* FAB «Создать сессию» → модалка создания тренировки */}
      <button
        type="button"
        aria-label="Создать сессию"
        onClick={() => open('session', { session: { screen: 'create' } })}
        className="fixed bottom-6 right-6 z-30 inline-flex items-center gap-2 rounded-full bg-fg px-4 py-3 text-[13px] font-semibold text-bg shadow-3 transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg max-lg:bottom-[calc(88px+env(safe-area-inset-bottom))] dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
      >
        <Plus className="size-4" strokeWidth={2.4} />
        <span className="max-sm:hidden">Создать сессию</span>
      </button>
    </div>
  );
}
