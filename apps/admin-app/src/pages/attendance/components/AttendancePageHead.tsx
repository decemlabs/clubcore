import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/layout/PageHeader';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { Download } from '@/components/icons';
import type { AttendanceData } from '@/features/attendance/types';

type Period = 'week' | 'month' | 'quarter' | 'year';
const PERIODS: SegmentedOption<Period>[] = [
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
  { value: 'quarter', label: 'Квартал' },
  { value: 'year', label: 'Год' },
];

export function AttendancePageHead({ subtitle }: { subtitle: AttendanceData['subtitle'] }) {
  const [period, setPeriod] = useState<Period>('month');
  return (
    <PageHeader
      title="Посещаемость"
      subtitle={
        <>
          <b className="font-semibold text-fg">{subtitle.period}</b> ·{' '}
          <b className="font-semibold text-fg">{subtitle.visits}</b> визитов · среднее на клиента{' '}
          <b className="font-semibold text-fg">{subtitle.avg}</b> ·{' '}
          <span className="inline-flex items-center gap-1.5 font-medium text-primary-deep dark:text-primary">
            <span className="size-1.5 animate-pulse rounded-full bg-primary-deep dark:bg-primary" />
            {subtitle.live}
          </span>
        </>
      }
      actionsClassName="max-sm:-mx-4 max-sm:overflow-x-auto max-sm:px-4 max-sm:[scrollbar-width:none]"
      actions={
        <>
          <Segmented options={PERIODS} value={period} onChange={setPeriod} ariaLabel="Период" />
          <Button
            variant="outline"
            className="h-[38px] shrink-0 gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold max-sm:w-[38px] max-sm:px-0"
          >
            <Download className="size-[14px]" />
            <span className="max-sm:hidden">Экспорт CSV</span>
          </Button>
        </>
      }
    />
  );
}
