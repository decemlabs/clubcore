import { cn } from '@/lib/cn';
import { Card } from '@/components/layout/Card';
import type { SalesChart as SalesChartData, SalesSegKey } from '@/features/plans/types';
import type { SalesUnit } from './sales-unit';
import { EmptyState } from '@/components/feedback/EmptyState';

const SEG_BG: Record<SalesSegKey, string> = {
  annual: 'bg-fg',
  half: 'bg-primary',
  month: 'bg-fg-subtle',
};

/** Стек-бары продаж по тарифам за 6 месяцев + легенда (Шт./₽ — снаружи). */
export function SalesChart({ data, unit }: { data: SalesChartData; unit: SalesUnit }) {
  if (data.months.length === 0) {
    return (
      <Card>
        <EmptyState className="py-14" title="Нет данных" />
      </Card>
    );
  }

  const values = data.months.map((m) => (unit === 'count' ? m.count : m.revenueK));
  const max = Math.max(...values);
  const safeMax = max > 0 ? max : 1;

  return (
    <Card>
      <div className="px-5 pt-5">
        <div className="grid h-[200px] grid-cols-6 items-end gap-4 border-b-[0.5px] border-border pb-3">
          {data.months.map((m, i) => {
            const h = (values[i]! / safeMax) * 92;
            return (
              <div key={m.label} className="flex h-full flex-col items-center justify-end gap-1.5">
                <span
                  className={cn(
                    'text-[11px] font-semibold tabular-nums',
                    m.current ? 'text-fg' : 'text-fg-subtle',
                  )}
                >
                  {unit === 'count' ? m.count : `${m.revenueK}К`}
                </span>
                <div
                  className="flex w-full max-w-[56px] flex-col overflow-hidden rounded-lg"
                  style={{ height: `${h}%` }}
                >
                  <div className={SEG_BG.annual} style={{ flexBasis: `${m.seg.annual * 100}%` }} />
                  <div className={SEG_BG.half} style={{ flexBasis: `${m.seg.half * 100}%` }} />
                  <div className={SEG_BG.month} style={{ flexBasis: `${m.seg.month * 100}%` }} />
                </div>
              </div>
            );
          })}
        </div>
        <div className="grid grid-cols-6 gap-4 pt-2 text-center">
          {data.months.map((m) => (
            <span
              key={m.label}
              className={cn('text-[11px] tabular-nums', m.current ? 'font-bold text-fg' : 'text-fg-subtle')}
            >
              {m.label}
            </span>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t-[0.5px] border-border px-5 py-3 text-[12px] text-fg-muted">
        {data.legend.map((l) => (
          <span key={l.key} className="inline-flex items-center gap-1.5">
            <span className={cn('size-2.5 rounded-[3px]', SEG_BG[l.key])} />
            {l.label} · <b className="font-semibold tabular-nums text-fg">{l.value}</b>
          </span>
        ))}
        <span className="ml-auto">
          Конверсия из новых лидов — <b className="font-semibold text-fg">{data.conversion}</b>
        </span>
      </div>
    </Card>
  );
}
