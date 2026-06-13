import { cn } from '@/lib/cn';
import { Skeleton } from '@/components/ui/skeleton';
import { fillHourlyBuckets } from '@/features/reports/utils';
import type { VisitsReportData } from '@/features/reports/schemas';
import { DashboardCard } from './shared';

type HourState = 'past' | 'now' | 'future';

const BAR_STYLES: Record<HourState, string> = {
  past: 'bg-fg dark:bg-fg-muted',
  now: 'bg-primary',
  future: 'border-[0.5px] border-border',
};

const FUTURE_BG =
  'repeating-linear-gradient(45deg, var(--surface-3) 0 4px, var(--surface) 4px 8px)';

function getHourState(hour: number): HourState {
  const nowHour = new Date().getHours();
  if (hour < nowHour) return 'past';
  if (hour === nowHour) return 'now';
  return 'future';
}

interface OccupancyHoursProps {
  data: VisitsReportData | undefined;
  isPending: boolean;
}

export function OccupancyHours({ data, isPending }: OccupancyHoursProps) {
  // Zero-fill hourly buckets (hours 6–23, 18 slots)
  const rawHourly = data?.hourly ?? [];
  const filled = fillHourlyBuckets(rawHourly);
  // Show hours 6–22 (17 bars)
  const bars = filled.filter((b) => b.hour >= 6 && b.hour <= 22);
  const maxCount = Math.max(...bars.map((b) => b.count), 1);

  const peakBar = bars.reduce((m, b) => (b.count > m.count ? b : m), bars[0] ?? { hour: 0, count: 0 });

  return (
    <DashboardCard
      title="Заполняемость по часам"
      subtitle={data ? `Сегодня · средн. ${data.averagePerDay} посещений/день` : '—'}
    >
      {isPending ? (
        <div className="px-5 pb-5 pt-1">
          <Skeleton className="h-[220px] w-full rounded-xl" />
        </div>
      ) : (
        <div className="px-5 pb-5 pt-1">
          <div
            className="relative grid h-[220px] items-end gap-1.5 pt-6"
            style={{ gridTemplateColumns: 'repeat(17, minmax(0, 1fr))' }}
          >
            {/* Horizontal grid lines */}
            <div className="pointer-events-none absolute inset-x-0 bottom-[22px] top-6 flex flex-col justify-between">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className={cn(
                    'border-t border-dashed border-border',
                    i === 0 && 'border-t-0',
                    i === 4 && 'border-solid',
                  )}
                />
              ))}
            </div>

            {bars.map((bar) => {
              const state = getHourState(bar.hour);
              const heightPct = maxCount > 0 ? Math.round((bar.count / maxCount) * 100) : 0;
              return (
                <div
                  key={bar.hour}
                  className={cn('rounded-[6px_6px_2px_2px] transition-colors', BAR_STYLES[state])}
                  style={{
                    height: `${Math.max(heightPct, 2)}%`,
                    ...(state === 'future' ? { background: FUTURE_BG } : null),
                  }}
                  title={`${bar.hour}:00 · ${bar.count} посещений`}
                />
              );
            })}
          </div>

          {/* X axis */}
          <div
            className="mt-2 grid gap-1.5 text-center text-[10.5px] tabular-nums text-fg-subtle"
            style={{ gridTemplateColumns: 'repeat(17, minmax(0, 1fr))' }}
          >
            {bars.map((bar) => (
              <span
                key={bar.hour}
                className={cn(bar.hour === new Date().getHours() && 'font-bold text-primary-deep')}
              >
                {bar.hour}
              </span>
            ))}
          </div>

          {/* Legend */}
          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t-[0.5px] border-border pt-3.5 text-xs text-fg-muted">
            <span className="inline-flex items-center">
              <span className="mr-1.5 inline-block size-2.5 rounded-[3px] bg-fg align-[-1px]" />
              Факт
            </span>
            <span className="inline-flex items-center">
              <span className="mr-1.5 inline-block size-2.5 rounded-[3px] bg-primary align-[-1px]" />
              Сейчас
            </span>
            <span className="inline-flex items-center">
              <span
                className="mr-1.5 inline-block size-2.5 rounded-[3px] border-[0.5px] border-border align-[-1px]"
                style={{ background: FUTURE_BG }}
              />
              Прогноз
            </span>
            <span className="ml-auto text-fg-subtle">
              Пик в&nbsp;<b className="font-semibold text-fg">{peakBar.hour}:00</b>&nbsp;·{' '}
              {peakBar.count} посещений
            </span>
          </div>
        </div>
      )}
    </DashboardCard>
  );
}
