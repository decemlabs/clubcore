import {
  ArrowUpDown,
  CreditCard,
  LayoutGrid,
  List,
  SlidersHorizontal,
  User,
} from '@/components/icons';
import {
  Toolbar,
  SearchInput,
  FilterSelect,
  ViewToggle,
  TOOLBAR_FIELD_CLS,
  type FilterOption,
} from '@/components/data/Toolbar';
import type { ClientSort } from '@/features/clients/types';

export type ViewMode = 'table' | 'cards';
export type PlanTypeFilter = 'all' | 'monthly' | 'half' | 'year';

const PLAN_OPTIONS: FilterOption[] = [
  { value: 'all', label: 'Все' },
  { value: 'monthly', label: 'Месячный' },
  { value: 'half', label: 'Полугодовой' },
  { value: 'year', label: 'Годовой' },
];

interface SortPreset extends FilterOption {
  key: ClientSort['key'];
  dir: ClientSort['dir'];
}

const SORT_PRESETS: SortPreset[] = [
  { value: 'expires:asc', label: 'Скоро истекают', key: 'expires', dir: 'asc' },
  { value: 'name:asc', label: 'По имени (А–Я)', key: 'name', dir: 'asc' },
  { value: 'visits:desc', label: 'Больше визитов', key: 'visits', dir: 'desc' },
  { value: 'last:desc', label: 'Недавние визиты', key: 'last', dir: 'desc' },
];

export interface ClientsToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  planType: PlanTypeFilter;
  onPlanTypeChange: (value: PlanTypeFilter) => void;
  trainer: string;
  onTrainerChange: (value: string) => void;
  trainerOptions: FilterOption[];
  sort: ClientSort;
  onSortChange: (sort: ClientSort) => void;
  view: ViewMode;
  onViewChange: (view: ViewMode) => void;
}

export function ClientsToolbar({
  search,
  onSearchChange,
  planType,
  onPlanTypeChange,
  trainer,
  onTrainerChange,
  trainerOptions,
  sort,
  onSortChange,
  view,
  onViewChange,
}: ClientsToolbarProps) {
  const sortValue = `${sort.key}:${sort.dir}`;
  const sortOptions = SORT_PRESETS.map((p) => ({ value: p.value, label: p.label }));

  return (
    <Toolbar>
      <SearchInput
        value={search}
        onChange={onSearchChange}
        placeholder="Поиск: имя, телефон, e-mail…"
        className="order-first min-w-[220px] flex-1 max-sm:w-full max-sm:flex-[1_1_100%] sm:max-w-[320px]"
      />

      <FilterSelect
        icon={CreditCard}
        label="Тип"
        options={PLAN_OPTIONS}
        value={planType}
        onChange={(v) => onPlanTypeChange(v as PlanTypeFilter)}
      />
      <FilterSelect
        icon={User}
        label="Тренер"
        options={trainerOptions}
        value={trainer}
        onChange={onTrainerChange}
      />
      <FilterSelect
        icon={ArrowUpDown}
        label="Сортировка"
        options={sortOptions}
        value={sortValue}
        onChange={(v) => {
          const preset = SORT_PRESETS.find((p) => p.value === v);
          if (preset) onSortChange({ key: preset.key, dir: preset.dir });
        }}
      />

      <button type="button" className={TOOLBAR_FIELD_CLS}>
        <SlidersHorizontal className="size-3.5 text-fg-subtle" />
        Ещё фильтры
      </button>

      <ViewToggle<ViewMode>
        className="ml-auto max-sm:hidden"
        value={view}
        onChange={onViewChange}
        options={[
          { value: 'table', icon: List, title: 'Таблица' },
          { value: 'cards', icon: LayoutGrid, title: 'Карточки' },
        ]}
      />
    </Toolbar>
  );
}
