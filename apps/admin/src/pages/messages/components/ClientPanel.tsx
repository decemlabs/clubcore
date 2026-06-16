import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import { useModals } from '@/components/modals/modals-context';
import { Banknote, Calendar, ChevronRight, Clock, Phone, Star } from '@/components/icons';
import type { ClientPanelData, UpcomingRow } from '@/features/messages/types';

const QUICK: { icon: LucideIcon; label: string }[] = [
  { icon: Phone, label: 'Звонок' },
  { icon: Calendar, label: 'Записать' },
  { icon: Clock, label: 'Заморозить' },
];

function SectionLabel({
  children,
  link,
  onClick,
}: {
  children: ReactNode;
  link: string;
  onClick?: () => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[10.5px] font-semibold uppercase tracking-[0.4px] text-fg-subtle">
        {children}
      </span>
      <button
        type="button"
        onClick={onClick}
        className="inline-flex items-center gap-0.5 rounded text-[11.5px] font-semibold text-fg-muted transition-colors hover:text-fg"
      >
        {link}
        <ChevronRight className="size-3" strokeWidth={2.4} />
      </button>
    </div>
  );
}

function UpcomingItem({ u }: { u: UpcomingRow }) {
  const Icon = u.icon === 'star' ? Star : Banknote;
  return (
    <div className="flex items-center gap-3 rounded-xl border-[0.5px] border-border bg-surface px-3 py-2.5">
      <span
        className={cn(
          'grid size-8 shrink-0 place-items-center rounded-lg',
          u.ok
            ? 'bg-primary-soft text-primary-deep dark:text-primary'
            : 'bg-surface-3 text-fg-muted',
        )}
      >
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[12.5px] font-semibold">{u.title}</div>
        <div className="truncate text-[11px] text-fg-subtle">{u.sub}</div>
      </div>
      <span className="whitespace-nowrap text-[11px] font-semibold text-fg-muted">{u.right}</span>
    </div>
  );
}

/** Правая колонка инбокса: профиль клиента, абонемент, ближайшее. */
export function ClientPanel({
  client,
  className,
}: {
  client: ClientPanelData;
  className?: string;
}) {
  const { open } = useModals();
  const onQuick = (label: string) => {
    if (label === 'Записать') open('book');
    else if (label === 'Заморозить') open('subscription', { subscription: { screen: 'freeze' } });
    else toast(`Звонок · ${client.name}`);
  };
  return (
    <div
      className={cn(
        'flex min-h-0 flex-col overflow-y-auto border-l-[0.5px] border-border bg-surface-2',
        className,
      )}
    >
      <div className="flex flex-col items-center border-b-[0.5px] border-border bg-surface px-5 py-5 text-center">
        <Initials
          initials={client.initials}
          color={client.gradient}
          className="size-14 text-[18px]"
        />
        <div className="mt-2.5 text-[16px] font-bold">{client.name}</div>
        <div className="mt-0.5 text-[12px] text-fg-subtle">{client.ptag}</div>
        <div className="mt-2.5 flex flex-wrap justify-center gap-1.5">
          {client.chips.map((c) => (
            <span
              key={c.label}
              className={cn(
                'rounded-full px-2.5 py-1 text-[11px] font-semibold',
                c.ok
                  ? 'bg-primary-soft text-primary-deep dark:text-primary'
                  : 'bg-surface-3 text-fg-muted',
              )}
            >
              {c.label}
            </span>
          ))}
        </div>
        <div className="mt-3 grid w-full grid-cols-3 gap-2">
          {QUICK.map(({ icon: Icon, label }) => (
            <button
              key={label}
              type="button"
              onClick={() => onQuick(label)}
              className="flex flex-col items-center gap-1 rounded-lg border-[0.5px] border-border bg-surface py-2 text-[11px] font-semibold text-fg-muted transition-colors hover:border-border-strong hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Icon className="size-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="border-b-[0.5px] border-border px-5 py-4">
        <SectionLabel
          link="открыть →"
          onClick={() => open('subscription', { subscription: { screen: 'edit' } })}
        >
          Абонемент
        </SectionLabel>
        <div className="mt-2 rounded-xl border-[0.5px] border-border bg-surface p-3.5">
          <div className="text-[14px] font-bold">{client.plan.name}</div>
          <div className="mt-0.5 text-[11.5px] text-fg-subtle">{client.plan.sub}</div>
          <div className="mt-2.5 flex flex-col gap-1.5">
            {client.plan.rows.map((r) => (
              <div key={r.label} className="flex items-center justify-between text-[11.5px]">
                <span className="text-fg-muted">{r.label}</span>
                <span>
                  <b className="font-semibold text-fg">{r.value}</b>
                  {r.note ? <span className="text-fg-subtle"> {r.note}</span> : null}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-surface-3">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${client.plan.barPct}%` }}
            />
          </div>
        </div>
      </div>

      <div className="px-5 py-4">
        <SectionLabel link="всё →" onClick={() => toast('Ближайшие события клиента')}>
          Ближайшее
        </SectionLabel>
        <div className="mt-2 flex flex-col gap-2">
          {client.upcoming.map((u) => (
            <UpcomingItem key={u.title} u={u} />
          ))}
        </div>
      </div>
    </div>
  );
}
