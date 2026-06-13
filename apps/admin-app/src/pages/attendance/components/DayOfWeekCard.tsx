import { cn } from '@/lib/cn';
import { Card, CardHeader, CardLink } from '@/components/layout/Card';
import { ROUTES } from '@/app/routes';
import type { DowBar } from '@/features/attendance/types';

export function DayOfWeekCard({ bars }: { bars: DowBar[] }) {
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="День недели · среднее"
        subtitle="Визитов в день · май 2026"
        action={<CardLink to={ROUTES.schedule}>Расписание</CardLink>}
      />
      <div className="px-5 pb-2 pt-6">
        <div className="flex h-[180px] items-end gap-2">
          {bars.map((b) => (
            <div
              key={b.day}
              className={cn(
                'relative w-full flex-1 overflow-hidden rounded-t-[6px]',
                b.peak ? 'bg-fg' : b.now ? 'bg-surface-3' : 'bg-fg-subtle/60',
              )}
              style={{ height: `${b.pct}%` }}
            >
              {b.now && b.nowPct != null ? (
                <div
                  className="absolute inset-x-0 bottom-0 bg-primary"
                  style={{ height: `${b.nowPct}%` }}
                />
              ) : null}
              <span
                className={cn(
                  'absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-[11px] font-semibold tabular-nums',
                  b.now ? 'text-primary-deep dark:text-primary' : 'text-fg',
                )}
              >
                {b.value}
                {b.now ? <small className="font-medium text-fg-subtle"> пока</small> : null}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-2 flex gap-2">
          {bars.map((b) => (
            <div key={b.day} className="flex-1 text-center">
              <div
                className={cn(
                  'text-[11px] font-semibold',
                  b.now && 'text-primary-deep dark:text-primary',
                )}
              >
                {b.day}
              </div>
              <div className="text-[10px] text-fg-subtle">{b.note}</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
