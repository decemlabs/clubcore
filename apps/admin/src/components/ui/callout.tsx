import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';

export function Callout({
  tone = 'default',
  icon: Icon,
  children,
}: {
  tone?: 'default' | 'accent' | 'warn' | 'danger';
  icon: LucideIcon;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        'flex gap-2.5 rounded-xl border-[0.5px] p-[12px_14px]',
        tone === 'accent' && 'border-transparent bg-primary-soft',
        tone === 'warn' && 'border-transparent bg-warning-soft',
        tone === 'danger' && 'border-transparent bg-danger-soft',
        tone === 'default' && 'border-border bg-surface-2',
      )}
    >
      <Icon
        className={cn(
          'mt-px size-5 shrink-0',
          tone === 'accent' && 'text-primary-deep dark:text-primary',
          tone === 'warn' && 'text-warning-deep',
          tone === 'danger' && 'text-danger',
          tone === 'default' && 'text-fg-muted',
        )}
        strokeWidth={2.2}
      />
      <div
        className={cn(
          'text-[12.5px] leading-relaxed',
          tone === 'accent' ? 'text-primary-deep dark:text-primary' : 'text-fg-muted',
          '[&_b]:font-[650] [&_b]:text-fg',
        )}
      >
        {children}
      </div>
    </div>
  );
}
