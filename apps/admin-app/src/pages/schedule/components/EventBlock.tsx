import { cn } from '@/lib/cn';
import type { SessionEvent } from '@/features/schedule/types';
import type { LaidOutEvent } from './calendar-utils';

/** Блок-событие в колонке дня: время + тег состояния + кто/фокус + заметка. */
export function EventBlock({
  item,
  color,
  onClick,
}: {
  item: LaidOutEvent;
  color: string;
  onClick?: (ev: SessionEvent) => void;
}) {
  const { ev, top, height, leftPct, widthPct } = item;
  const past = ev.state === 'past';
  const live = ev.state === 'live';
  const cancelled = ev.state === 'cancelled';

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick?.(ev);
      }}
      style={{
        top,
        height,
        left: `calc(${leftPct}% + 3px)`,
        width: `calc(${widthPct}% - 6px)`,
        borderLeft: `3px solid ${color}`,
        background: `color-mix(in oklab, ${color} 15%, var(--surface))`,
      }}
      className={cn(
        'absolute z-[2] flex flex-col overflow-hidden rounded-lg px-2 py-1.5 text-left transition-[transform,box-shadow]',
        'hover:z-10 hover:-translate-y-px hover:shadow-2 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        past && 'opacity-50 saturate-[0.7] hover:opacity-100',
        cancelled && 'opacity-50',
        live && 'z-[5] shadow-2 ring-2 ring-primary',
      )}
    >
      {ev.kind === 'group' && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background: `repeating-linear-gradient(45deg, color-mix(in oklab, ${color} 24%, transparent) 0 1px, transparent 1px 6px)`,
          }}
        />
      )}

      <div className="relative flex items-center gap-1.5">
        <span className="text-[10.5px] font-bold tabular-nums" style={{ color }}>
          {ev.start}–{ev.end}
        </span>
        {live && (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary px-1.5 py-px text-[8.5px] font-bold uppercase tracking-[0.3px] text-[#06120c]">
            <span className="size-1 animate-pulse rounded-full bg-[#06120c]" />
            идёт
          </span>
        )}
        {cancelled && (
          <span
            className="rounded-full bg-fg/10 px-1.5 py-px text-[8.5px] font-bold uppercase tracking-[0.3px]"
            style={{ color }}
          >
            отменена
          </span>
        )}
      </div>

      <div
        className={cn(
          'relative mt-0.5 line-clamp-2 text-[11.5px] leading-tight',
          cancelled && 'line-through',
        )}
        style={cancelled ? { color } : undefined}
      >
        <b className="font-semibold text-fg">{ev.who}</b>
        {ev.focus ? <span className="text-fg-muted"> · {ev.focus}</span> : null}
      </div>

      {ev.note ? (
        <div className="relative mt-0.5 text-[10.5px] italic text-fg-muted">{ev.note}</div>
      ) : null}
    </button>
  );
}
