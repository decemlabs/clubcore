/**
 * LoadHeatmapCard — visits aggregate heatmap + trend (Phase 103-03).
 *
 * Receives zero-filled hourly (24 pts) + daily (full range) data from useLoad.
 * Never receives NaN — zero-fill is guaranteed by features/load/api.ts.
 *
 * Hourly data (24 pts, 0–23): displayed as an IntensityHeatmap single-row
 * showing hour distribution. Count 0 → level 0 (lightest shade).
 *
 * Daily data: displayed as an AreaTrendChart trend line.
 *
 * Level mapping: count → 0..6 via quantile of the hourly max.
 * All-zero case is handled upstream (LoadPage shows EmptyState instead).
 */
import { cn } from '@/lib/cn';
import { Card, CardHeader } from '@/components/layout/Card';
import { IntensityHeatmap } from '@/components/charts/IntensityHeatmap';
import { AreaTrendChart } from '@/components/charts/AreaTrendChart';
import { cellClass } from '@/components/charts/heatmap-utils';
import type { HeatRowData } from '@/components/charts/heatmap-utils';
import type { VisitsReportHourlyBucket, VisitsReportDailyBucket } from '@/features/reports/schemas';

/** Map visit count to heatmap level 0–6 based on the observed max count. */
function countToLevel(count: number, max: number): 0 | 1 | 2 | 3 | 4 | 5 | 6 {
  if (max === 0 || count === 0) return 0;
  const ratio = count / max;
  if (ratio <= 0) return 0;
  if (ratio <= 0.15) return 1;
  if (ratio <= 0.30) return 2;
  if (ratio <= 0.45) return 3;
  if (ratio <= 0.65) return 4;
  if (ratio <= 0.85) return 5;
  return 6;
}

const SCALE: (0 | 1 | 2 | 3 | 5 | 6)[] = [0, 1, 2, 3, 5, 6];

export function LoadHeatmapCard({
  hourly,
  daily,
}: {
  hourly: VisitsReportHourlyBucket[];
  daily: VisitsReportDailyBucket[];
}) {
  // Hourly heatmap: single row representing the 24-hour distribution.
  const maxCount = Math.max(...hourly.map((b) => b.count), 0);
  const heatRow: HeatRowData = {
    label: 'Часы',
    cells: hourly.map((b) => ({
      level: countToLevel(b.count, maxCount),
      title: `${b.hour}:00 — ${b.count} визитов`,
      text: b.count > 0 ? String(b.count) : '',
    })),
  };
  const hourLabels = hourly.map((b) => `${b.hour}`);

  // Daily trend: map to TrendPoint[]
  const dailyTrend = daily.map((b) => ({
    label: b.date.slice(5), // 'MM-DD'
    value: b.count,
  }));

  // Show every 7th label to avoid X-axis crowding
  const ticks = dailyTrend
    .filter((_, i) => i % 7 === 0)
    .map((p) => p.label);

  return (
    <div className="flex flex-col gap-4">
      {/* Hourly heatmap */}
      <Card as="section" className="flex min-w-0 flex-col">
        <CardHeader
          title="Загруженность по часам"
          subtitle="Распределение визитов по часу дня за выбранный период"
        />
        <div className="px-5 pb-3">
          <IntensityHeatmap hours={hourLabels} rows={[heatRow]} />
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t-[0.5px] border-border px-5 py-3 text-[11.5px] text-fg-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="flex gap-0.5">
              {SCALE.map((l) => (
                <span key={l} className={cn('h-3 w-4 rounded-[3px]', cellClass(l))} />
              ))}
            </span>
            от 0 до максимума
          </span>
        </div>
      </Card>

      {/* Daily trend */}
      <Card as="section" className="flex min-w-0 flex-col">
        <CardHeader
          title="Динамика по дням"
          subtitle="Количество визитов в день за выбранный период"
        />
        <div className="px-5 pb-4">
          <AreaTrendChart
            data={dailyTrend}
            height={220}
            yMax={Math.max(...daily.map((b) => b.count), 0)}
            ticks={ticks}
          />
        </div>
      </Card>
    </div>
  );
}
