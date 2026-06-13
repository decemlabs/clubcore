import type { LucideIcon } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { Gift, GraduationCap, Percent, Tag } from '@/components/icons';
import type { Promo, PromoIconKind, PromoStatus } from '@/features/plans/types';

const ICON: Record<PromoIconKind, { Icon: LucideIcon; cls: string }> = {
  discount: { Icon: Tag, cls: 'bg-primary-soft text-primary-deep dark:text-primary' },
  gift: { Icon: Gift, cls: 'bg-lead-soft text-lead' },
  student: { Icon: GraduationCap, cls: 'bg-warning-soft text-warning-deep' },
  percent: { Icon: Percent, cls: 'bg-primary-soft text-primary-deep dark:text-primary' },
};

const ACTION =
  'inline-flex h-[30px] items-center rounded-lg px-2.5 text-[12.5px] font-semibold transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function StatusPill({ status, label }: { status: PromoStatus; label: string }) {
  const active = status === 'active';
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full py-[3px] pl-[6px] pr-2 text-[10.5px] font-bold uppercase tracking-[0.3px]',
        active ? 'bg-primary-soft text-primary-deep dark:text-primary' : 'bg-surface-3 text-fg-muted',
      )}
    >
      <span className={cn('size-1.5 rounded-full', active ? 'animate-pulse bg-primary-deep dark:bg-primary' : 'bg-fg-subtle')} />
      {label}
    </span>
  );
}

/** Карточка акции/промо: иконка-тон, статус, описание, статистика, действия. */
export function PromoCard({ promo: p }: { promo: Promo }) {
  const { Icon, cls } = ICON[p.iconKind];
  return (
    <article className="flex gap-4 rounded-lg border-[0.5px] border-border bg-surface p-[18px] shadow-1">
      <span className={cn('grid size-11 shrink-0 place-items-center rounded-xl', cls)}>
        <Icon className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <div className="text-[14.5px] font-bold">
            {p.title}
            {p.codeChip ? (
              <code className="ml-1.5 rounded-[5px] bg-surface-3 px-1.5 py-0.5 font-mono text-[13px] font-semibold">
                {p.codeChip}
              </code>
            ) : null}
          </div>
          <StatusPill status={p.status} label={p.statusLabel} />
        </div>
        <p className="mt-1 text-[12px] leading-relaxed text-fg-muted">{p.sub}</p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-fg-muted">
          {p.stats.map((s) => (
            <span key={s.label}>
              {s.label}: <b className="font-semibold text-fg">{s.value}</b>
            </span>
          ))}
        </div>
        <div className="mt-2.5 flex flex-wrap gap-1">
          {p.actions.map((a) => (
            <button
              key={a.label}
              type="button"
              onClick={() => toast(`${a.label} · ${p.title}`)}
              className={cn(ACTION, a.primary ? 'text-fg' : 'text-fg-muted hover:text-fg')}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}
