import { Card, CardHeader } from '@/components/layout/Card';
import { DonutChart } from '@/components/charts/DonutChart';
import type { MixData } from '@/features/reports/types';

export function RevenueMixCard({ data }: { data: MixData }) {
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader title="Структура выручки" subtitle="по категориям, апрель" />

      <div className="flex flex-col items-center gap-5 px-5 pb-2 pt-1 sm:flex-row">
        <DonutChart
          segments={data.segments}
          center={
            <div>
              <div className="text-[22px] font-bold tabular-nums">
                {data.center.top}
                <small className="text-[11px] font-semibold text-fg-muted">
                  {' '}
                  {data.center.sub}
                </small>
              </div>
              <div className="text-[10.5px] text-fg-subtle">{data.center.label}</div>
            </div>
          }
        />
        <div className="min-w-0 flex-1 self-stretch">
          {data.segments.map((s) => (
            <div
              key={s.label}
              className="grid grid-cols-[10px_minmax(0,1fr)_auto_auto] items-center gap-2.5 py-2 text-[12.5px]"
            >
              <span className="size-2.5 rounded-[3px]" style={{ background: s.color }} />
              <span className="truncate text-fg-muted">{s.label}</span>
              <span className="text-right text-fg-subtle tabular-nums">{s.pct}</span>
              <span className="text-right font-bold tabular-nums">{s.amount}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t-[0.5px] border-border px-5 py-3 text-[12px] text-fg-muted">
        <span className="inline-flex items-center gap-1.5">
          Самый растущий — <b className="font-semibold text-fg">{data.growingLabel}</b>
          <span className="rounded-full bg-primary-soft px-[7px] py-0.5 text-[11px] font-semibold text-primary-deep dark:text-primary">
            {data.growingDelta}
          </span>
        </span>
        <span>
          из них наличные <b className="font-semibold text-fg">{data.cashPct}</b>
        </span>
      </div>
    </Card>
  );
}
