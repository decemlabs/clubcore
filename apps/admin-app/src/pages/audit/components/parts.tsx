import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Plus, SquarePen, Trash2, LogIn, ChevronRight } from '@/components/icons';
import { ACTION_LABEL, type AuditAction, type AuditEvent } from '@/features/audit/types';

const ACTION: Record<AuditAction, { icon: LucideIcon; cls: string }> = {
  create: { icon: Plus, cls: 'bg-primary-soft text-primary-deep dark:text-primary' },
  edit: { icon: SquarePen, cls: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-300' },
  delete: { icon: Trash2, cls: 'bg-danger-soft text-danger' },
  login: { icon: LogIn, cls: 'bg-surface-3 text-fg-muted' },
};

/** Иконка действия (тон по типу события). */
export function ActionIcon({ action, size = 'sm' }: { action: AuditAction; size?: 'sm' | 'lg' }) {
  const { icon: Icon, cls } = ACTION[action];
  return (
    <span
      className={cn(
        'grid shrink-0 place-items-center',
        cls,
        size === 'lg' ? 'size-[42px] rounded-xl' : 'size-[30px] rounded-[9px]',
      )}
    >
      <Icon className={size === 'lg' ? 'size-5' : 'size-[15px]'} strokeWidth={2} />
    </span>
  );
}

export function AuditRow({ event, onClick }: { event: AuditEvent; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 border-b-[0.5px] border-border px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:px-[18px]"
    >
      <span className="w-[42px] shrink-0 text-[12px] tabular-nums text-fg-subtle">
        {event.time}
      </span>
      <ActionIcon action={event.action} />
      <span className="min-w-0 flex-1">
        <span className="block text-[13px] leading-snug">
          {event.lead}
          {event.obj ? <b className="font-bold">{event.obj}</b> : null}
          {event.tail}
        </span>
        <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11.5px] text-fg-subtle">
          <span className="inline-flex items-center gap-1.5">
            <span
              style={{ background: event.actor.gradient }}
              className="grid size-4 shrink-0 place-items-center rounded-full text-[8px] font-bold text-white"
            >
              {event.actor.initials}
            </span>
            {event.actor.name}
          </span>
          <span className="rounded-full bg-surface-3 px-[7px] py-px text-[10px] font-bold uppercase tracking-[0.3px] text-fg-muted">
            {ACTION_LABEL[event.action]}
          </span>
        </span>
      </span>
      <span className="ml-auto hidden items-center gap-3 sm:flex">
        <span className="whitespace-nowrap font-mono text-[11px] text-fg-subtle">{event.ip}</span>
        <ChevronRight className="size-3.5 text-fg-subtle" />
      </span>
    </button>
  );
}
