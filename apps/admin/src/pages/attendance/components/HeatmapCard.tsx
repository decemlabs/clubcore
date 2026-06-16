import { useState } from 'react';
import { cn } from '@/lib/cn';
import { Card, CardHeader } from '@/components/layout/Card';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { IntensityHeatmap } from '@/components/charts/IntensityHeatmap';
import { HEAT_SCALE, cellClass } from '@/components/charts/heatmap-utils';
import type { HeatmapData } from '@/features/attendance/types';

type Range = 'week' | 'month' | 'quarter';
const RANGES: SegmentedOption<Range>[] = [
  { value: 'week', label: 'Эта нед.' },
  { value: 'month', label: 'Май' },
  { value: 'quarter', label: 'Квартал' },
];

export function HeatmapCard({ data }: { data: HeatmapData }) {
  const [range, setRange] = useState<Range>('month');
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Карта посещаемости · день × час"
        subtitle="Средняя плотность визитов за май · 1 клетка = % от вместимости (60 чел)"
        action={
          <Segmented
            variant="mini"
            options={RANGES}
            value={range}
            onChange={setRange}
            ariaLabel="Период карты"
          />
        }
      />
      <div className="px-5 pb-3">
        <IntensityHeatmap hours={data.hours} rows={data.rows} />
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t-[0.5px] border-border px-5 py-3 text-[11.5px] text-fg-muted">
        <span className="inline-flex items-center gap-1.5">
          Меньше
          <span className="flex gap-0.5">
            {HEAT_SCALE.map((l) => (
              <span key={l} className={cn('size-2.5 rounded-[3px]', cellClass(l as 0))} />
            ))}
          </span>
          Больше
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-[3px] bg-danger" /> Перегруз
        </span>
        <span className="ml-auto tabular-nums">
          Окон {data.windows} · <b className="font-semibold text-fg">{data.overload}</b> в перегрузе
          · Тишина: <b className="font-semibold text-fg">{data.quietest}</b> · Сейчас:{' '}
          <b className="font-semibold text-fg">{data.now}</b>
        </span>
      </div>
    </Card>
  );
}
