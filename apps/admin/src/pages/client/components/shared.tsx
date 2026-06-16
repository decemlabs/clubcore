import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { CardHeader, CardLink as BaseCardLink } from '@/components/layout/Card';
import type { Rich } from '@/features/clients/detail';

// Оболочка карточки — общий компонент (на детальной странице используется как и раньше).
export { Card } from '@/components/layout/Card';

/** Рендер лёгкой разметки (string или сегменты с bold/muted). */
export function RichText({ value }: { value: Rich }) {
  if (typeof value === 'string') return <>{value}</>;
  return (
    <>
      {value.map((s, i) =>
        s.bold ? (
          <b key={i} className="font-semibold text-fg">
            {s.text}
          </b>
        ) : s.muted ? (
          <span key={i} className="font-normal text-fg-subtle">
            {s.text}
          </span>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </>
  );
}

/** Шапка карточки таб-панели: заголовок + подпись + действие. Делегирует общему CardHeader. */
export function CardHead({
  title,
  sub,
  action,
  className,
}: {
  title: ReactNode;
  sub?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <CardHeader title={title} subtitle={sub} action={action} align="center" className={className} />
  );
}

/** Текстовая ссылка-действие в шапке карточки. */
export function CardLink(props: React.ComponentProps<'button'>) {
  return <BaseCardLink {...props} />;
}

/** Чип-тег (цели, предпочтения, теги заметок). */
export function Chip({ warn, children }: { warn?: boolean; children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex h-[22px] items-center rounded-full px-[9px] text-[11.5px]',
        warn
          ? 'bg-warning-soft font-semibold text-warning-deep'
          : 'bg-surface-3 font-medium text-fg-muted',
      )}
    >
      {children}
    </span>
  );
}

/** Боковая карточка с заголовком-капсом и опциональным действием. */
export function SideCard({
  title,
  action,
  children,
  className,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'rounded-lg border-[0.5px] border-border bg-surface px-[18px] py-4 shadow-1',
        className,
      )}
    >
      <div className="mb-3.5 flex items-center justify-between gap-2">
        <div className="text-[13px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
          {title}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

/** Текстовая ссылка в шапке боковой карточки («Изменить», «Сменить»). */
export function SideCardLink({ children, className, ...props }: React.ComponentProps<'button'>) {
  return (
    <button
      type="button"
      className={cn(
        'shrink-0 rounded-md px-1.5 py-0.5 text-xs font-semibold text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

/** Компактная кнопка-пилюля (заморозить / отменить / ответить). */
export function MiniButton({
  danger,
  className,
  ...props
}: React.ComponentProps<'button'> & { danger?: boolean }) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex h-[30px] items-center justify-center rounded-full border-[0.5px] border-border bg-surface px-3 text-xs font-semibold tracking-[-0.1px] transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        danger ? 'text-danger' : 'text-fg',
        className,
      )}
      {...props}
    />
  );
}
