import { useReports } from '@/features/reports/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { ReportsPageHead } from './components/ReportsPageHead';
import { ReportsKpis } from './components/ReportsKpis';
import { RevenueCard } from './components/RevenueCard';
import { RevenueMixCard } from './components/RevenueMixCard';
import { RankedListCard } from './components/RankedListCard';

export function ReportsPage() {
  const { data, isPending, isError, refetch } = useReports();

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <ReportsPageHead
        periodLabel={data.periodLabel}
        periodDelta={data.periodDelta}
        dateRange={data.dateRange}
      />

      <ReportsKpis kpis={data.kpis} />

      <div className="grid gap-4 lg:grid-cols-[1.7fr_1fr]">
        <RevenueCard data={data.revenue} />
        <RevenueMixCard data={data.mix} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <RankedListCard data={data.topPlans} />
        <RankedListCard data={data.topTrainers} />
      </div>
    </div>
  );
}
