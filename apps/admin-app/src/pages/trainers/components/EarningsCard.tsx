import { useState } from 'react';
import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import { Card, CardHeader } from '@/components/layout/Card';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { formatRub } from '@/lib/format';
import type { EarningsData } from '@/features/trainers/types';
import { EmptyState } from '@/components/feedback/EmptyState';

type Unit = 'rub' | 'count';

const UNIT_OPTIONS: SegmentedOption<Unit>[] = [
  { value: 'rub', label: '₽' },
  { value: 'count', label: 'Шт.' },
];

const BAR: Record<'accent' | 'normal' | 'low', string> = {
  accent: 'bg-primary',
  normal: 'bg-fg',
  low: 'bg-fg-subtle',
};

/** Выручка по тренерам: список с полосами + переключатель ₽ / Шт. + итог. */
export function EarningsCard({ data }: { data: EarningsData }) {
  const [unit, setUnit] = useState<Unit>('rub');

  if (data.rows.length === 0) {
    return (
      <Card as="section" className="flex min-w-0 flex-col">
        <CardHeader
          title="Выручка с тренеров · апрель"
          subtitle="Сколько каждый тренер принёс через ПТ. Сортировка по сумме."
          action={
            <Segmented
              variant="mini"
              options={UNIT_OPTIONS}
              value={unit}
              onChange={setUnit}
              ariaLabel="Единицы"
            />
          }
        />
        <EmptyState className="py-10" title="Нет данных" />
      </Card>
    );
  }

  const maxRev = Math.max(...data.rows.map((r) => r.revenue));
  const maxPt = Math.max(...data.rows.map((r) => r.ptCount));
  const safeMaxRev = maxRev > 0 ? maxRev : 1;
  const safeMaxPt = maxPt > 0 ? maxPt : 1;

  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Выручка с тренеров · апрель"
        subtitle="Сколько каждый тренер принёс через ПТ. Сортировка по сумме."
        action={
          <Segmented
            variant="mini"
            options={UNIT_OPTIONS}
            value={unit}
            onChange={setUnit}
            ariaLabel="Единицы"
          />
        }
      />

      <div className="@container">
        {data.rows.map((r, i) => {
          const barPct =
            unit === 'rub' ? (r.revenue / safeMaxRev) * 100 : (r.ptCount / safeMaxPt) * 100;
          const tone: keyof typeof BAR =
            r.revenue === maxRev ? 'accent' : r.share < 10 ? 'low' : 'normal';
          return (
            <div
              key={r.trainerId}
              className={cn(
                'grid grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3 px-5 py-2.5',
                i > 0 && 'border-t-[0.5px] border-border',
              )}
            >
              <Initials initials={r.initials} color={r.color} className="size-9 text-[11px]" />
              <div className="min-w-0">
                <div className="truncate text-[13.5px] font-semibold tracking-[-0.1px]">
                  {r.name}
                </div>
                <div className="mt-px truncate text-[11px] text-fg-subtle">{r.meta}</div>
                <div className="mt-1.5 h-[5px] overflow-hidden rounded-full bg-surface-3">
                  <div
                    className={cn('h-full rounded-full', BAR[tone])}
                    style={{ width: `${barPct}%` }}
                  />
                </div>
              </div>
              <div className="text-right">
                <div className="text-[14px] font-bold tabular-nums">
                  {unit === 'rub' ? (
                    formatRub(r.revenue)
                  ) : (
                    <>
                      {r.ptCount}
                      <small className="ml-0.5 font-semibold text-fg-subtle">ПТ</small>
                    </>
                  )}
                </div>
                <div className="mt-0.5 text-[11.5px] tabular-nums text-fg-subtle @max-[360px]:hidden">
                  {r.share}%
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t-[0.5px] border-border px-5 py-3 text-[12px] text-fg-muted">
        <span>
          <b className="font-bold tabular-nums text-fg">{formatRub(data.total)}</b> ·{' '}
          {data.totalLabel}
        </span>
        <span className="text-fg-subtle">{data.payoutNote}</span>
      </div>
    </Card>
  );
}
