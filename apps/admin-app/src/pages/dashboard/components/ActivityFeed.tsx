import { useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  Check,
  CircleX,
  Clock,
  CreditCard,
  SquareCheckBig,
  TriangleAlert,
  UserPlus,
} from '@/components/icons';
import type {
  ActivityCategory,
  ActivityEvent,
  ActivityFeedData,
  ActivityType,
} from '@/features/dashboard/types';
import { DashboardCard, MiniSegmented, type MiniSegmentedOption } from './shared';

const ICONS: Record<ActivityType, LucideIcon> = {
  checkin: SquareCheckBig,
  payment: CreditCard,
  training: Check,
  cancel: CircleX,
  alert: TriangleAlert,
  signup: UserPlus,
  expire: Clock,
};

const ICON_BG: Record<ActivityType, string> = {
  checkin: 'bg-fg text-bg dark:bg-surface-3 dark:text-fg',
  payment: 'bg-primary-deep text-white dark:bg-primary dark:text-[#06120c]',
  training: 'bg-[#6366f1]',
  cancel: 'bg-danger',
  alert: 'bg-[#e9a23b]',
  signup: 'bg-[#ec4899]',
  expire: 'bg-fg-muted',
};

const CATEGORY: Record<ActivityType, ActivityCategory> = {
  checkin: 'checkin',
  signup: 'checkin',
  payment: 'payment',
  training: 'training',
  cancel: 'training',
  alert: 'alert',
  expire: 'alert',
};

type FilterValue = 'all' | ActivityCategory;

const FILTER_OPTIONS: MiniSegmentedOption<FilterValue>[] = [
  { value: 'all', label: 'Все' },
  { value: 'checkin', label: 'Чек-ины' },
  { value: 'payment', label: 'Оплаты' },
  { value: 'training', label: 'Тренировки' },
  { value: 'alert', label: 'Алерты' },
];

function eventsLabel(n: number): string {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return `${n} событие`;
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return `${n} события`;
  return `${n} событий`;
}

function ActivityRow({ event }: { event: ActivityEvent }) {
  const Icon = ICONS[event.type];
  return (
    <div className="grid grid-cols-[32px_1fr_auto] items-center gap-3 border-b-[0.5px] border-border px-5 py-3 transition-colors last:border-b-0 hover:bg-surface-2 sm:grid-cols-[36px_1fr_auto] sm:gap-3.5">
      <span
        className={cn(
          'grid size-8 place-items-center rounded-[9px] text-white sm:size-9 sm:rounded-[11px]',
          ICON_BG[event.type],
        )}
      >
        <Icon className="size-[14px]" strokeWidth={2.4} />
      </span>

      <div className="flex min-w-0 flex-col gap-px">
        <div className="truncate text-[13px] font-semibold tracking-[-0.1px]">{event.title}</div>
        <div className="truncate text-[11.5px] text-fg-subtle">
          {event.subLead}
          {event.amount ? (
            <span className="font-[650] tabular-nums text-primary-deep dark:text-primary">
              {event.amount}
            </span>
          ) : null}
          {event.danger ? <span className="font-[650] text-danger">{event.danger}</span> : null}
        </div>
      </div>

      <span className="shrink-0 whitespace-nowrap text-[11px] font-medium tabular-nums text-fg-subtle">
        {event.timeLabel}
      </span>
    </div>
  );
}

export function ActivityFeed({ data }: { data: ActivityFeedData }) {
  const [filter, setFilter] = useState<FilterValue>('all');

  const visible = data.events.filter((e) => filter === 'all' || CATEGORY[e.type] === filter);

  return (
    <DashboardCard
      title="Активность"
      titleExtra={
        <span className="relative ml-2 inline-flex size-[7px] -translate-y-px">
          <span className="absolute inset-0 animate-ping rounded-full bg-primary opacity-60" />
          <span className="relative inline-flex size-[7px] rounded-full bg-primary" />
        </span>
      }
      subtitle={data.subtitle}
      action={
        <MiniSegmented
          options={FILTER_OPTIONS}
          value={filter}
          onChange={setFilter}
          ariaLabel="Фильтр активности"
          className="max-w-full overflow-x-auto [scrollbar-width:none]"
        />
      }
    >
      <div
        className="max-h-[360px] overflow-y-auto border-t-[0.5px] border-border"
        role="log"
        aria-live="polite"
      >
        {visible.length > 0 ? (
          visible.map((event) => <ActivityRow key={event.id} event={event} />)
        ) : (
          <div className="px-5 py-10 text-center">
            <div className="text-[13px] font-semibold">Тут пока тихо</div>
            <div className="mt-1 text-xs text-fg-subtle">
              За последний час по этому фильтру ничего не было
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between rounded-b-lg border-t-[0.5px] border-border bg-surface-2 px-5 py-2.5 text-[11.5px] text-fg-subtle">
        <span className="tabular-nums">{eventsLabel(data.events.length)}</span>
      </div>
    </DashboardCard>
  );
}
