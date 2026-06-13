import { useState } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { Calendar, ChevronDown } from '@/components/icons';

type Period = 'week' | 'month' | 'quarter' | 'year';
const PERIODS: SegmentedOption<Period>[] = [
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
  { value: 'quarter', label: 'Квартал' },
  { value: 'year', label: 'Год' },
];

export function ReportsPageHead({
  periodLabel,
  periodDelta,
  dateRange,
}: {
  periodLabel: string;
  periodDelta: string;
  dateRange: string;
}) {
  const [period, setPeriod] = useState<Period>('month');
  return (
    <PageHeader
      title="Отчёты"
      subtitle={
        <>
          Период: <b className="font-semibold text-fg">{periodLabel}</b> · к марту{' '}
          <b className="font-semibold text-primary-deep dark:text-primary">{periodDelta}</b>
        </>
      }
      actionsClassName="max-sm:-mx-4 max-sm:overflow-x-auto max-sm:px-4 max-sm:[scrollbar-width:none]"
      actions={
        <>
          <button
            type="button"
            title="Выбрать период"
            className="inline-flex h-[38px] shrink-0 items-center gap-2 rounded-full border-[0.5px] border-border bg-surface px-3.5 text-[13px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring max-sm:hidden"
          >
            <Calendar className="size-3.5 text-fg-subtle" />
            {dateRange}
            <ChevronDown className="size-3 text-fg-subtle" strokeWidth={2.4} />
          </button>
          <Segmented
            options={PERIODS}
            value={period}
            onChange={setPeriod}
            ariaLabel="Период отчёта"
          />
        </>
      }
    />
  );
}
