/**
 * RevenueChart — zero-filled revenue trend chart (Phase 103-04).
 *
 * Props: sparse RevenueBucket[] + date range + groupBy.
 * Zero-fills via fillRevenueBuckets before mapping to AreaTrendChart.
 * Chart Y-axis value = netKopecks/100 (rubles, for readability).
 * Tooltip: formatRub(netKopecks/100) — signed, negative renders correctly.
 *
 * All-zero check is caller's responsibility (FinancePage shows EmptyState instead).
 */
import { Card, CardHeader } from '@/components/layout/Card';
import { AreaTrendChart } from '@/components/charts/AreaTrendChart';
import { fillRevenueBuckets } from '@/features/reports/utils';
import { formatRub } from '@/lib/format';
import type { RevenueBucket } from '@/features/reports/schemas';

export interface RevenueChartProps {
  buckets: RevenueBucket[];
  fromDate: string;
  toDate: string;
  groupBy: 'day' | 'month';
}

export function RevenueChart({ buckets, fromDate, toDate, groupBy }: RevenueChartProps) {
  const filled = fillRevenueBuckets(buckets, fromDate, toDate, groupBy);

  const data = filled.map((b) => ({
    label: b.period,
    value: b.netKopecks / 100, // rubles for Y-axis readability
  }));

  // Subset ticks: show every Nth label to avoid overcrowding
  const tickInterval = Math.max(1, Math.floor(data.length / 8));
  const ticks = data
    .filter((_, i) => i % tickInterval === 0 || i === data.length - 1)
    .map((d) => d.label);

  return (
    <Card as="section" className="flex flex-col">
      <CardHeader
        title="Выручка"
        subtitle={`${groupBy === 'day' ? 'По дням' : 'По месяцам'} · нетто с учётом возвратов`}
      />
      <div className="px-4 pb-4">
        <AreaTrendChart
          data={data}
          ticks={ticks}
          height={260}
          yMax={Math.max(...filled.map((b) => b.netKopecks / 100), 0) || undefined}
          renderTooltip={(point) => (
            <div className="rounded-lg border-[0.5px] border-border bg-surface px-3 py-2 shadow-2">
              <div className="mb-1 text-[11.5px] text-fg-subtle">{point.label}</div>
              <div
                className={`text-[14px] font-bold tabular-nums ${point.value < 0 ? 'text-danger' : 'text-fg'}`}
              >
                {point.value < 0 ? '−' : '+'}
                {formatRub(Math.abs(point.value))}
              </div>
            </div>
          )}
          className="w-full"
        />
      </div>
    </Card>
  );
}
