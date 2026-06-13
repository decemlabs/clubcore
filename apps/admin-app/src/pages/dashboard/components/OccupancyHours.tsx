import { useState } from 'react';
import { cn } from '@/lib/cn';
import { DashboardCard, MiniSegmented, type MiniSegmentedOption } from './shared';
import type { HourState, HourlyOccupancy } from '@/features/dashboard/types';

const RANGE_OPTIONS: MiniSegmentedOption<string>[] = [
  { value: 'today', label: 'Сегодня' },
  { value: 'wed', label: 'Ср ср' },
  { value: '7d', label: '7 дней' },
];

/** Полосатый паттерн «прогноз» — повторяет заливку из референса. */
const FUTURE_BG =
  'repeating-linear-gradient(45deg, var(--surface-3) 0 4px, var(--surface) 4px 8px)';

const BAR_STYLES: Record<HourState, string> = {
  past: 'bg-fg dark:bg-fg-muted',
  now: 'bg-primary',
  future: 'border-[0.5px] border-border',
};

export function OccupancyHours({ data }: { data: HourlyOccupancy }) {
  const [range, setRange] = useState('today');

  return (
    <DashboardCard
      title="Заполняемость по часам"
      subtitle={data.subtitle}
      action={
        <MiniSegmented
          options={RANGE_OPTIONS}
          value={range}
          onChange={setRange}
          ariaLabel="Период заполняемости"
        />
      }
    >
      <div className="px-5 pb-5 pt-1">
        {/* Столбцы по часам */}
        <div
          className="relative grid h-[220px] items-end gap-1.5 pt-6"
          style={{ gridTemplateColumns: 'repeat(17, minmax(0, 1fr))' }}
        >
          {/* Сетка горизонтальных линий */}
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

          {data.bars.map((bar) => (
            <div
              key={bar.hour}
              className={cn('rounded-[6px_6px_2px_2px] transition-colors', BAR_STYLES[bar.state])}
              style={{
                height: `${bar.value}%`,
                ...(bar.state === 'future' ? { background: FUTURE_BG } : null),
              }}
              title={`${bar.hour}:00 · ${bar.value}%`}
            />
          ))}
        </div>

        {/* Ось X */}
        <div
          className="mt-2 grid gap-1.5 text-center text-[10.5px] tabular-nums text-fg-subtle"
          style={{ gridTemplateColumns: 'repeat(17, minmax(0, 1fr))' }}
        >
          {data.bars.map((bar) => (
            <span key={bar.hour} className={cn(bar.hour === 16 && 'font-bold text-primary-deep')}>
              {bar.hour}
            </span>
          ))}
        </div>

        {/* Легенда */}
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
            Пик в&nbsp;<b className="font-semibold text-fg">{data.peakHour}</b>&nbsp;·{' '}
            {data.peakCount} чел
          </span>
        </div>
      </div>
    </DashboardCard>
  );
}
