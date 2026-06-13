import { Check, ChevronDown, Plus } from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useActiveClub } from './club-context';

/** Селектор филиала в шапке сайдбара: триггер + выпадающий список с отметкой активного. */
export function ClubSelector() {
  const { clubs, activeId, active, setActiveId } = useActiveClub();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="group flex w-full items-center gap-2.5 rounded-md border-[0.5px] border-border bg-surface px-3 py-[9px] text-left outline-none transition-colors hover:border-border-strong focus-visible:ring-2 focus-visible:ring-ring">
        <span className="size-2 shrink-0 rounded-full bg-primary" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13.5px] font-semibold leading-tight text-fg">
            {active.name}
          </span>
          <span className="block truncate text-[11.5px] text-fg-subtle">{active.sub}</span>
        </span>
        <ChevronDown className="size-3.5 shrink-0 text-fg-subtle transition-transform group-data-[state=open]:rotate-180" />
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="start"
        className="w-(--radix-dropdown-menu-trigger-width) min-w-64 p-1.5"
      >
        {clubs.map((club) => {
          const isActive = club.id === activeId;
          return (
            <DropdownMenuItem
              key={club.id}
              onSelect={() => setActiveId(club.id)}
              className={cn(
                'gap-2.5 rounded-lg px-2.5 py-2',
                isActive && 'bg-surface-3 focus:bg-surface-3',
              )}
            >
              <span
                className={cn('size-2 shrink-0 rounded-full bg-primary', !isActive && 'opacity-35')}
                aria-hidden
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold text-fg">
                  {club.name}
                </span>
                <span className="block truncate text-[11.5px] text-fg-subtle">{club.sub}</span>
              </span>
              {isActive ? <Check className="size-3.5 shrink-0 text-primary-deep" /> : null}
            </DropdownMenuItem>
          );
        })}

        <DropdownMenuSeparator />

        <DropdownMenuItem className="gap-2 rounded-lg px-2.5 py-2 text-[13px] font-medium text-fg-muted">
          <Plus className="size-3.5" />
          Добавить филиал
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
