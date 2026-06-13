import { useState } from 'react';
import { cn } from '@/lib/cn';
import { Card, CardHeader } from '@/components/layout/Card';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { IntensityHeatmap } from '@/components/charts/IntensityHeatmap';
import { cellClass } from '@/components/charts/heatmap-utils';
import type { LoadHeatmapData } from '@/features/load/types';

type Range = 'week' | 'prev' | 'month';
const RANGES: SegmentedOption<Range>[] = [
  { value: 'week', label: 'Эта нед.' },
  { value: 'prev', label: 'Прошлая' },
  { value: 'month', label: 'Месяц' },
];

const SCALE: (0 | 1 | 2 | 3 | 5 | 6)[] = [0, 1, 2, 3, 5, 6];

export function LoadHeatmapCard({ data }: { data: LoadHeatmapData }) {
  const [range, setRange] = useState<Range>('week');
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Загруженность · день × час"
        subtitle="Эта неделя · % от вместимости (80 чел) · среднее за час"
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
          <span className="flex gap-0.5">
            {SCALE.map((l) => (
              <span key={l} className={cn('h-3 w-4 rounded-[3px]', cellClass(l))} />
            ))}
          </span>
          от 0% до перегрузки
        </span>
        <span className="ml-auto tabular-nums">
          Свободных слотов на неделе — <b className="font-semibold text-fg">{data.freeSlots}</b> ·
          окно для маркетинга — <b className="font-semibold text-fg">{data.marketingWindow}</b>
        </span>
      </div>
    </Card>
  );
}
