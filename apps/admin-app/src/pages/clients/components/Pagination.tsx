import { cn } from '@/lib/cn';
import { ChevronLeft, ChevronRight } from '@/components/icons';

const PG_BTN =
  'inline-grid h-[30px] min-w-[30px] place-items-center rounded-lg border-[0.5px] border-border bg-surface px-2 text-[12.5px] font-semibold tabular-nums text-fg transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40';

/**
 * Пагинация. Презентационная (страница ведётся бэкендом) — активна стр. 1,
 * номера-кнопки получают состояния hover/active/disabled.
 */
export function Pagination({
  shownCount,
  totalCount,
  totalPages,
  currentPage,
}: {
  shownCount: number;
  totalCount: number;
  totalPages: number;
  currentPage: number;
}) {
  const pages = [1, 2, 3, 4].filter((p) => p < totalPages);
  return (
    <div className="flex items-center gap-2 border-t-[0.5px] border-border bg-surface px-4 py-3.5 text-[12.5px] text-fg-muted max-sm:flex-wrap">
      <span className="tabular-nums">
        Показано{' '}
        <b className="font-semibold text-fg">{shownCount === 0 ? 0 : `1 — ${shownCount}`}</b> из{' '}
        <b className="font-semibold text-fg">{totalCount}</b> клиентов
      </span>

      <div className="ml-auto flex items-center gap-1">
        <button type="button" className={PG_BTN} disabled={currentPage === 1} aria-label="Назад">
          <ChevronLeft className="size-3" strokeWidth={2.4} />
        </button>
        {pages.map((p) => (
          <button
            key={p}
            type="button"
            aria-current={p === currentPage ? 'page' : undefined}
            className={cn(PG_BTN, p === currentPage && 'border-fg bg-fg text-bg hover:bg-fg')}
          >
            {p}
          </button>
        ))}
        <span className="px-1 text-fg-subtle">…</span>
        <button type="button" className={PG_BTN}>
          {totalPages}
        </button>
        <button type="button" className={PG_BTN} aria-label="Вперёд">
          <ChevronRight className="size-3" strokeWidth={2.4} />
        </button>
      </div>
    </div>
  );
}
