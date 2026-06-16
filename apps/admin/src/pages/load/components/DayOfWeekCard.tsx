/**
 * DayOfWeekCard — weekday bar list for the Load page (Phase 114 / ANL-01).
 *
 * Displays a 7-row horizontal bar list (Пн → Вс). Bar width is proportional
 * to total visits for each weekday. Peak weekday bar uses accent fill;
 * all others use chart-2. Zero bars render at 0% width (rows stay visible
 * to preserve weekday alignment).
 *
 * Data: derived client-side from VisitsReportDailyBucket[] via deriveDayOfWeek.
 * No network calls, no hooks.
 */
import { cn } from '@/lib/cn';
import { Card, CardHeader } from '@/components/layout/Card';
import type { VisitsReportDailyBucket } from '@/features/reports/schemas';
import { deriveDayOfWeek } from './derive';

export function DayOfWeekCard({ daily }: { daily: VisitsReportDailyBucket[] }) {
  const stats = deriveDayOfWeek(daily);
  const maxTotal = Math.max(...stats.map((s) => s.total), 0);

  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="По дням недели"
        subtitle="Суммарная посещаемость по дням за выбранный период"
      />
      <div className="px-5 pb-4">
        {stats.map((stat) => {
          const pct = maxTotal === 0 ? 0 : (stat.total / maxTotal) * 100;
          const isPeak = maxTotal > 0 && stat.total === maxTotal;
          return (
            <div key={stat.weekday} className="flex items-center gap-3 py-1.5">
              <span className="w-6 shrink-0 text-[11.5px] text-fg-muted">{stat.label}</span>
              <div className="flex-1 overflow-hidden rounded-full bg-surface-2 h-2">
                <div
                  style={{ width: `${pct}%` }}
                  className={cn(
                    'h-2 rounded-full transition-all',
                    isPeak ? 'bg-primary' : 'bg-chart-2',
                  )}
                />
              </div>
              <span className="w-8 shrink-0 text-right text-[11.5px] tabular-nums text-fg-muted">
                {stat.total}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
