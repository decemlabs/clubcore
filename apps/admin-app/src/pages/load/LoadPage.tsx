import { useLoad } from '@/features/load/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { LoadPageHead } from './components/LoadPageHead';
import { LoadKpis } from './components/LoadKpis';
import { LiveNowCard } from './components/LiveNowCard';
import { LoadHeatmapCard } from './components/LoadHeatmapCard';

export function LoadPage() {
  const { data, isPending, isError, refetch } = useLoad();

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <LoadPageHead avg={data.subtitleAvg} peak={data.subtitlePeak} />

      <LoadKpis kpis={data.kpis} />

      <div className="grid gap-4 xl:grid-cols-[1fr_2.2fr]">
        <LiveNowCard data={data.live} />
        <LoadHeatmapCard data={data.heatmap} />
      </div>
    </div>
  );
}
