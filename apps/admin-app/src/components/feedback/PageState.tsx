import { RefreshCw } from '@/components/icons';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from './EmptyState';

/** Скелет страницы на время первичной загрузки данных. */
export function PageLoading() {
  return (
    <div
      className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pt-6 lg:px-7"
      aria-busy="true"
    >
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-[420px] w-full" />
    </div>
  );
}

/** Ошибка загрузки данных страницы + повтор запроса. */
export function PageError({ onRetry }: { onRetry: () => void }) {
  return (
    <EmptyState
      className="py-24"
      title="Не удалось загрузить данные"
      message="Проверьте соединение и попробуйте ещё раз."
      action={
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex h-9 items-center gap-1.5 rounded-[10px] border-[0.5px] border-border-strong bg-surface px-3.5 text-[13px] font-semibold transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <RefreshCw className="size-3.5" />
          Повторить
        </button>
      }
    />
  );
}
