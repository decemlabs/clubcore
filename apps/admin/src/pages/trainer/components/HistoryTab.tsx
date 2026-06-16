import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Check, CircleX, SquarePen, Users, Wallet } from '@/components/icons';
import type { TimelineGroup, TimelineItem, TimelineKind } from '@/features/trainers/detail';
import { Panel, PanelBody, PanelHead, RichText } from './shared';

const ICON: Record<TimelineKind, LucideIcon> = {
  check: Check,
  client: Users,
  cancel: CircleX,
  payout: Wallet,
  rate: SquarePen,
  join: Check,
};

const DOT: Record<TimelineItem['tone'], string> = {
  accent: 'border-transparent bg-primary-soft text-primary-deep dark:text-primary',
  warn: 'border-transparent bg-warning-soft text-warning-deep',
  default: 'border-border-strong bg-surface text-fg-subtle',
};

export function HistoryTab({ groups }: { groups: TimelineGroup[] }) {
  return (
    <Panel>
      <PanelHead title="История активности" />
      <PanelBody>
        {groups.map((g) => (
          <div key={g.day}>
            <div className="mb-3.5 mt-1 text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
              {g.day}
            </div>
            <div className="relative mb-1 pl-[30px] before:absolute before:bottom-1 before:left-[9px] before:top-1 before:w-[1.5px] before:bg-border before:content-['']">
              {g.items.map((it) => {
                const Icon = ICON[it.kind];
                return (
                  <div key={it.id} className="relative pb-5 last:pb-0.5">
                    <span
                      className={cn(
                        'absolute -left-[30px] top-px grid size-5 place-items-center rounded-full border-[1.5px]',
                        DOT[it.tone],
                      )}
                    >
                      <Icon className="size-[11px]" strokeWidth={2.4} />
                    </span>
                    <div className="text-[13px] font-semibold tracking-[-0.1px]">
                      <RichText value={it.title} />
                    </div>
                    <div className="mt-0.5 text-[11.5px] tabular-nums text-fg-subtle">
                      {it.time}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </PanelBody>
    </Panel>
  );
}
