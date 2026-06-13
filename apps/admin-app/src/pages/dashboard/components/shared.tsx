import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { Card, CardHeader, CardLink as BaseCardLink } from '@/components/layout/Card';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';

// Аватар-инициалы продвинут в общий слой (переиспользуется на странице «Клиенты»).
export { Initials } from '@/components/ui/initials';

/** Каркас карточки дашборда: шапка (заголовок + подпись + действие) и тело. Делегирует общему Card. */
export function DashboardCard({
  title,
  titleExtra,
  subtitle,
  action,
  children,
  className,
}: {
  title: ReactNode;
  titleExtra?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card as="section" className={cn('flex min-w-0 flex-col', className)}>
      <CardHeader title={title} titleExtra={titleExtra} subtitle={subtitle} action={action} />
      {children}
    </Card>
  );
}

/** Ссылка «Все →» в шапке карточки. */
export function CardLink({ to, children }: { to: string; children: ReactNode }) {
  return <BaseCardLink to={to}>{children}</BaseCardLink>;
}

export type MiniSegmentedOption<T extends string> = SegmentedOption<T>;

/** Компактный сегментный контрол внутри карточек (фильтры периодов/ленты). */
export function MiniSegmented<T extends string>(props: {
  options: MiniSegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel?: string;
  className?: string;
}) {
  return <Segmented variant="mini" {...props} />;
}

type ListButtonVariant = 'solid' | 'icon' | 'solidIcon';

const LIST_BUTTON_BASE =
  'inline-flex h-[30px] items-center justify-center gap-1.5 rounded-lg text-xs font-semibold tracking-[-0.1px] whitespace-nowrap transition-[background-color,color,border-color,transform] duration-150 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface';

const LIST_BUTTON_VARIANTS: Record<ListButtonVariant, string> = {
  solid:
    'px-3 bg-fg text-bg hover:bg-black dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]',
  icon: 'w-[30px] border-[0.5px] border-border bg-surface text-fg-muted hover:border-border-strong hover:bg-surface-2 hover:text-fg dark:bg-surface dark:text-fg-muted dark:hover:text-fg',
  solidIcon:
    'w-[30px] bg-fg text-bg hover:bg-black dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]',
};

/** Кнопка-действие в строках списков (тёмная пилюля / иконка). */
export function ListButton({
  variant = 'solid',
  className,
  children,
  ...props
}: React.ComponentProps<'button'> & { variant?: ListButtonVariant }) {
  return (
    <button
      type="button"
      className={cn(LIST_BUTTON_BASE, LIST_BUTTON_VARIANTS[variant], className)}
      {...props}
    >
      {children}
    </button>
  );
}
