import { useEffect, useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { useTrainer } from '@/features/trainers/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { TrainerHero } from './components/TrainerHero';
import { TrainerKpis } from './components/TrainerKpis';
import { OverviewTab } from './components/OverviewTab';
import { PayoutsTab } from './components/PayoutsTab';
import { HistoryTab } from './components/HistoryTab';
import { DetailTabs } from './components/shared';

type TabKey = 'overview' | 'payouts' | 'history';

const TABS: { value: TabKey; label: string }[] = [
  { value: 'overview', label: 'Обзор' },
  { value: 'payouts', label: 'Выплаты' },
  { value: 'history', label: 'История' },
];

export function TrainerPage() {
  const { trainerId = '' } = useParams<{ trainerId: string }>();
  const { hash } = useLocation();
  const { data: t, isPending, isError, refetch } = useTrainer(trainerId);
  const [tab, setTab] = useState<TabKey>('overview');

  // Поддержка прямых ссылок на вкладки (#payouts / #history), как в макете.
  useEffect(() => {
    const h = hash.replace('#', '');
    if (h === 'payouts' || h === 'history') setTab(h);
  }, [hash]);

  if (isPending) return <PageLoading />;
  if (isError || !t) return <PageError onRetry={() => void refetch()} />;

  return (
    <div className="mx-auto flex w-full max-w-[1120px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <TrainerHero trainer={t} />
      <TrainerKpis kpis={t.kpis} />
      <DetailTabs
        options={TABS}
        value={tab}
        onChange={setTab}
        ariaLabel="Разделы профиля тренера"
      />

      {tab === 'overview' && <OverviewTab trainer={t} />}
      {tab === 'payouts' && <PayoutsTab trainer={t} />}
      {tab === 'history' && <HistoryTab groups={t.timeline} />}
    </div>
  );
}
