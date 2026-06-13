import { useState } from 'react';
import { Area, AreaChart, CartesianGrid, ReferenceLine, XAxis, YAxis } from 'recharts';
import { ChartContainer, ChartTooltip, type ChartConfig } from '@/components/ui/chart';
import { formatInt } from '@/lib/format';
import { ChevronUp } from '@/components/icons';
import type { RevenueData, RevenuePeriod, RevenuePoint } from '@/features/dashboard/types';
import { DashboardCard, MiniSegmented, type MiniSegmentedOption } from './shared';
import { EmptyState } from '@/components/feedback/EmptyState';

const PERIOD_OPTIONS: MiniSegmentedOption<RevenuePeriod>[] = [
  { value: '30', label: '30д' },
  { value: '90', label: '90д' },
  { value: 'year', label: 'Год' },
];

const CHART_CONFIG: ChartConfig = {
  value: { label: 'Выручка', color: 'var(--primary-deep)' },
};

/** Постоянная точка в конце линии (на последней позиции серии). */
function EndDot(props: { cx?: number; cy?: number; index?: number; lastIndex?: number }) {
  const { cx, cy, index, lastIndex } = props;
  if (cx == null || cy == null || index !== lastIndex) return <g />;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={3.5}
      fill="var(--surface)"
      stroke="var(--primary-deep)"
      strokeWidth={2}
    />
  );
}

function RevenueTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: RevenuePoint }[];
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;
  return (
    <div className="rounded-lg bg-fg px-2.5 py-1.5 text-[11.5px] font-semibold leading-tight text-bg shadow-lg dark:border-[0.5px] dark:border-border-strong dark:bg-surface dark:text-fg">
      <div className="text-[10px] font-medium uppercase tracking-[0.3px] opacity-70">
        {point.label}
      </div>
      <div className="tabular-nums">{formatInt(Math.round(point.value))} ₽</div>
    </div>
  );
}

export function RevenueChart({ data }: { data: RevenueData }) {
  const [period, setPeriod] = useState<RevenuePeriod>(data.defaultPeriod);
  const series = data.series[period];
  const points = series.points;

  if (points.length === 0) {
    return (
      <DashboardCard
        title={series.title}
        subtitle={series.rangeLabel}
        action={
          <MiniSegmented
            options={PERIOD_OPTIONS}
            value={period}
            onChange={setPeriod}
            ariaLabel="Период выручки"
          />
        }
        className="md:col-span-2 xl:col-span-1"
      >
        <EmptyState
          className="py-10"
          title="Нет данных за период"
          message="Выберите другой период."
        />
      </DashboardCard>
    );
  }

  const lastIndex = points.length - 1;

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const avg = values.reduce((s, v) => s + v, 0) / values.length;
  const pad = (max - min) * 0.12 || max * 0.1;

  return (
    <DashboardCard
      title={series.title}
      subtitle={series.rangeLabel}
      action={
        <MiniSegmented
          options={PERIOD_OPTIONS}
          value={period}
          onChange={setPeriod}
          ariaLabel="Период выручки"
        />
      }
      className="md:col-span-2 xl:col-span-1"
    >
      <div className="flex flex-1 flex-col">
        {/* Шапка чисел */}
        <div className="px-5 pt-1">
          <div className="text-[28px] font-bold tracking-[-0.6px] tabular-nums">
            {formatInt(series.total)}&nbsp;₽
          </div>
          <div className="mt-1 flex items-center gap-2 text-[12.5px] text-fg-muted">
            <span className="inline-flex items-center gap-[3px] rounded-full bg-primary-soft px-[7px] py-0.5 text-xs font-semibold text-primary-deep">
              <ChevronUp className="size-2.5" strokeWidth={3} />
              {series.delta.label}
            </span>
            <span>{series.deltaSub}</span>
          </div>
        </div>

        {/* График */}
        <ChartContainer config={CHART_CONFIG} className="aspect-auto h-[170px] w-full px-2">
          <AreaChart data={points} margin={{ top: 10, right: 8, left: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2dd4a4" stopOpacity={0.32} />
                <stop offset="100%" stopColor="#2dd4a4" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.55} />
            <XAxis
              dataKey="short"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              interval={series.ticksEvery - 1}
              tick={{ fontSize: 10 }}
            />
            <YAxis hide domain={[Math.max(0, min - pad), max + pad]} />
            <ReferenceLine
              y={avg}
              stroke="var(--fg-subtle)"
              strokeDasharray="3 4"
              strokeOpacity={0.55}
            />
            <ChartTooltip
              content={<RevenueTooltip />}
              cursor={{ stroke: 'var(--primary-deep)', strokeDasharray: '2 3', strokeOpacity: 0.5 }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="var(--primary-deep)"
              strokeWidth={2}
              fill="url(#revGrad)"
              dot={<EndDot lastIndex={lastIndex} />}
              activeDot={{
                r: 4,
                fill: 'var(--surface)',
                stroke: 'var(--primary-deep)',
                strokeWidth: 2,
              }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ChartContainer>

        {/* Разбивка */}
        <div className="@container border-t-[0.5px] border-border px-5 pb-[18px] pt-3.5">
          <div className="grid grid-cols-3 gap-3 @max-[400px]:grid-cols-1">
            {series.breakdown.map((cell) => (
              <div
                key={cell.label}
                className="min-w-0 @max-[400px]:flex @max-[400px]:items-baseline @max-[400px]:justify-between @max-[400px]:gap-3"
              >
                <div className="flex items-center gap-1.5 text-[11.5px] text-fg-subtle">
                  <span
                    className="size-2 shrink-0 rounded-[2px]"
                    style={{ background: cell.color }}
                  />
                  {cell.label}
                </div>
                <div className="mt-1 whitespace-nowrap text-base font-bold tracking-[-0.3px] tabular-nums @max-[400px]:mt-0 @max-[400px]:text-[14.5px]">
                  {formatInt(cell.value)}&nbsp;₽
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardCard>
  );
}
