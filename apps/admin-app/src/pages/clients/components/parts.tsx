import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';
import { MoreHorizontal } from '@/components/icons';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import type { PlanTone } from '@/features/clients/types';
import { PLAN_FILL } from './status-styles';

// Пилюля статуса продвинута в слой features (переиспользуется на детальной странице клиента).
export { StatusPill } from '@/features/clients/components/StatusPill';
// Чекбокс продвинут в общий UI-слой.
export { Checkbox } from '@/components/ui/Checkbox';

/** Тонкий прогресс-бар абонемента (дни использования). */
export function PlanBar({
  pct,
  tone,
  className,
}: {
  pct: number;
  tone: PlanTone;
  className?: string;
}) {
  return (
    <div className={cn('h-1 overflow-hidden rounded-full bg-surface-3', className)}>
      <div
        className={cn('h-full rounded-full', PLAN_FILL[tone])}
        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
      />
    </div>
  );
}

/** Меню действий в строке/карточке клиента (⋯). */
export function RowActions({ clientId, className }: { clientId: string; className?: string }) {
  const navigate = useNavigate();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Действия с клиентом"
          className={cn(
            'grid size-[30px] place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            className,
          )}
        >
          <MoreHorizontal className="size-[18px]" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[190px]">
        <DropdownMenuItem onSelect={() => navigate(ROUTES.client(clientId))}>
          Открыть профиль
        </DropdownMenuItem>
        <DropdownMenuItem>Написать сообщение</DropdownMenuItem>
        <DropdownMenuItem>Продлить абонемент</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-danger focus:text-danger">Архивировать</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
