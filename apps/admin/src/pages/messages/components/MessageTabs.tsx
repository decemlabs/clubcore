import { useState } from 'react';
import { cn } from '@/lib/cn';
import { CheckCircle2 } from '@/components/icons';
import type { StatusTab } from '@/features/messages/types';

const COUNT_TONE = {
  accent: 'bg-primary-soft text-primary-deep dark:text-primary',
  danger: 'bg-danger-soft text-danger',
  neutral: 'bg-surface-3 text-fg-muted',
} as const;

/** Вкладки статуса диалогов + действие «отметить всё прочитанным». */
export function MessageTabs({ tabs }: { tabs: StatusTab[] }) {
  const [active, setActive] = useState(tabs[0]?.id);

  return (
    <div className="-mx-1 flex items-center gap-1.5 overflow-x-auto border-b-[0.5px] border-border px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {tabs.map((t) => {
        const isActive = t.id === active;
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => setActive(t.id)}
            className={cn(
              'relative inline-flex shrink-0 items-center gap-2 whitespace-nowrap px-3.5 pb-3.5 pt-3 text-[13.5px] font-semibold tracking-[-0.1px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              isActive ? 'text-fg' : 'text-fg-muted hover:text-fg',
            )}
          >
            {t.label}
            {t.count != null ? (
              <span
                className={cn(
                  'rounded-full px-[7px] py-px text-[11.5px] font-bold tabular-nums',
                  isActive ? 'bg-fg text-bg' : COUNT_TONE[t.tone ?? 'neutral'],
                )}
              >
                {t.count}
              </span>
            ) : null}
            {isActive ? (
              <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-t-sm bg-fg" />
            ) : null}
          </button>
        );
      })}
      <button
        type="button"
        className="ml-auto inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-3 text-[13px] font-semibold text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <CheckCircle2 className="size-3.5" />
        <span className="max-sm:hidden">Отметить всё прочитанным</span>
      </button>
    </div>
  );
}
