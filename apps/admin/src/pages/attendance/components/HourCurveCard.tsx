import { useState } from 'react';
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, XAxis, YAxis } from 'recharts';
import { Card, CardHeader } from '@/components/layout/Card';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { ChartContainer, type ChartConfig } from '@/components/ui/chart';
import type { HourCurveData } from '@/features/attendance/types';

type Mode = 'people' | 'capacity';
const MODES: SegmentedOption<Mode>[] = [
  { value: 'people', label: 'Чел / час' },
  { value: 'capacity', label: '% от capacity' },
];
const CONFIG: ChartConfig = {
  weekday: { label: 'Будни', color: 'var(--primary-deep)' },
  today: { label: 'Сегодня', color: 'var(--fg)' },
};

function LegendDot({ className }: { className: string }) {
  return <span className={className} />;
}

export function HourCurveCard({ data }: { data: HourCurveData }) {
  const [mode, setMode] = useState<Mode>('people');
  return (
    <Card as="section" className="flex flex-col">
      <CardHeader
        title="Час дня · сегодня vs средняя по будням / выходным"
        subtitle="Будни — средняя за май · выходные — сб + вс · сегодня — пятница"
        action={
          <Segmented
            variant="mini"
            options={MODES}
            value={mode}
            onChange={setMode}
            ariaLabel="Единицы кривой"
          />
        }
      />
      <div className="px-3 pb-1">
        <ChartContainer config={CONFIG} className="aspect-auto h-[260px] w-full">
          <ComposedChart data={data.points} margin={{ top: 14, right: 16, left: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="curveWeekday" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2dd4a4" stopOpacity={0.18} />
                <stop offset="100%" stopColor="#2dd4a4" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              vertical={false}
              stroke="var(--border)"
              strokeDasharray="3 4"
              strokeOpacity={0.6}
            />
            <XAxis
              dataKey="hour"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tick={{ fontSize: 10 }}
            />
            <YAxis hide domain={[0, 80]} />
            <ReferenceLine
              y={data.capacity}
              stroke="var(--danger)"
              strokeDasharray="4 4"
              strokeOpacity={0.85}
              label={{
                value: `capacity ${data.capacity}`,
                position: 'insideTopRight',
                fill: 'var(--danger)',
                fontSize: 10,
              }}
            />
            <Area
              type="monotone"
              dataKey="weekday"
              stroke="var(--primary-deep)"
              strokeWidth={2}
              fill="url(#curveWeekday)"
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="weekend"
              stroke="var(--fg-subtle)"
              strokeWidth={1.5}
              strokeDasharray="3 4"
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="today"
              stroke="var(--fg)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ChartContainer>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t-[0.5px] border-border px-5 py-3 text-[11.5px] text-fg-muted">
        <span className="inline-flex items-center gap-1.5">
          <LegendDot className="size-2.5 rounded-[3px] bg-fg" /> Сегодня · пт 16 мая
        </span>
        <span className="inline-flex items-center gap-1.5">
          <LegendDot className="size-2.5 rounded-[3px] bg-primary-deep" /> Средняя по будням
        </span>
        <span className="inline-flex items-center gap-1.5">
          <LegendDot className="h-0 w-3 border-t-2 border-dashed border-fg-subtle" /> Средняя по
          выходным
        </span>
        <span className="ml-auto inline-flex items-center gap-1.5">
          <LegendDot className="h-0 w-3 border-t-2 border-dashed border-danger" /> capacity ={' '}
          {data.capacity} чел
        </span>
      </div>
    </Card>
  );
}
