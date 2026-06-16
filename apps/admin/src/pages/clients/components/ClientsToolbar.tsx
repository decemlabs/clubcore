/**
 * Clients list toolbar — server-supported filters only (Phase 101 CLI-01).
 *
 * Removed (mock-only): membership-status tabs, planType, trainer, «Ещё фильтры» button,
 * unsupported sort presets (expires/visits/last).
 *
 * Added (backend-supported): gender, hasTelegram, tag filters.
 * Sort: recent:desc (default) and name:asc only.
 */
import { ArrowUpDown, LayoutGrid, List, MessageSquare, Tag, User } from '@/components/icons';
import {
  Toolbar,
  SearchInput,
  FilterSelect,
  ViewToggle,
  type FilterOption,
} from '@/components/data/Toolbar';

export type ViewMode = 'table' | 'cards';

export type GenderFilter = 'all' | 'male' | 'female';
export type TelegramFilter = 'all' | 'yes' | 'no';
export type SortPreset = 'recent:desc' | 'name:asc';

const GENDER_OPTIONS: FilterOption[] = [
  { value: 'all', label: 'Все' },
  { value: 'male', label: 'Мужской' },
  { value: 'female', label: 'Женский' },
];

const TELEGRAM_OPTIONS: FilterOption[] = [
  { value: 'all', label: 'Все' },
  { value: 'yes', label: 'Есть Telegram' },
  { value: 'no', label: 'Нет Telegram' },
];

const SORT_OPTIONS: FilterOption[] = [
  { value: 'recent:desc', label: 'Недавние' },
  { value: 'name:asc', label: 'По имени (А–Я)' },
];

export interface ClientsToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  gender: GenderFilter;
  onGenderChange: (value: GenderFilter) => void;
  telegram: TelegramFilter;
  onTelegramChange: (value: TelegramFilter) => void;
  tag: string;
  onTagChange: (value: string) => void;
  tagOptions: FilterOption[];
  sort: SortPreset;
  onSortChange: (sort: SortPreset) => void;
  view: ViewMode;
  onViewChange: (view: ViewMode) => void;
}

export function ClientsToolbar({
  search,
  onSearchChange,
  gender,
  onGenderChange,
  telegram,
  onTelegramChange,
  tag,
  onTagChange,
  tagOptions,
  sort,
  onSortChange,
  view,
  onViewChange,
}: ClientsToolbarProps) {
  return (
    <Toolbar>
      <SearchInput
        value={search}
        onChange={onSearchChange}
        placeholder="Поиск: имя, телефон, e-mail…"
        className="order-first min-w-[220px] flex-1 max-sm:w-full max-sm:flex-[1_1_100%] sm:max-w-[320px]"
      />

      <FilterSelect
        icon={User}
        label="Пол"
        options={GENDER_OPTIONS}
        value={gender}
        onChange={(v) => onGenderChange(v as GenderFilter)}
      />
      <FilterSelect
        icon={MessageSquare}
        label="Telegram"
        options={TELEGRAM_OPTIONS}
        value={telegram}
        onChange={(v) => onTelegramChange(v as TelegramFilter)}
      />
      {tagOptions.length > 1 && (
        <FilterSelect
          icon={Tag}
          label="Тег"
          options={tagOptions}
          value={tag}
          onChange={onTagChange}
        />
      )}
      <FilterSelect
        icon={ArrowUpDown}
        label="Сортировка"
        options={SORT_OPTIONS}
        value={sort}
        onChange={(v) => onSortChange(v as SortPreset)}
      />

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
