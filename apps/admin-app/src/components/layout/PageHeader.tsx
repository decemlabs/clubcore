import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { ChevronLeft } from '@/components/icons';

/**
 * Шапка страницы: крупный заголовок + подпись слева, блок действий справа.
 * Сворачивается в колонку на мобиле (как во всех прототипах). `backLink` —
 * ссылка «назад» над заголовком для детальных страниц.
 */
export function PageHeader({
  title,
  subtitle,
  actions,
  actionsClassName,
  backLink,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  /** Доп. классы контейнера действий (напр. горизонтальный скролл на мобиле). */
  actionsClassName?: string;
  backLink?: { to: string; label?: string };
  className?: string;
}) {
  return (
    <div
      className={cn('flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between', className)}
    >
      <div className="min-w-0">
        {backLink ? (
          <Link
            to={backLink.to}
            className="mb-1.5 inline-flex items-center gap-1 text-[13px] font-medium text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ChevronLeft className="size-3.5" />
            {backLink.label ?? 'Назад'}
          </Link>
        ) : null}
        <h1 className="text-[22px] font-bold leading-[1.1] tracking-[-0.5px] sm:text-[28px] sm:tracking-[-0.6px]">
          {title}
        </h1>
        {subtitle ? (
          <p className="mt-1 text-[13.5px] text-fg-muted sm:text-sm">{subtitle}</p>
        ) : null}
      </div>
      {actions ? (
        <div className={cn('flex items-center gap-2', actionsClassName)}>{actions}</div>
      ) : null}
    </div>
  );
}
