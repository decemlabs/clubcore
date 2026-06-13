import { useAttendance } from '@/features/attendance/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { AttendancePageHead } from './components/AttendancePageHead';
import { AttendanceFilters } from './components/AttendanceFilters';
import { AttendanceKpis } from './components/AttendanceKpis';
import { HeatmapCard } from './components/HeatmapCard';
import { PeakHero } from './components/PeakHero';
import { HourCurveCard } from './components/HourCurveCard';
import { FrequencyCard } from './components/FrequencyCard';
import { DayOfWeekCard } from './components/DayOfWeekCard';
import { DurationCard } from './components/DurationCard';
import { CohortCard } from './components/CohortCard';
import { AnomalyCards } from './components/AnomalyCards';
import { RiskList } from './components/RiskList';

export function AttendancePage() {
  const { data, isPending, isError, refetch } = useAttendance();

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <AttendancePageHead subtitle={data.subtitle} />

      <AttendanceFilters />

      <AttendanceKpis kpis={data.kpis} />

      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <HeatmapCard data={data.heatmap} />
        <PeakHero data={data.peak} />
      </div>

      <HourCurveCard data={data.curve} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[1.2fr_1fr_1fr]">
        <FrequencyCard data={data.frequency} />
        <DayOfWeekCard bars={data.dow} />
        <DurationCard data={data.duration} />
      </div>

      <CohortCard data={data.cohort} />

      <AnomalyCards items={data.anomalies} />

      <RiskList data={data.risk} />
    </div>
  );
}
