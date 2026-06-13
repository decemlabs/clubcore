import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { FileText, Lock, MessageSquare, User } from '@/components/icons';
import type {
  ActivityEvent,
  ActivityKind,
  ActivityTone,
  ClientDetail,
} from '@/features/clients/detail';
import { Card, MiniButton, RichText } from './shared';

const MARKER_ICON: Record<ActivityKind, LucideIcon> = {
  checkin: Lock,
  chat: MessageSquare,
  training: User,
  note: FileText,
};

const MARKER_TONE: Record<ActivityTone, string> = {
  default: 'bg-surface-3 text-fg-muted',
  accent: 'bg-primary-soft text-primary-deep dark:text-primary',
  warn: 'bg-warning-soft text-warning-deep',
  note: 'bg-lead-soft text-lead',
};

function TimelineRow({ event }: { event: ActivityEvent }) {
  const Icon = MARKER_ICON[event.kind];
  return (
    <div className="grid grid-cols-[44px_28px_1fr] items-start gap-2.5 border-t-[0.5px] border-border px-4 py-3 sm:grid-cols-[50px_32px_1fr] sm:gap-3 sm:px-5">
      <div className="pt-1.5 text-xs font-semibold tabular-nums tracking-[-0.1px] text-fg-muted">
        {event.time}
      </div>
      <div
        className={cn(
          'mt-[3px] grid size-7 place-items-center rounded-full',
          MARKER_TONE[event.tone],
        )}
      >
        <Icon className="size-[13px]" strokeWidth={2.4} />
      </div>
      <div className="min-w-0">
        <div className="text-[13.5px] font-semibold leading-[1.3] tracking-[-0.1px]">
          <RichText value={event.title} />
        </div>
        {event.sub ? (
          <div className="mt-0.5 text-xs text-fg-muted">
            <RichText value={event.sub} />
          </div>
        ) : null}
        {event.quote ? (
          <div className="mt-1.5 rounded-r-lg border-l-2 border-border-strong bg-surface-2 px-3 py-2 text-[13px] italic leading-snug text-fg-muted">
            {event.quote}
          </div>
        ) : null}
        {event.action ? (
          <div className="mt-2 flex items-center gap-2.5">
            <MiniButton>{event.action.button}</MiniButton>
            <span className="text-xs text-fg-subtle">{event.action.note}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function ActivityTab({ activity }: { activity: ClientDetail['activity'] }) {
  return (
    <Card className="pb-2">
      {activity.groups.map((group, gi) => (
        <div key={group.day}>
          <div
            className={cn(
              'bg-surface-2 px-5 pb-1.5 pt-3 text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle',
              gi > 0 && 'border-t-[0.5px] border-border',
            )}
          >
            {group.day}
          </div>
          {group.events.map((event) => (
            <TimelineRow key={event.id} event={event} />
          ))}
        </div>
      ))}
      <button
        type="button"
        className="w-full border-t-[0.5px] border-border py-3.5 text-[12.5px] font-semibold text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
      >
        {activity.moreLabel}
      </button>
    </Card>
  );
}
