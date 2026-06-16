import { useState } from 'react';
import { Card, CardHeader } from '@/components/layout/Card';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { ChevronUp } from '@/components/icons';
import { AreaTrendChart } from '@/components/charts/AreaTrendChart';
import type { RevenueData } from '@/features/reports/types';

type Agg = 'day' | 'week';
const AGG_OPTIONS: SegmentedOption<Agg>[] = [
  { value: 'day', label: 'День' },
  { value: 'week', label: 'Неделя' },
];

export function RevenueCard({ data }: { data: RevenueData }) {
  const [agg, setAgg] = useState<Agg>('day');

  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Выручка по дням"
        subtitle="апрель 2026 · сравнение с мартом"
        action={
          <Segmented
            variant="mini"
            options={AGG_OPTIONS}
            value={agg}
            onChange={setAgg}
            ariaLabel="Агрегация"
          />
        }
      />

      <div className="px-5 pb-1">
        <div className="text-[30px] font-bold leading-none tracking-[-0.8px] tabular-nums">
          {data.bigValue}
          <span className="ml-1 text-[16px] font-semibold text-fg-muted">₽</span>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[12.5px] text-fg-muted">
          <span className="inline-flex items-center gap-[3px] rounded-full bg-primary-soft px-[7px] py-0.5 text-xs font-semibold text-primary-deep dark:text-primary">
            <ChevronUp className="size-2.5" strokeWidth={3} />
            {data.deltaLabel}
          </span>
          <span>{data.vsLabel}</span>
        </div>
      </div>

      <AreaTrendChart
        data={data.points}
        ticks={data.ticks}
        yMax={data.yMax}
        height={240}
        className="px-2"
        renderTooltip={(p) => (
          <div className="rounded-lg bg-fg px-2.5 py-1.5 text-[11.5px] font-semibold leading-tight text-bg shadow-lg dark:border-[0.5px] dark:border-border-strong dark:bg-surface dark:text-fg">
            <div className="text-[10px] font-medium uppercase tracking-[0.3px] opacity-70">
              {p.label} апреля
            </div>
            <div className="tabular-nums">{p.value}к ₽</div>
            {p.compare != null ? (
              <div className="tabular-nums opacity-60">март · {p.compare}к ₽</div>
            ) : null}
          </div>
        )}
      />

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t-[0.5px] border-border px-5 py-3.5 text-[12px] text-fg-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-[3px] bg-primary" />
          Апрель <b className="font-semibold tabular-nums text-fg">{data.legend.aprTotal}</b>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0 w-3 border-t-2 border-dashed border-fg-subtle" />
          Март <b className="font-semibold tabular-nums text-fg">{data.legend.marTotal}</b>
        </span>
        <span className="ml-auto">
          Лучший день — <b className="font-semibold text-fg">{data.legend.bestDay}</b> ·{' '}
          {data.legend.bestVal}
        </span>
      </div>
    </Card>
  );
}
