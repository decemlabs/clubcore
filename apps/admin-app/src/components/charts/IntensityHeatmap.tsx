import { cn } from '@/lib/cn';
import { cellClass, type HeatRowData } from './heatmap-utils';

/**
 * Тепловая карта интенсивности (день × час и т.п.). Ячейки красятся изумрудной
 * шкалой; «over» — перегруз (красный), «closed» — закрыто (штрих). Переиспользуется
 * на «Посещаемости» и «Загруженности». Карты/типы — в ./heatmap-utils.
 */
export function IntensityHeatmap({
  hours,
  rows,
  labelWidth = 56,
  cellHeight = 26,
}: {
  hours: string[];
  rows: HeatRowData[];
  labelWidth?: number;
  cellHeight?: number;
}) {
  const cols = `${labelWidth}px repeat(${hours.length}, minmax(0, 1fr))`;
  return (
    <div className="overflow-x-auto [scrollbar-width:thin]">
      <div className="min-w-[640px]">
        <div className="grid gap-[3px]" style={{ gridTemplateColumns: cols }}>
          <span />
          {hours.map((h) => (
            <span key={h} className="pb-1 text-center text-[10px] tabular-nums text-fg-subtle">
              {h}
            </span>
          ))}
        </div>
        {rows.map((row) => (
          <div
            key={row.label}
            className="grid gap-[3px] py-[1.5px]"
            style={{ gridTemplateColumns: cols }}
          >
            <span
              className={cn(
                'flex items-center text-[11px] font-semibold',
                row.weekend ? 'text-primary-deep dark:text-primary' : 'text-fg-subtle',
              )}
            >
              {row.label}
            </span>
            {row.cells.map((c, i) => (
              <div
                key={i}
                title={c.title}
                style={{ height: cellHeight }}
                className={cn(
                  'grid place-items-center rounded-[5px] text-[9px] font-bold transition-transform',
                  cellClass(c.level),
                  c.level !== 'closed' && 'hover:scale-[1.15] hover:shadow-2',
                  c.now && 'ring-2 ring-inset ring-fg dark:ring-primary',
                )}
              >
                {c.text}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
