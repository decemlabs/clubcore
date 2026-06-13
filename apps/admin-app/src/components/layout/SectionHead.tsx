import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

/**
 * Заголовок секции уровня страницы (вне карточки): крупный H2 + подпись слева,
 * управляющий контрол справа. Переносит контрол под заголовок на узких экранах —
 * без горизонтального скролла. Источник — секции «Команда» / «Загрузка» в Trainers.
 */
export function SectionHead({
  title,
  subtitle,
  action,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-wrap items-end justify-between gap-x-4 gap-y-2.5', className)}>
      <div className="min-w-0">
        <h2 className="text-[18px] font-bold leading-tight tracking-[-0.3px]">{title}</h2>
        {subtitle ? <p className="mt-1 text-[13px] text-fg-muted">{subtitle}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
