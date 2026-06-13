import type { LucideIcon } from 'lucide-react';
import { SquareCheckBig, UserPlus, CreditCard, Calendar } from '@/components/icons';
import { useModals, type ModalKey } from '@/components/modals/modals-context';
import { cn } from '@/lib/cn';

interface DockAction {
  key: ModalKey;
  label: string;
  icon: LucideIcon;
  primary?: boolean;
}

/**
 * Быстрые действия дублируют пункты из mobile-dock.js, но открывают СУЩЕСТВУЮЩИЕ
 * глобальные модалки — AdaptiveModal сам показывает их как bottom-sheet на мобиле,
 * поэтому отдельные шиты из макета не нужны.
 */
const ACTIONS: DockAction[] = [
  { key: 'checkin', label: 'Чек-ин', icon: SquareCheckBig, primary: true },
  { key: 'new-client', label: 'Клиент', icon: UserPlus },
  { key: 'extend', label: 'Продлить', icon: CreditCard },
  { key: 'book', label: 'Запись', icon: Calendar },
];

/**
 * Нижний док быстрых действий (≤lg). Скрыт на десктопе (lg:hidden). Учитывает
 * safe-area; нижний паддинг контента задаётся в AppLayout, чтобы док не перекрывал
 * последний блок страницы.
 */
export function MobileDock() {
  const { open } = useModals();

  return (
    <nav
      aria-label="Быстрые действия"
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 gap-0.5 border-t border-border bg-surface/90 px-2 pt-[7px] backdrop-blur-xl backdrop-saturate-150 lg:hidden"
      style={{ paddingBottom: 'max(8px, env(safe-area-inset-bottom))' }}
    >
      {ACTIONS.map(({ key, label, icon: Icon, primary }) => (
        <button
          key={key}
          type="button"
          onClick={() => open(key)}
          className="group flex min-h-[56px] flex-col items-center justify-center gap-1 rounded-xl px-0.5 pb-[5px] pt-1.5 transition-[background,transform] active:scale-95 active:bg-surface-3"
        >
          <span
            className={cn(
              'grid size-[30px] place-items-center rounded-[9px] transition-colors',
              primary
                ? 'bg-fg text-bg ring-[3px] ring-primary-soft dark:bg-primary dark:text-primary-foreground'
                : 'bg-surface-3 text-fg-muted',
            )}
          >
            <Icon className="size-4" strokeWidth={2.2} />
          </span>
          <span
            className={cn(
              'text-[10.5px] font-semibold leading-none tracking-[-0.1px]',
              primary ? 'text-fg' : 'text-fg-subtle',
            )}
          >
            {label}
          </span>
        </button>
      ))}
    </nav>
  );
}
