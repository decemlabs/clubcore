import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { StatStrip } from '@/components/layout/StatStrip';
import { Activity, ChevronUp, Info, TrendingUp } from '@/components/icons';
import type { DeltaTone, LoadKpi, LoadKpiIcon, MeterTone } from '@/features/load/types';

const ICONS: Record<LoadKpiIcon, LucideIcon> = {
  now: Activity,
  avg: TrendingUp,
  peak: TrendingUp,
  free: Info,
};
const METER: Record<MeterTone, string> = {
  accent: 'bg-primary',
  warn: 'bg-warning',
  neutral: 'bg-fg-subtle',
};
const DELTA: Record<DeltaTone, string> = {
  accent: 'bg-primary-soft text-primary-deep dark:text-primary',
  warn: 'bg-warning-soft text-warning-deep',
  flat: 'bg-surface-3 text-fg-muted',
};

function Tile({ k }: { k: LoadKpi }) {
  const Icon = ICONS[k.icon];
  return (
    <div className="flex flex-col rounded-lg border-[0.5px] border-border bg-surface px-5 pb-4 pt-[18px] shadow-1 transition-shadow hover:shadow-2">
      <div className="flex items-center gap-2 text-[12.5px] font-medium text-fg-muted">
        <span className="grid size-[26px] shrink-0 place-items-center rounded-[8px] bg-surface-3 text-fg">
          <Icon className="size-[14px]" strokeWidth={2} />
        </span>
        <span className="truncate">{k.label}</span>
      </div>
      <div className="mt-2.5 text-[30px] font-bold leading-[1.05] tracking-[-0.8px] tabular-nums">
        {k.value}
        {k.unit ? <span className="text-[16px] font-semibold text-fg-muted">{k.unit}</span> : null}
      </div>
      <div className="mt-2.5 h-[5px] overflow-hidden rounded-full bg-surface-3">
        <div
          className={cn('h-full rounded-full', METER[k.meterTone])}
          style={{ width: `${k.meterPct}%` }}
        />
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-2 text-[12.5px] text-fg-muted">
        <span
          className={cn(
            'inline-flex items-center gap-[3px] rounded-full px-[7px] py-0.5 text-xs font-semibold',
            DELTA[k.delta.tone],
          )}
        >
          {k.delta.up ? <ChevronUp className="size-2.5" strokeWidth={3} /> : null}
          {k.delta.label}
        </span>
        <span>{k.caption}</span>
      </div>
    </div>
  );
}

export function LoadKpis({ kpis }: { kpis: LoadKpi[] }) {
  return (
    <StatStrip className="grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((k) => (
        <Tile key={k.id} k={k} />
      ))}
    </StatStrip>
  );
}
