import { Area, AreaChart, CartesianGrid, ReferenceLine, XAxis, YAxis } from 'recharts';
import { ChartContainer, ChartTooltip, type ChartConfig } from '@/components/ui/chart';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/feedback/EmptyState';
import { formatRub, formatDateRu } from '@/lib/format';
import { fillRevenueBuckets } from '@/features/reports/utils';
import type { RevenueReportData, RevenueBucket } from '@/features/reports/schemas';
import { DashboardCard } from './shared';

interface RevenueChartProps {
  data: RevenueReportData | undefined;
  fromDate: string;
  toDate: string;
  isPending: boolean;
}

const CHART_CONFIG: ChartConfig = {
  value: { label: 'Выручка', color: 'var(--primary-deep)' },
};

interface RevenuePoint {
  period: string;
  label: string;
  value: number;
}

function bucketToPoint(b: RevenueBucket): RevenuePoint {
  const v = Number.isFinite(b.netKopecks) ? Math.round(b.netKopecks / 100) : 0;
  return {
    period: b.period,
    label: formatDateRu(b.period, b.period.length === 7 ? 'MMM yyyy' : 'd MMM'),
    value: Math.max(v, 0), // treat negative net as 0 for chart display
  };
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
      <div className="tabular-nums">{formatRub(point.value)}</div>
    </div>
  );
}

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

export function RevenueChart({ data, fromDate, toDate, isPending }: RevenueChartProps) {
  const title = 'Выручка за 30 дней';
  const subtitle = `${formatDateRu(fromDate)} — ${formatDateRu(toDate)}`;

  if (isPending) {
    return (
      <DashboardCard title={title} subtitle="—">
        <div className="px-5 pb-5 pt-1">
          <Skeleton className="h-[220px] w-full rounded-xl" />
        </div>
      </DashboardCard>
    );
  }

  const filled = data
    ? fillRevenueBuckets(data.buckets, fromDate, toDate, 'day')
    : [];
  const points = filled.map(bucketToPoint);

  const totalKopecks = data
    ? data.buckets.reduce((s, b) => s + (Number.isFinite(b.netKopecks) ? b.netKopecks : 0), 0)
    : 0;
  const totalRub = Math.max(Math.round(totalKopecks / 100), 0);

  // Show empty state when no raw buckets (no transactions in period)
  const hasData = data != null && data.buckets.length > 0;
  if (!hasData) {
    return (
      <DashboardCard title={title} subtitle={subtitle}>
        <EmptyState
          className="py-10"
          title="Нет данных за период"
          message="Выберите другой период или подождите первых данных."
        />
      </DashboardCard>
    );
  }

  const lastIndex = points.length - 1;
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const avg = values.reduce((s, v) => s + v, 0) / values.length;
  const pad = (max - min) * 0.12 || max * 0.1 || 100;

  // Show every 5th tick so the axis isn't crowded over 30 days
  const ticksEvery = Math.max(Math.floor(points.length / 6), 1);

  return (
    <DashboardCard title={title} subtitle={subtitle}>
      <div className="flex flex-1 flex-col">
        <div className="px-5 pt-1">
          <div className="text-[28px] font-bold tracking-[-0.6px] tabular-nums">
            {formatRub(totalRub)}
          </div>
          <div className="mt-1 text-[12.5px] text-fg-muted">Итого за период</div>
        </div>

        <ChartContainer config={CHART_CONFIG} className="aspect-auto h-[170px] w-full px-2">
          <AreaChart data={points} margin={{ top: 10, right: 8, left: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.32} />
                <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.55} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              interval={ticksEvery - 1}
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
      </div>
    </DashboardCard>
  );
}
