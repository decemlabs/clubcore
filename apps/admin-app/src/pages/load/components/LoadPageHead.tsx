import { useState } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';

type Period = 'today' | 'week' | 'month';
const PERIODS: SegmentedOption<Period>[] = [
  { value: 'today', label: 'Сегодня' },
  { value: 'week', label: 'Эта неделя' },
  { value: 'month', label: 'Месяц' },
];

export function LoadPageHead({ avg, peak }: { avg: string; peak: string }) {
  const [period, setPeriod] = useState<Period>('week');
  return (
    <PageHeader
      title="Загруженность"
      subtitle={
        <>
          Среднее за неделю — <b className="font-semibold text-fg">{avg}</b> · пик во{' '}
          <b className="font-semibold text-fg">{peak}</b>
        </>
      }
      actions={
        <Segmented options={PERIODS} value={period} onChange={setPeriod} ariaLabel="Период" />
      }
    />
  );
}
