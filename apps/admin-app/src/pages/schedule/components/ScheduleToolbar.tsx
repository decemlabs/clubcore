import { cn } from '@/lib/cn';
import { Activity, ChevronLeft, ChevronRight, LayoutGrid, Users } from '@/components/icons';
import { Toolbar, FilterSelect, type FilterOption } from '@/components/data/Toolbar';
import type { ScheduleData } from '@/features/schedule/types';

export interface ScheduleFilters {
  trainer: string;
  type: string;
  hall: string;
}

const TYPE_OPTIONS: FilterOption[] = [
  { value: 'all', label: 'Все' },
  { value: 'personal', label: 'Персональные' },
  { value: 'group', label: 'Групповые' },
];
const HALL_OPTIONS: FilterOption[] = [
  { value: 'all', label: 'Все' },
  { value: '1', label: 'Зал 1' },
  { value: '2', label: 'Зал 2' },
  { value: '3', label: 'Зал 3' },
];

const NAV_BTN =
  'grid size-[26px] place-items-center rounded-full text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

export function ScheduleToolbar({
  data,
  filters,
  onChange,
}: {
  data: ScheduleData;
  filters: ScheduleFilters;
  onChange: (patch: Partial<ScheduleFilters>) => void;
}) {
  const trainerOptions: FilterOption[] = [
    { value: 'all', label: `Все ${data.trainers.length}` },
    ...data.trainers.map((t) => ({ value: t.key, label: t.legend })),
  ];

  return (
    <Toolbar>
      {/* Навигатор недели (визуальный — данные на одну неделю) */}
      <div className="inline-flex items-center gap-1 rounded-full border-[0.5px] border-border bg-surface p-[3px]">
        <button
          type="button"
          className={NAV_BTN}
          title="Прошлая неделя"
          aria-label="Прошлая неделя"
        >
          <ChevronLeft className="size-3.5" strokeWidth={2.4} />
        </button>
        <span className="px-1.5 text-[13px] font-semibold tabular-nums">{data.rangeLabel}</span>
        <button
          type="button"
          className={NAV_BTN}
          title="Следующая неделя"
          aria-label="Следующая неделя"
        >
          <ChevronRight className="size-3.5" strokeWidth={2.4} />
        </button>
        <button
          type="button"
          className="ml-0.5 rounded-full bg-surface-2 px-3 py-1 text-[12.5px] font-semibold text-fg transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Сегодня
        </button>
      </div>

      <FilterSelect
        icon={Users}
        label="Тренер"
        options={trainerOptions}
        value={filters.trainer}
        onChange={(v) => onChange({ trainer: v })}
      />
      <FilterSelect
        icon={Activity}
        label="Тип"
        options={TYPE_OPTIONS}
        value={filters.type}
        onChange={(v) => onChange({ type: v })}
      />
      <FilterSelect
        icon={LayoutGrid}
        label="Зал"
        options={HALL_OPTIONS}
        value={filters.hall}
        onChange={(v) => onChange({ hall: v })}
      />

      {/* Легенда тренеров */}
      <div className={cn('ml-auto flex flex-wrap items-center gap-x-3 gap-y-1.5 max-lg:hidden')}>
        {data.trainers.map((t) => (
          <span key={t.key} className="inline-flex items-center gap-1.5 text-[12px] text-fg-muted">
            <span className="size-2.5 rounded-[3px]" style={{ background: t.color }} />
            {t.legend}
          </span>
        ))}
      </div>
    </Toolbar>
  );
}
