import { useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Card } from '@/components/layout/Card';
import { Clock, Coffee, Lock, Star, Upload } from '@/components/icons';
import type { Addon, AddonIconKind } from '@/features/plans/types';

const ICON: Record<AddonIconKind, LucideIcon> = {
  sauna: Upload,
  guest: Star,
  towel: Lock,
  shaker: Coffee,
  freeze: Clock,
};

/** Список доп. услуг с ценой и переключателем (локальное состояние). */
export function AddonsCard({ addons }: { addons: Addon[] }) {
  const [enabled, setEnabled] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(addons.map((a) => [a.id, a.on])),
  );

  return (
    <Card>
      {addons.map((a, i) => {
        const Icon = ICON[a.iconKind];
        const on = enabled[a.id];
        return (
          <div
            key={a.id}
            className={cn(
              'grid grid-cols-[36px_minmax(0,1fr)_auto_auto] items-center gap-3.5 px-5 py-3.5 transition-colors hover:bg-surface-2 max-[740px]:grid-cols-[36px_minmax(0,1fr)_auto]',
              i > 0 && 'border-t-[0.5px] border-border',
            )}
          >
            <span className="grid size-9 place-items-center rounded-[10px] bg-surface-3 text-fg">
              <Icon className="size-[18px]" />
            </span>
            <div className="min-w-0">
              <div className="text-[14px] font-semibold">{a.title}</div>
              <div className="mt-0.5 text-[12px] text-fg-muted">{a.sub}</div>
            </div>
            <div className="whitespace-nowrap text-right">
              <div className="text-[14px] font-bold tabular-nums">{a.price}</div>
              <div className="text-[11px] text-fg-subtle">{a.unit}</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={on}
              aria-label={`${a.title}: ${on ? 'включена' : 'выключена'}`}
              onClick={() => setEnabled((s) => ({ ...s, [a.id]: !s[a.id] }))}
              className={cn(
                'relative h-[18px] w-8 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring max-[740px]:hidden',
                on ? 'bg-fg dark:bg-primary' : 'bg-border-strong',
              )}
            >
              <span
                className={cn(
                  'absolute top-0.5 size-3.5 rounded-full bg-white transition-[left]',
                  on ? 'left-[18px]' : 'left-0.5',
                )}
              />
            </button>
          </div>
        );
      })}
    </Card>
  );
}
