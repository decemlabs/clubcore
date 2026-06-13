/**
 * DateRangePicker — reusable from/to date filter (Phase 103-03).
 *
 * Shared by Cashbox, Load, and Finance pages (owner-only screens).
 * Default range: last 30 days (toDate=today, fromDate=today-29 days).
 *
 * Validation (client-side, fires on blur before query):
 *   - inverted range (to < from) → inline error; query NOT fired
 *   - span > 365 days → inline error; query NOT fired
 *   - valid range → fire onChange; error cleared
 *
 * Uses date-fns `differenceInCalendarDays` for span check.
 * Native <input type="date"> — no date picker library (no new dep).
 */
import { useEffect, useState } from 'react';
import { differenceInCalendarDays, parseISO } from 'date-fns';
import { cn } from '@/lib/cn';
import { mskTodayISO } from '@/lib/format';

export interface DateRangePickerProps {
  from: string; // 'YYYY-MM-DD'
  to: string;   // 'YYYY-MM-DD'
  onChange: (from: string, to: string) => void;
  className?: string;
}

/** Validate the range and return an error string or null. */
function validate(from: string, to: string): string | null {
  if (!from || !to) return null;
  const span = differenceInCalendarDays(parseISO(to), parseISO(from));
  if (span < 0) return 'Дата "По" должна быть позже даты "С"';
  if (span > 365) return 'Максимальный период — 365 дней';
  return null;
}

const INPUT_CLASS =
  'h-9 w-full rounded-[10px] border-[0.5px] border-border bg-surface px-3 text-[13px] text-fg focus:outline-none focus:ring-2 focus:ring-primary-soft focus:border-primary';

/**
 * Compact date-range picker: «С» and «По» native date inputs with validation.
 *
 * Fires `onChange` only when the range is valid (both fields blurred or
 * both populated). Inline validation error shown below the inputs.
 */
export function DateRangePicker({ from, to, onChange, className }: DateRangePickerProps) {
  const [localFrom, setLocalFrom] = useState(from);
  const [localTo, setLocalTo] = useState(to);
  const [error, setError] = useState<string | null>(null);
  const today = mskTodayISO();

  // CR-01: Sync external prop changes back to local state (e.g. parent resets range).
  // Guard against feedback loops — effects only fire when the prop value actually changes.
  useEffect(() => {
    setLocalFrom(from);
  }, [from]);

  useEffect(() => {
    setLocalTo(to);
  }, [to]);

  function handleBlur(nextFrom: string, nextTo: string) {
    const err = validate(nextFrom, nextTo);
    setError(err);
    if (!err && nextFrom && nextTo) {
      onChange(nextFrom, nextTo);
    }
  }

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <span className="text-[12.5px] font-semibold text-fg-muted">Период</span>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-[12.5px] font-semibold text-fg-muted">С</span>
          <input
            type="date"
            value={localFrom}
            max={today}
            className={INPUT_CLASS}
            onChange={(e) => setLocalFrom(e.target.value)}
            onBlur={(e) => handleBlur(e.target.value, localTo)}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[12.5px] font-semibold text-fg-muted">По</span>
          <input
            type="date"
            value={localTo}
            min={localFrom}
            max={today}
            className={INPUT_CLASS}
            onChange={(e) => setLocalTo(e.target.value)}
            onBlur={(e) => handleBlur(localFrom, e.target.value)}
          />
        </label>
      </div>
      {error ? (
        <p className="mt-1 text-[12px] text-danger">{error}</p>
      ) : null}
    </div>
  );
}
