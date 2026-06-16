import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

/** Тяжёлая панель раздела: 18px-радиус + shadow-2 (в отличие от лёгкой Card). */
export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        'overflow-hidden rounded-[18px] border-[0.5px] border-border bg-surface shadow-2',
        className,
      )}
    >
      {children}
    </div>
  );
}
/** Компактная шапка панели с нижней границей (стиль «Уведомления»). */
export function PanelHead({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 border-b-[0.5px] border-border px-[18px] py-3.5">
      <h2 className="text-sm font-bold">{title}</h2>
      {action ? <div className="ml-auto flex items-center gap-2">{action}</div> : null}
    </div>
  );
}
/** Заголовок-с-подписью без границы (стиль «Импорт/экспорт»). */
export function PanelTitle({ title, caption }: { title: string; caption?: ReactNode }) {
  return (
    <div className="px-[18px] pb-1 pt-4">
      <h2 className="text-[15px] font-bold">{title}</h2>
      {caption ? <div className="mt-1 text-[12.5px] text-fg-subtle">{caption}</div> : null}
    </div>
  );
}
/** Стандартный отступ тела панели. */
export function PanelBody({ children }: { children: ReactNode }) {
  return <div className="px-[18px] pb-[18px] pt-3.5">{children}</div>;
}
