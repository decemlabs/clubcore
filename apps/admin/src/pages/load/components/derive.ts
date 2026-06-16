/**
 * Pure client-side derivation layer for the visits aggregate (Phase 114 / ANL-01).
 *
 * Transforms VisitsReportDailyBucket[] / VisitsReportHourlyBucket[] — already
 * Zod-validated by useLoad — into three analytics shapes consumed by the Load page
 * widgets. No React, no side effects, no API calls.
 *
 * No-NaN guarantee: every average/ratio is guarded by a zero-denominator check;
 * every argmax has an all-zero early-out. Empty inputs always return zero-filled
 * buckets, never NaN or Infinity.
 *
 * MSK-safe: date-only strings ('YYYY-MM-DD') are parsed via parseISO (local
 * midnight) per CLAUDE.md — NEVER new Date(dateOnlyString) which has a DST risk.
 */
import { parseISO } from 'date-fns';
import type { VisitsReportDailyBucket, VisitsReportHourlyBucket } from '@/features/reports/schemas';

// ---------------------------------------------------------------------------
// Day-of-week breakdown
// ---------------------------------------------------------------------------

/** Russian Mon-first weekday labels. */
const DOW_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'] as const;

export interface DayOfWeekStat {
  /** 0 = Пн … 6 = Вс */
  weekday: number;
  /** Russian abbreviation: 'Пн', 'Вт', … */
  label: string;
  /** Sum of visit counts across all days that fall on this weekday. */
  total: number;
  /** Number of calendar days in the range that mapped to this weekday. */
  daysWithData: number;
  /**
   * Average visits per occurrence of this weekday.
   * Guarded: 0 when daysWithData === 0 (never NaN).
   */
  avgPerWeekday: number;
}

/**
 * Groups the daily visit buckets by MSK-safe weekday (Mon-first).
 *
 * Returns exactly 7 zero-filled buckets. Empty input → all totals and averages
 * are 0. No NaN can appear because the divide is guarded.
 */
export function deriveDayOfWeek(daily: VisitsReportDailyBucket[]): DayOfWeekStat[] {
  // Initialise 7 zero-filled accumulators (Mon=0 … Sun=6).
  const stats: DayOfWeekStat[] = DOW_LABELS.map((label, weekday) => ({
    weekday,
    label,
    total: 0,
    daysWithData: 0,
    avgPerWeekday: 0,
  }));

  for (const bucket of daily) {
    // parseISO('YYYY-MM-DD') → local midnight — no DST shift (per CLAUDE.md).
    const d = parseISO(bucket.date);
    // getDay(): 0=Sun, 1=Mon … 6=Sat → shift to Mon=0 … Sun=6.
    const dow = (d.getDay() + 6) % 7;
    const stat = stats[dow];
    if (stat === undefined) continue; // noUncheckedIndexedAccess guard
    stat.total += bucket.count;
    stat.daysWithData += 1;
  }

  // Compute averages after accumulation so the guard is applied once per slot.
  for (const stat of stats) {
    stat.avgPerWeekday = stat.daysWithData === 0 ? 0 : stat.total / stat.daysWithData;
  }

  return stats;
}

// ---------------------------------------------------------------------------
// Peak hour
// ---------------------------------------------------------------------------

export interface PeakHour {
  /** 0–23 */
  hour: number;
  /** Visit count at this hour. */
  count: number;
}

/**
 * Returns the busiest hour from the hourly visit buckets.
 *
 * - All counts ≤ 0 (or empty input) → null.
 * - Tie between two equal maxima → the EARLIER hour wins.
 *
 * Order-independent: the tie-break compares the `hour` value, not array index, so
 * SPARSE/unordered input (as the schema documents) yields the correct earlier hour.
 */
export function derivePeakHour(hourly: VisitsReportHourlyBucket[]): PeakHour | null {
  let best: PeakHour | null = null;
  for (const bucket of hourly) {
    if (bucket.count <= 0) continue;
    if (
      best === null ||
      bucket.count > best.count ||
      (bucket.count === best.count && bucket.hour < best.hour)
    ) {
      best = { hour: bucket.hour, count: bucket.count };
    }
  }
  return best;
}

// ---------------------------------------------------------------------------
// Daily-volume frequency distribution
// ---------------------------------------------------------------------------

/**
 * Fixed range definitions for the frequency histogram.
 * Labels use en-dash (U+2013) per the UI-SPEC Copywriting Contract.
 */
const FREQ_RANGES: ReadonlyArray<{ label: string; max: number }> = [
  { label: '0–4', max: 5 },
  { label: '5–9', max: 10 },
  { label: '10–14', max: 15 },
  { label: '15–19', max: 20 },
  { label: '20–24', max: 25 },
  { label: '25+', max: Infinity },
];

export interface FrequencyBucket {
  /** Range label, e.g. '0–4', '25+'. Uses en-dash (U+2013). */
  label: string;
  /** Number of calendar days whose visit count fell in this range. */
  count: number;
}

/**
 * Buckets the daily visit counts into 6 fixed visit-volume ranges.
 *
 * Answers "how many days had N visits?" — a histogram of daily load.
 * Returns exactly 6 zero-filled buckets. Empty input → all counts 0.
 */
export function deriveFrequency(daily: VisitsReportDailyBucket[]): FrequencyBucket[] {
  const buckets: FrequencyBucket[] = FREQ_RANGES.map(({ label }) => ({ label, count: 0 }));

  for (const day of daily) {
    const idx = FREQ_RANGES.findIndex((r) => day.count < r.max);
    // findIndex returns -1 only when no range matches; the last range has max=Infinity
    // so this can never happen. Guard added for noUncheckedIndexedAccess safety.
    const bucket = buckets[idx === -1 ? buckets.length - 1 : idx];
    if (bucket !== undefined) {
      bucket.count += 1;
    }
  }

  return buckets;
}
