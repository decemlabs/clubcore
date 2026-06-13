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

// Пилюля статуса продвинута в слой features (переиспользуется в таблице и карточках).
export { StatusPill } from '@/features/trainers/components/StatusPill';

/**
 * Меню действий по тренеру (⋯). Профиль/статистика ведут на детальную страницу
 * (с #payouts — сразу на вкладку выплат); «Написать» и «Расписание» — на маршруты.
 */
export function TrainerActions({
  trainerId,
  className,
}: {
  trainerId?: string;
  className?: string;
}) {
  const navigate = useNavigate();
  const profile = trainerId ? ROUTES.trainer(trainerId) : ROUTES.trainers;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Действия с тренером"
          className={cn(
            'grid size-[30px] place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            className,
          )}
        >
          <MoreHorizontal className="size-[18px]" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[200px]">
        <DropdownMenuItem onSelect={() => navigate(profile)}>Открыть профиль</DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate(ROUTES.schedule)}>
          Расписание тренера
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate(`${profile}#payouts`)}>
          Статистика и выплаты
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate(ROUTES.messages)}>
          Написать сообщение
        </DropdownMenuItem>
        <DropdownMenuItem>Сменить статус</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-danger focus:text-danger">
          Удалить из штата
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
