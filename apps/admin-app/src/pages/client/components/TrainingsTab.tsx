import { useState } from 'react';
import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import type { TrainingItem, TrainingsTabData, TrainingType } from '@/features/clients/detail';
import { Card, CardHead, RichText } from './shared';

type Filter = 'all' | TrainingType;

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'personal', label: 'Персональные' },
  { value: 'group', label: 'Групповые' },
];

function TrainingRow({ item }: { item: TrainingItem }) {
  return (
    <div className="grid grid-cols-[44px_28px_1fr] items-start gap-x-3 gap-y-1 border-t-[0.5px] border-border px-4 py-3.5 first:border-t-0 sm:px-5 @[520px]:grid-cols-[48px_32px_1fr_auto] @[520px]:gap-3.5">
      <div className="rounded-[10px] bg-surface-2 py-1.5 text-center">
        <div className="text-[17px] font-bold leading-none tabular-nums tracking-[-0.4px]">
          {item.day}
        </div>
        <div className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.4px] text-fg-subtle">
          {item.month}
        </div>
      </div>
      <Initials
        initials={item.trainerInitials}
        color={item.trainerColor}
        className="size-8 text-xs"
      />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 text-sm font-semibold tracking-[-0.1px]">
          {item.title}
          <span className="rounded-full bg-surface-3 px-[7px] py-0.5 text-[10.5px] font-semibold text-fg-muted">
            {item.tag}
          </span>
        </div>
        <div className="mt-[3px] text-xs text-fg-muted">
          <RichText value={item.meta} />
        </div>
        <div className="mt-1.5 text-[12.5px] italic text-fg-muted">{item.note}</div>
      </div>
      <div className="whitespace-nowrap pt-1 text-sm font-bold tabular-nums tracking-[-0.2px] @max-[520px]:col-span-3 @max-[520px]:pt-0 @max-[520px]:text-right">
        {item.amount}
      </div>
    </div>
  );
}

export function TrainingsTab({ data }: { data: TrainingsTabData }) {
  const [filter, setFilter] = useState<Filter>('all');
  const items = data.items.filter((i) => filter === 'all' || i.type === filter);

  return (
    <Card>
      <CardHead
        title={data.title}
        sub={data.sub}
        action={
          <div className="inline-flex gap-px rounded-full bg-surface-3 p-0.5">
            {FILTERS.map((f) => {
              const active = f.value === filter;
              return (
                <button
                  key={f.value}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setFilter(f.value)}
                  className={cn(
                    'h-[22px] rounded-full px-[9px] text-[11.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    active ? 'bg-surface text-fg shadow-1' : 'text-fg-muted hover:text-fg',
                  )}
                >
                  {f.label}
                </button>
              );
            })}
          </div>
        }
      />
      <div className="border-t-[0.5px] border-border">
        {items.length > 0 ? (
          items.map((item) => <TrainingRow key={item.id} item={item} />)
        ) : (
          <div className="px-5 py-10 text-center text-[13px] text-fg-subtle">
            Нет тренировок в этой категории
          </div>
        )}
      </div>
      <button
        type="button"
        className="w-full border-t-[0.5px] border-border py-3.5 text-[12.5px] font-semibold text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
      >
        {data.moreLabel}
      </button>
    </Card>
  );
}
