import { useState } from 'react';
import { cn } from '@/lib/cn';
import { ChevronDown, CreditCard, Search, User } from '@/components/icons';

const BRANCHES = ['Все филиалы', 'Тверская', 'Парк', 'Юг'];

const CHIP =
  'inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full px-3 text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

/** Панель фильтров: группа филиалов (single-select) + дропдаун-чипы + поиск. */
export function AttendanceFilters() {
  const [branch, setBranch] = useState('Все филиалы');
  return (
    <div className="-mx-1 flex items-center gap-2 overflow-x-auto px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {BRANCHES.map((b) => {
        const active = branch === b;
        return (
          <button
            key={b}
            type="button"
            onClick={() => setBranch(b)}
            className={cn(
              CHIP,
              active
                ? 'bg-fg text-bg dark:bg-primary dark:text-[#06120c]'
                : 'border-[0.5px] border-border text-fg-muted hover:border-border-strong hover:text-fg',
            )}
          >
            {b}
            {b === 'Все филиалы' ? (
              <span className={cn('font-medium', active ? 'opacity-70' : 'text-fg-subtle')}>
                · 3
              </span>
            ) : null}
            {b === 'Все филиалы' ? <ChevronDown className="size-3" strokeWidth={2.4} /> : null}
          </button>
        );
      })}

      <span className="h-[18px] w-px shrink-0 bg-border" />

      <button
        type="button"
        className={cn(
          CHIP,
          'border-[0.5px] border-border text-fg-muted hover:border-border-strong hover:text-fg',
        )}
      >
        <CreditCard className="size-3.5 text-fg-subtle" />
        Все абонементы
        <ChevronDown className="size-3" strokeWidth={2.4} />
      </button>
      <button
        type="button"
        className={cn(
          CHIP,
          'border-[0.5px] border-border text-fg-muted hover:border-border-strong hover:text-fg',
        )}
      >
        <User className="size-3.5 text-fg-subtle" />
        Все клиенты <span className="text-fg-subtle">· 847</span>
      </button>
      <button
        type="button"
        className={cn(
          CHIP,
          'border-[0.5px] border-border text-fg-muted hover:border-border-strong hover:text-fg',
        )}
      >
        Визиты + групповые
        <ChevronDown className="size-3" strokeWidth={2.4} />
      </button>

      <span className="h-[18px] w-px shrink-0 bg-border max-md:hidden" />

      <div className="relative w-[200px] shrink-0 max-md:hidden">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-fg-subtle" />
        <input
          type="search"
          placeholder="Поиск клиента…"
          className="h-8 w-full rounded-full border-[0.5px] border-border bg-surface pl-8 pr-3 text-[12.5px] outline-none transition-colors placeholder:text-fg-subtle focus:border-fg-subtle"
        />
      </div>
    </div>
  );
}
