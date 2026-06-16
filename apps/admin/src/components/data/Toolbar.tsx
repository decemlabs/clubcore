import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { ChevronDown, Search } from '@/components/icons';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

/** Базовый класс пилюли-контрола тулбара (фильтр-кнопка, «Ещё фильтры» и т.п.). */
export const TOOLBAR_FIELD_CLS =
  'inline-flex h-9 shrink-0 items-center gap-2 rounded-full border-[0.5px] border-border bg-surface pl-3 pr-3.5 text-[13px] text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring max-sm:h-[34px] max-sm:text-[12.5px]';

/** Контейнер панели управления списком (поиск + фильтры + переключатель вида). */
export function Toolbar({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('flex flex-wrap items-center gap-2.5', className)}>{children}</div>;
}

/** Поле поиска со скруглённой пилюлей и иконкой. */
export function SearchInput({
  value,
  onChange,
  placeholder,
  className,
  inputClassName,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  /** Классы внешнего контейнера (ширина/порядок во flex). */
  className?: string;
  inputClassName?: string;
}) {
  return (
    <div className={cn('relative', className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(
          'h-9 w-full rounded-full border-[0.5px] border-border bg-surface pl-9 pr-3.5 text-[13px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-fg-subtle',
          inputClassName,
        )}
      />
    </div>
  );
}

export interface FilterOption {
  value: string;
  label: string;
}

/** Пилюля-фильтр с выпадающим radio-меню (иконка + метка + текущее значение). */
export function FilterSelect({
  icon: Icon,
  label,
  options,
  value,
  onChange,
}: {
  icon: LucideIcon;
  label: string;
  options: FilterOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  const current = options.find((o) => o.value === value) ?? options[0];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className={TOOLBAR_FIELD_CLS}>
          <Icon className="size-3.5 text-fg-subtle" />
          <span className="text-fg-muted max-sm:hidden">{label}:</span>
          <span className="font-semibold text-fg">{current?.label}</span>
          <ChevronDown className="size-3 text-fg-subtle" strokeWidth={2.4} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-[180px]">
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          {options.map((o) => (
            <DropdownMenuRadioItem key={o.value} value={o.value}>
              {o.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export interface ViewToggleOption<V extends string> {
  value: V;
  icon: LucideIcon;
  title: string;
}

/** Сегментный переключатель режима отображения (таблица / карточки и т.п.). */
export function ViewToggle<V extends string>({
  value,
  onChange,
  options,
  className,
}: {
  value: V;
  onChange: (value: V) => void;
  options: ViewToggleOption<V>[];
  className?: string;
}) {
  return (
    <div
      className={cn(
        'inline-flex gap-0.5 rounded-full border-[0.5px] border-border bg-surface p-[3px]',
        className,
      )}
    >
      {options.map(({ value: v, icon: Icon, title }) => {
        const active = value === v;
        return (
          <button
            key={v}
            type="button"
            aria-pressed={active}
            title={title}
            onClick={() => onChange(v)}
            className={cn(
              'grid h-7 w-8 place-items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active ? 'bg-fg text-bg' : 'text-fg-muted hover:text-fg',
            )}
          >
            <Icon className="size-3.5" strokeWidth={2.2} />
          </button>
        );
      })}
    </div>
  );
}
