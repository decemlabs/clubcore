import { useState } from 'react';
import { cn } from '@/lib/cn';
import { Card, CardHeader } from '@/components/layout/Card';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { ChevronRight } from '@/components/icons';
import { cellClass, type HeatLevel } from '@/components/charts/heatmap-utils';
import type { CohortData } from '@/features/attendance/types';

type Scope = 'all' | 'nopt' | 'pt';
const SCOPES: SegmentedOption<Scope>[] = [
  { value: 'all', label: 'Все типы' },
  { value: 'nopt', label: 'Без ПТ' },
  { value: 'pt', label: 'С ПТ' },
];

const GRID = { gridTemplateColumns: '110px 44px repeat(8, minmax(0, 1fr))' };

function level(v: number): HeatLevel {
  if (v >= 90) return 6;
  if (v >= 80) return 5;
  if (v >= 65) return 4;
  if (v >= 50) return 3;
  if (v >= 40) return 2;
  return 1;
}
function textClass(l: HeatLevel): string {
  if (l === 6) return 'text-white';
  if (l === 5) return 'text-[#06120c]';
  return 'text-fg';
}

export function CohortCard({ data }: { data: CohortData }) {
  const [scope, setScope] = useState<Scope>('nopt');
  return (
    <Card as="section" className="flex flex-col">
      <CardHeader
        title="Удержание по когортам"
        subtitle="% клиентов, пришедших хотя бы раз на N-й неделе после первой покупки абонемента"
        action={
          <Segmented
            variant="mini"
            options={SCOPES}
            value={scope}
            onChange={setScope}
            ariaLabel="Тип когорты"
          />
        }
      />
      <div className="overflow-x-auto px-5 pb-3 [scrollbar-width:thin]">
        <div className="min-w-[680px]">
          <div className="grid gap-1 pb-1" style={GRID}>
            <span className="text-[10.5px] font-semibold uppercase tracking-[0.3px] text-fg-subtle">
              Когорта
            </span>
            <span className="text-right text-[10.5px] font-semibold uppercase tracking-[0.3px] text-fg-subtle">
              Чел
            </span>
            {data.weeks.map((w) => (
              <span key={w} className="text-center text-[10px] text-fg-subtle">
                {w}
              </span>
            ))}
          </div>
          {data.rows.map((r) => (
            <div key={r.label} className="grid items-center gap-1 py-0.5" style={GRID}>
              <span className="text-[11.5px] font-semibold">{r.label}</span>
              <span className="text-right text-[11px] tabular-nums text-fg-subtle">{r.size}</span>
              {r.values.map((v, i) =>
                v == null ? (
                  <span key={i} className="grid h-7 place-items-center text-[11px] text-fg-subtle">
                    —
                  </span>
                ) : (
                  <div
                    key={i}
                    className={cn(
                      'grid h-7 place-items-center rounded-[5px] text-[11px] font-semibold tabular-nums',
                      cellClass(level(v)),
                      textClass(level(v)),
                    )}
                  >
                    {v}
                  </div>
                ),
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t-[0.5px] border-border px-5 py-3 text-[12px] text-fg-muted">
        <span>
          {data.footPre}
          <b className="font-semibold text-fg">{data.footAvg}</b>
          {data.footMid}
          <b className="font-semibold text-primary-deep dark:text-primary">{data.footGoal}</b>
          {data.footPost}
        </span>
        <button
          type="button"
          className="inline-flex items-center gap-0.5 rounded font-semibold text-fg-muted transition-colors hover:text-fg"
        >
          Сравнить с «Парк»
          <ChevronRight className="size-3" strokeWidth={2.4} />
        </button>
      </div>
    </Card>
  );
}
