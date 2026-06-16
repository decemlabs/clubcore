import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { ChevronRight } from '@/components/icons';

/** Базовая оболочка карточки: граница + поверхность + тень, скруглённый клип. */
export function Card({
  as: Comp = 'div',
  className,
  children,
}: {
  as?: 'div' | 'section';
  className?: string;
  children: ReactNode;
}) {
  return (
    <Comp
      className={cn(
        'overflow-hidden rounded-lg border-[0.5px] border-border bg-surface shadow-1',
        className,
      )}
    >
      {children}
    </Comp>
  );
}

/** Шапка карточки: заголовок (+inline-добавка) + подпись + действие справа. */
export function CardHeader({
  title,
  titleExtra,
  subtitle,
  action,
  align = 'start',
  className,
}: {
  title: ReactNode;
  titleExtra?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  /** Выравнивание строки шапки: 'start' (по умолчанию) или 'center'. */
  align?: 'start' | 'center';
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex flex-wrap justify-between gap-x-3 gap-y-2 px-5 pb-3 pt-4',
        align === 'center' ? 'items-center' : 'items-start',
        className,
      )}
    >
      <div className="min-w-0">
        <div className="flex items-center text-[15px] font-[650] leading-tight tracking-[-0.2px]">
          {title}
          {titleExtra}
        </div>
        {subtitle ? <div className="mt-0.5 text-xs text-fg-subtle">{subtitle}</div> : null}
      </div>
      {action ? <div className="flex shrink-0 items-center">{action}</div> : null}
    </div>
  );
}

/**
 * Действие-ссылка в шапке карточки. С `to` — навигационная ссылка с шевроном
 * («Все →»); без `to` — текстовая кнопка-действие («Изменить»).
 */
export function CardLink({
  to,
  children,
  className,
  ...props
}: React.ComponentProps<'button'> & { to?: string }) {
  if (to) {
    return (
      <Link
        to={to}
        className={cn(
          'inline-flex shrink-0 items-center gap-1 rounded-md text-[12.5px] font-semibold text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface',
          className,
        )}
      >
        {children}
        <ChevronRight className="size-3" strokeWidth={2.4} />
      </Link>
    );
  }
  return (
    <button
      type="button"
      className={cn(
        'shrink-0 rounded-md text-[12.5px] font-semibold text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
