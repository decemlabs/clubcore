import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/layout/PageHeader';
import { Download } from '@/components/icons';
import type { DashboardPeriod } from '@/features/dashboard/types';
import { Segmented, type SegmentedOption } from './Segmented';

const PERIODS: SegmentedOption<DashboardPeriod>[] = [
  { value: 'day', label: 'День' },
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
  { value: 'year', label: 'Год' },
];

interface PageHeadProps {
  dateLabel: string;
  greetingName: string;
  trainingsToday: number;
  expectedVisits: number;
  defaultPeriod: DashboardPeriod;
}

export function PageHead({
  dateLabel,
  greetingName,
  trainingsToday,
  expectedVisits,
  defaultPeriod,
}: PageHeadProps) {
  const [period, setPeriod] = useState<DashboardPeriod>(defaultPeriod);

  return (
    <PageHeader
      title={dateLabel}
      subtitle={
        <>
          Привет, {greetingName}! Сегодня в зале{' '}
          <b className="font-semibold text-fg">{trainingsToday} тренировок</b>, ожидается{' '}
          <b className="font-semibold text-fg">{expectedVisits} визитов</b>.
        </>
      }
      actionsClassName="max-sm:-mx-4 max-sm:overflow-x-auto max-sm:px-4 max-sm:[scrollbar-width:none]"
      actions={
        <>
          <Segmented options={PERIODS} value={period} onChange={setPeriod} ariaLabel="Период" />
          <Button
            variant="outline"
            className="h-[38px] shrink-0 gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold"
          >
            <Download className="size-[14px]" />
            Экспорт
          </Button>
        </>
      }
    />
  );
}
