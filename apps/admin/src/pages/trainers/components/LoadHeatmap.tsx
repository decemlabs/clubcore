import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import { Card } from '@/components/layout/Card';
import type { HeatCell, HeatLevel, HeatmapData } from '@/features/trainers/types';

/** Фон ячейки по уровню занятости (изумрудная шкала поверх surface-3). */
const CELL_BG: Record<HeatLevel, string> = {
  1: 'bg-[color-mix(in_oklab,var(--primary)_20%,var(--surface-3))] text-fg',
  2: 'bg-[color-mix(in_oklab,var(--primary)_45%,var(--surface-3))] text-fg',
  3: 'bg-[color-mix(in_oklab,var(--primary)_72%,var(--surface-3))] text-[#06120c]',
  4: 'bg-primary text-[#06120c]',
};

/** Свотчи легенды: серый → насыщенный изумруд. */
const SCALE_BG = [
  'bg-surface-3',
  'bg-[color-mix(in_oklab,var(--primary)_20%,var(--surface-3))]',
  'bg-[color-mix(in_oklab,var(--primary)_45%,var(--surface-3))]',
  'bg-[color-mix(in_oklab,var(--primary)_72%,var(--surface-3))]',
  'bg-primary',
];

const GRID_COLS = 'grid grid-cols-[140px_repeat(7,minmax(0,1fr))]';

function HeatTile({ cell, today }: { cell: HeatCell; today?: boolean }) {
  const occupied = cell.hours != null && cell.level != null;
  return (
    <div
      className={cn(
        'grid h-8 place-items-center rounded-[6px] text-[11px] font-bold tabular-nums transition-transform hover:scale-105',
        occupied ? CELL_BG[cell.level as HeatLevel] : 'text-fg-subtle',
        today && 'ring-[1.5px] ring-inset ring-fg dark:ring-primary',
      )}
    >
      {occupied ? `${cell.hours}ч` : cell.offLabel}
    </div>
  );
}

/** Тепловая карта недельной загрузки: тренеры × дни недели + легенда. */
export function LoadHeatmap({ data }: { data: HeatmapData }) {
  return (
    <Card as="section">
      <div className="overflow-x-auto [scrollbar-width:thin]">
        <div className="min-w-[680px]">
          <div className={cn(GRID_COLS, 'border-b-[0.5px] border-border')}>
            <div className="px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.4px] text-fg-subtle">
              Тренер
            </div>
            {data.days.map((d) => (
              <div key={d.weekday} className="px-1 py-3 text-center">
                <div className={cn('text-[12px] font-semibold', d.today && 'text-fg')}>
                  {d.weekday}
                </div>
                <div
                  className={cn(
                    'text-[11px] tabular-nums',
                    d.today
                      ? 'font-semibold text-primary-deep dark:text-primary'
                      : 'text-fg-subtle',
                  )}
                >
                  {d.date}
                </div>
              </div>
            ))}
          </div>

          {data.rows.map((r, ri) => (
            <div
              key={r.trainerId}
              className={cn(GRID_COLS, ri > 0 && 'border-t-[0.5px] border-border')}
            >
              <div className="flex min-w-0 items-center gap-2.5 px-5 py-2.5">
                <Initials
                  initials={r.initials}
                  color={r.color}
                  className="size-[26px] text-[10px]"
                />
                <div className="min-w-0">
                  <div className="truncate text-[12.5px] font-semibold">{r.name}</div>
                  <div className="truncate text-[11px] tabular-nums text-fg-subtle">
                    {r.totalLabel}
                  </div>
                </div>
              </div>
              {r.cells.map((c, ci) => (
                <div key={`${r.trainerId}-${ci}`} className="p-1.5">
                  <HeatTile cell={c} today={data.days[ci]?.today} />
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t-[0.5px] border-border px-5 py-3 text-[11.5px] text-fg-muted">
        <div className="flex items-center gap-2">
          <span className="flex gap-0.5">
            {SCALE_BG.map((bg, i) => (
              <span
                key={i}
                className={cn('size-3 rounded-[3px] border-[0.5px] border-border', bg)}
              />
            ))}
          </span>
          <span>{data.scaleLabel}</span>
        </div>
        <div className="ml-auto tabular-nums">
          Свободных слотов на этой неделе —{' '}
          <b className="font-semibold text-fg">{data.freeSlots}</b> · средняя загрузка{' '}
          <b className="font-semibold text-fg">{data.avgLoadPct}%</b>
        </div>
      </div>
    </Card>
  );
}
