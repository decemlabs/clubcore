import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * Пустое состояние списка/раздела: иконка в круге + заголовок + подпись + действие.
 * Источник дизайна — States.html / страница «Клиенты».
 */
export function EmptyState({
  icon: Icon,
  title,
  message,
  action,
  className,
}: {
  icon?: LucideIcon;
  title: ReactNode;
  message?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 px-6 py-16 text-center',
        className,
      )}
    >
      {Icon ? (
        <span className="grid size-12 place-items-center rounded-full bg-surface-3 text-fg-subtle">
          <Icon className="size-5" />
        </span>
      ) : null}
      <div>
        <div className="text-[15px] font-semibold">{title}</div>
        {message ? <div className="mt-1 text-[13px] text-fg-subtle">{message}</div> : null}
      </div>
      {action}
    </div>
  );
}
