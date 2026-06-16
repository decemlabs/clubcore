/**
 * ScheduleToolbar — Phase 102-03 SCH-02.
 *
 * Changes from Phase 37 mock toolbar:
 *   - «Зал» FilterSelect REMOVED (no backend param for hall filter).
 *   - «Тип» FilterSelect REMOVED (TrainerSlot model has no kind field).
 *   - «Тренер» FilterSelect now populated from real useTrainers({active:true}).
 *   - Week navigator prev/next/today buttons wired to onWeekChange callbacks.
 *   - Trainer legend built from real trainer data (color from caller-supplied map).
 *
 * UI-SPEC §Surface 4 toolbar reduction.
 */
import { ChevronLeft, ChevronRight, Users } from '@/components/icons';
import { Toolbar, FilterSelect, type FilterOption } from '@/components/data/Toolbar';
import { useTrainers } from '@/features/trainers/api';

export interface ScheduleFilters {
  trainer: string;
}

/** NAV button shared style */
const NAV_BTN =
  'grid size-[26px] place-items-center rounded-full text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

interface ScheduleToolbarProps {
  rangeLabel: string;
  filters: ScheduleFilters;
  trainerColorMap: Map<string, string>;
  onChange: (patch: Partial<ScheduleFilters>) => void;
  onPrevWeek: () => void;
  onNextWeek: () => void;
  onToday: () => void;
}

export function ScheduleToolbar({
  rangeLabel,
  filters,
  trainerColorMap,
  onChange,
  onPrevWeek,
  onNextWeek,
  onToday,
}: ScheduleToolbarProps) {
  const trainersQuery = useTrainers({ active: true });
  const trainers = trainersQuery.data?.items ?? [];

  const trainerOptions: FilterOption[] = [
    { value: 'all', label: trainers.length > 0 ? `Все ${trainers.length}` : 'Все' },
    ...trainers.map((t) => ({
      value: t.id,
      label: t.fullName,
    })),
  ];

  return (
    <Toolbar>
      {/* Week navigator */}
      <div className="inline-flex items-center gap-1 rounded-full border-[0.5px] border-border bg-surface p-[3px]">
        <button
          type="button"
          className={NAV_BTN}
          title="Прошлая неделя"
          aria-label="Прошлая неделя"
          onClick={onPrevWeek}
        >
          <ChevronLeft className="size-3.5" strokeWidth={2.4} />
        </button>
        <span className="px-1.5 text-[13px] font-semibold tabular-nums">{rangeLabel}</span>
        <button
          type="button"
          className={NAV_BTN}
          title="Следующая неделя"
          aria-label="Следующая неделя"
          onClick={onNextWeek}
        >
          <ChevronRight className="size-3.5" strokeWidth={2.4} />
        </button>
        <button
          type="button"
          className="ml-0.5 rounded-full bg-surface-2 px-3 py-1 text-[12.5px] font-semibold text-fg transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={onToday}
        >
          Сегодня
        </button>
      </div>

      {/* Тренер filter (real data from API) */}
      <FilterSelect
        icon={Users}
        label="Тренер"
        options={trainerOptions}
        value={filters.trainer}
        onChange={(v) => onChange({ trainer: v })}
      />

      {/* Trainer legend (color-coded, real data) */}
      {trainers.length > 0 && (
        <div className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1.5 max-lg:hidden">
          {trainers.map((t) => (
            <span key={t.id} className="inline-flex items-center gap-1.5 text-[12px] text-fg-muted">
              <span
                className="size-2.5 rounded-[3px]"
                style={{ background: trainerColorMap.get(t.id) ?? '#888' }}
              />
              {t.fullName}
            </span>
          ))}
        </div>
      )}
    </Toolbar>
  );
}
