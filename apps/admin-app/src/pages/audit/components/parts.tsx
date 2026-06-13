/**
 * Audit page shared components (Phase 104-03).
 *
 * RealAuditRow — row component for the real API AuditEvent shape.
 * ActionIcon   — action-type icon chip (also used by AuditDetailModal).
 * LegacyAuditRow — preserved for compatibility (legacy mock shape).
 */
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  Plus,
  SquarePen,
  Trash2,
  LogIn,
  ChevronRight,
  LogOut,
} from '@/components/icons';
import type { AuditEvent } from '@/features/audit/schemas';
import { formatTime } from '@/lib/format';
import { ACTION_LABEL, type AuditAction, type AuditEvent as LegacyAuditEvent } from '@/features/audit/types';

// ---------------------------------------------------------------------------
// ActionIcon — action-type icon chip
// ---------------------------------------------------------------------------

/** Map real action strings to icon/colour. Unknown actions fall back to neutral. */
function getActionStyle(action: string): { icon: LucideIcon; cls: string } {
  switch (action) {
    case 'create':
      return { icon: Plus, cls: 'bg-primary-soft text-primary-deep dark:text-primary' };
    case 'update':
    case 'edit':
      return { icon: SquarePen, cls: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-300' };
    case 'delete':
      return { icon: Trash2, cls: 'bg-danger-soft text-danger' };
    case 'login':
      return { icon: LogIn, cls: 'bg-surface-3 text-fg-muted' };
    case 'logout':
      return { icon: LogOut, cls: 'bg-surface-3 text-fg-muted' };
    default:
      return { icon: SquarePen, cls: 'bg-surface-3 text-fg-muted' };
  }
}

/** Иконка действия (тон по типу события). */
export function ActionIcon({ action, size = 'sm' }: { action: string; size?: 'sm' | 'lg' }) {
  const { icon: Icon, cls } = getActionStyle(action);
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

// ---------------------------------------------------------------------------
// Action labels for real API actions
// ---------------------------------------------------------------------------

const REAL_ACTION_LABEL: Record<string, string> = {
  create: 'Создание',
  update: 'Изменение',
  edit: 'Изменение',
  delete: 'Удаление',
  login: 'Вход',
  logout: 'Выход',
};

function getActionLabel(action: string): string {
  return REAL_ACTION_LABEL[action] ?? action;
}

// ---------------------------------------------------------------------------
// RealAuditRow — row component for real API AuditEvent
// ---------------------------------------------------------------------------

/**
 * Дата-группирующий заголовок (e.g. «Сегодня, 13 июня»).
 * UI-SPEC §3.2: text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle.
 */
export function AuditDateGroup({ label }: { label: string }) {
  return (
    <div className="px-[18px] pb-1 pt-3.5 text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
      {label}
    </div>
  );
}

/**
 * Real audit row — uses the API AuditEvent shape from schemas.ts.
 * Initials derived from actorEmailSnapshot (first char uppercase).
 * Time formatted as HH:mm via formatTime.
 * Clicking opens AuditDetailModal.
 */
export function RealAuditRow({
  event,
  onClick,
}: {
  event: AuditEvent;
  onClick: () => void;
}) {
  const initials = event.actorEmailSnapshot.charAt(0).toUpperCase();
  const time = formatTime(event.createdAt);
  const actionLabel = getActionLabel(event.action);
  const resourceIdDisplay = event.resourceId
    ? event.resourceId.length > 16
      ? `${event.resourceId.slice(0, 16)}…`
      : event.resourceId
    : null;

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 border-b-[0.5px] border-border px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:px-[18px]"
    >
      {/* Initials circle */}
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-3 text-[12px] font-semibold text-fg-muted">
        {initials}
      </span>

      {/* Main content */}
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-2">
          <span className="truncate text-[13px] font-semibold text-fg">
            {event.actorEmailSnapshot}
          </span>
          <span
            className="shrink-0 text-[11.5px] tabular-nums text-fg-muted"
            title={event.createdAt}
          >
            {time}
          </span>
        </span>
        <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[12px] text-fg-muted">
          <span>
            {actionLabel}
            {event.resourceType ? ` / ${event.resourceType}` : null}
          </span>
          {resourceIdDisplay ? (
            <span className="max-w-[120px] truncate font-mono text-[11px] text-fg-subtle">
              {resourceIdDisplay}
            </span>
          ) : null}
        </span>
      </span>

      <ChevronRight className="ml-auto size-3.5 shrink-0 text-fg-subtle max-sm:hidden" />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Legacy AuditRow — preserved for compatibility (mock-era shape)
// ---------------------------------------------------------------------------

/** @deprecated Phase 104-01 stub — use RealAuditRow for real API data. */
export function AuditRow({
  event,
  onClick,
}: {
  event: LegacyAuditEvent;
  onClick: () => void;
}) {
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
            {ACTION_LABEL[event.action as AuditAction]}
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
