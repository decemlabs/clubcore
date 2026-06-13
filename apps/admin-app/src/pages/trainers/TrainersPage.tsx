import { useMemo, useRef, useState, type RefObject } from 'react';
import type { DataTableSort } from '@/components/data/DataTable';
import { useTrainers } from '@/features/trainers/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import type { Trainer, TrainerCategory, TrainerTab } from '@/features/trainers/types';
import { SectionHead } from '@/components/layout/SectionHead';
import { Card } from '@/components/layout/Card';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { DataTable } from '@/components/data/DataTable';
import { TrainersPageHead, type RosterView } from './components/TrainersPageHead';
import { TrainersKpis } from './components/TrainersKpis';
import { TrainerFilterTabs } from './components/TrainerFilterTabs';
import { RosterCard, HireCard } from './components/RosterCard';
import { trainerColumns } from './components/columns';
import { LoadHeatmap } from './components/LoadHeatmap';
import { EarningsCard } from './components/EarningsCard';
import { RequestsCard } from './components/RequestsCard';
import { CATEGORY_LABEL } from './components/status';

type SpecFilter = 'all' | TrainerCategory;
type SortKey = 'name' | 'rating' | 'trainings' | 'revenue' | 'load';
type WeekNav = 'prev' | 'this' | 'next';
type TrainerSort = { key: SortKey; dir: DataTableSort['dir'] };

const DEFAULT_DIR: Record<SortKey, DataTableSort['dir']> = {
  name: 'asc',
  rating: 'desc',
  trainings: 'desc',
  revenue: 'desc',
  load: 'desc',
};

function compare(a: Trainer, b: Trainer, sort: TrainerSort): number {
  const m = sort.dir === 'asc' ? 1 : -1;
  switch (sort.key) {
    case 'name':
      return a.name.localeCompare(b.name, 'ru') * m;
    case 'rating':
      return (a.rating - b.rating) * m;
    case 'trainings':
      return (a.trainings - b.trainings) * m;
    case 'revenue':
      return (a.revenue - b.revenue) * m;
    case 'load':
      return (a.loadPct - b.loadPct) * m;
  }
}

const WEEK_OPTIONS: SegmentedOption<WeekNav>[] = [
  { value: 'prev', label: 'Прошлая' },
  { value: 'this', label: 'Эта неделя' },
  { value: 'next', label: 'Следующая' },
];

export function TrainersPage() {
  const { data, isPending, isError, refetch } = useTrainers();

  const [tab, setTab] = useState<TrainerTab>('roster');
  const [view, setView] = useState<RosterView>('cards');
  const [spec, setSpec] = useState<SpecFilter>('all');
  const [week, setWeek] = useState<WeekNav>('this');
  const [sort, setSort] = useState<TrainerSort>({ key: 'revenue', dir: 'desc' });

  const rosterRef = useRef<HTMLElement>(null);
  const loadRef = useRef<HTMLElement>(null);
  const earnRef = useRef<HTMLElement>(null);

  const trainers = data?.trainers;

  const specOptions = useMemo<SegmentedOption<SpecFilter>[]>(() => {
    const counts: Record<TrainerCategory, number> = { strength: 0, cardio: 0, 'mind-body': 0 };
    (trainers ?? []).forEach((t) => {
      counts[t.category] += 1;
    });
    return [
      { value: 'all', label: `Все · ${trainers?.length ?? 0}` },
      { value: 'strength', label: `${CATEGORY_LABEL.strength} · ${counts.strength}` },
      { value: 'cardio', label: `${CATEGORY_LABEL.cardio} · ${counts.cardio}` },
      { value: 'mind-body', label: `${CATEGORY_LABEL['mind-body']} · ${counts['mind-body']}` },
    ];
  }, [trainers]);

  const visible = useMemo(
    () => (spec === 'all' ? (trainers ?? []) : (trainers ?? []).filter((t) => t.category === spec)),
    [trainers, spec],
  );
  const tableRows = useMemo(
    () => [...visible].sort((a, b) => compare(a, b, sort)),
    [visible, sort],
  );

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  const sectionRef: Partial<Record<TrainerTab, RefObject<HTMLElement>>> = {
    roster: rosterRef,
    load: loadRef,
    payouts: earnRef,
    requests: earnRef,
  };
  const handleTab = (next: TrainerTab) => {
    setTab(next);
    sectionRef[next]?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  const handleSort = (key: string) =>
    setSort((prev) =>
      prev.key === key
        ? { key: prev.key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key: key as SortKey, dir: DEFAULT_DIR[key as SortKey] },
    );

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <TrainersPageHead summary={data.summary} view={view} onViewChange={setView} />

      <TrainersKpis kpis={data.kpis} />

      <TrainerFilterTabs tabs={data.tabs} value={tab} onChange={handleTab} />

      {/* Команда */}
      <section ref={rosterRef} className="flex scroll-mt-24 flex-col gap-3.5">
        <SectionHead
          title={data.rosterTitle}
          subtitle={data.rosterSubtitle}
          action={
            <Segmented
              variant="mini"
              options={specOptions}
              value={spec}
              onChange={setSpec}
              ariaLabel="Специализация"
            />
          }
        />

        {view === 'cards' ? (
          <div className="@container">
            <div className="grid grid-cols-1 gap-3.5 @min-[640px]:grid-cols-2 @min-[1000px]:grid-cols-3">
              {visible.map((t) => (
                <RosterCard key={t.id} trainer={t} />
              ))}
              <HireCard />
            </div>
          </div>
        ) : (
          <Card as="section" className="@container">
            <div className="hidden overflow-x-auto @min-[640px]:block">
              <DataTable
                data={tableRows}
                columns={trainerColumns}
                getRowId={(t) => t.id}
                sort={sort}
                onSort={handleSort}
              />
            </div>
            <div className="grid gap-3.5 p-4 @min-[640px]:hidden">
              {visible.map((t) => (
                <RosterCard key={t.id} trainer={t} />
              ))}
            </div>
          </Card>
        )}
      </section>

      {/* Загрузка */}
      <section ref={loadRef} className="flex scroll-mt-24 flex-col gap-3.5">
        <SectionHead
          title={`Загрузка · неделя ${data.heatmap.weekLabel}`}
          subtitle={data.loadSubtitle}
          action={
            <Segmented
              variant="mini"
              options={WEEK_OPTIONS}
              value={week}
              onChange={setWeek}
              ariaLabel="Неделя"
            />
          }
        />
        <LoadHeatmap data={data.heatmap} />
      </section>

      {/* Выручка + Заявки */}
      <section ref={earnRef} className="grid scroll-mt-24 gap-4 lg:grid-cols-[1.6fr_1fr]">
        <EarningsCard data={data.earnings} />
        <RequestsCard data={data.requests} />
      </section>
    </div>
  );
}
