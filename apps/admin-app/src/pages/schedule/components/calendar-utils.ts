/**
 * Геометрия и раскладка недельного календаря (вынесено из компонентов ради react-refresh).
 */
import type { SessionEvent } from '@/features/schedule/types';

export const START_HOUR = 7;
export const END_HOUR = 23;
export const HOUR_PX = 56;
/** Часовые метки 7:00…23:00. */
export const HOURS = Array.from({ length: END_HOUR - START_HOUR + 1 }, (_, i) => START_HOUR + i);
/** Высота тела календаря (16 интервалов × 56px + хвост). */
export const BODY_HEIGHT = (END_HOUR - START_HOUR) * HOUR_PX + 16;

/** Минуты от 07:00 для строки «HH:MM». */
export function toMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number);
  return (h ?? 0) * 60 + (m ?? 0) - START_HOUR * 60;
}

export interface LaidOutEvent {
  ev: SessionEvent;
  top: number;
  height: number;
  /** Левый отступ в % (для раскладки пересекающихся событий в колонки). */
  leftPct: number;
  widthPct: number;
}

interface Span {
  ev: SessionEvent;
  start: number;
  end: number;
}

/**
 * Раскладка событий одного дня: пересекающиеся по времени делят колонку
 * по горизонтали (жадная упаковка в дорожки внутри кластера пересечений).
 */
export function layoutDay(events: SessionEvent[]): LaidOutEvent[] {
  const spans: Span[] = events.map((ev) => {
    const start = toMinutes(ev.start);
    return { ev, start, end: start + ev.durationMin };
  });
  spans.sort((a, b) => a.start - b.start || b.end - a.end);

  const out: LaidOutEvent[] = [];
  let cluster: Span[] = [];
  let clusterEnd = -1;

  const flush = () => {
    if (cluster.length === 0) return;
    const colEnds: number[] = [];
    const colOf = new Map<Span, number>();
    for (const span of cluster) {
      let col = colEnds.findIndex((end) => end <= span.start);
      if (col === -1) {
        col = colEnds.length;
        colEnds.push(span.end);
      } else {
        colEnds[col] = span.end;
      }
      colOf.set(span, col);
    }
    const cols = colEnds.length;
    for (const span of cluster) {
      const col = colOf.get(span) ?? 0;
      out.push({
        ev: span.ev,
        top: (span.start * HOUR_PX) / 60,
        height: (span.ev.durationMin * HOUR_PX) / 60,
        leftPct: (col / cols) * 100,
        widthPct: 100 / cols,
      });
    }
    cluster = [];
  };

  for (const span of spans) {
    if (cluster.length > 0 && span.start >= clusterEnd) {
      flush();
      clusterEnd = -1;
    }
    cluster.push(span);
    clusterEnd = Math.max(clusterEnd, span.end);
  }
  flush();
  return out;
}
