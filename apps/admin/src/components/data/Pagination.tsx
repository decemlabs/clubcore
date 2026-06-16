import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { ChevronLeft, ChevronRight } from '@/components/icons';

const PG_BTN =
  'inline-grid h-[30px] min-w-[30px] place-items-center rounded-lg border-[0.5px] border-border bg-surface px-2 text-[12.5px] font-semibold tabular-nums text-fg transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40';

/** Окно номеров страниц с эллипсисами: 1 … (page-1, page, page+1) … last. */
function pageRange(page: number, pageCount: number): (number | 'gap')[] {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, i) => i + 1);
  const window: number[] = [];
  for (let p = Math.max(2, page - 1); p <= Math.min(pageCount - 1, page + 1); p++) window.push(p);
  const items: (number | 'gap')[] = [1];
  if (window.length > 0 && window[0]! > 2) items.push('gap');
  items.push(...window);
  if (window.length > 0 && window[window.length - 1]! < pageCount - 1) items.push('gap');
  items.push(pageCount);
  return items;
}

export interface PaginationProps {
  page: number;
  pageCount: number;
  /** Если не задан — номера страниц инертны (бэкенд ещё не пагинирует). */
  onPageChange?: (page: number) => void;
  /** Левая сводка «Показано X—Y из Z {noun}». */
  shown?: number;
  total?: number;
  noun?: string;
  /** Кастомная сводка вместо стандартной. */
  summary?: ReactNode;
  className?: string;
}

/** Пагинация: сводка слева + окно номеров с эллипсисами и стрелками справа. */
export function Pagination({
  page,
  pageCount,
  onPageChange,
  shown,
  total,
  noun,
  summary,
  className,
}: PaginationProps) {
  const items = pageRange(page, pageCount);
  const go = (p: number) => {
    if (onPageChange && p >= 1 && p <= pageCount) onPageChange(p);
  };

  const defaultSummary =
    shown != null && total != null ? (
      <span className="tabular-nums">
        Показано <b className="font-semibold text-fg">{shown === 0 ? 0 : `1 — ${shown}`}</b> из{' '}
        <b className="font-semibold text-fg">{total}</b>
        {noun ? ` ${noun}` : null}
      </span>
    ) : null;

  return (
    <div
      className={cn(
        'flex items-center gap-2 border-t-[0.5px] border-border bg-surface px-4 py-3.5 text-[12.5px] text-fg-muted max-sm:flex-wrap',
        className,
      )}
    >
      {summary ?? defaultSummary}

      <div className="ml-auto flex items-center gap-1">
        <button
          type="button"
          className={PG_BTN}
          disabled={page === 1}
          onClick={onPageChange ? () => go(page - 1) : undefined}
          aria-label="Назад"
        >
          <ChevronLeft className="size-3" strokeWidth={2.4} />
        </button>
        {items.map((item, i) =>
          item === 'gap' ? (
            <span key={`gap-${i}`} className="px-1 text-fg-subtle">
              …
            </span>
          ) : (
            <button
              key={item}
              type="button"
              aria-current={item === page ? 'page' : undefined}
              onClick={onPageChange ? () => go(item) : undefined}
              className={cn(PG_BTN, item === page && 'border-fg bg-fg text-bg hover:bg-fg')}
            >
              {item}
            </button>
          ),
        )}
        <button
          type="button"
          className={PG_BTN}
          disabled={page === pageCount}
          onClick={onPageChange ? () => go(page + 1) : undefined}
          aria-label="Вперёд"
        >
          <ChevronRight className="size-3" strokeWidth={2.4} />
        </button>
      </div>
    </div>
  );
}
