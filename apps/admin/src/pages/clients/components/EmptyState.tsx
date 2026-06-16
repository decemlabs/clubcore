import { Search } from '@/components/icons';
import { EmptyState as BaseEmptyState } from '@/components/feedback/EmptyState';

export function EmptyState({ onReset }: { onReset: () => void }) {
  return (
    <BaseEmptyState
      icon={Search}
      title="Ничего не найдено"
      message="Под текущие фильтры нет клиентов. Попробуйте изменить запрос."
      action={
        <button
          type="button"
          onClick={onReset}
          className="mt-1 inline-flex h-9 items-center rounded-full bg-fg px-4 text-[13px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
        >
          Сбросить фильтры
        </button>
      }
    />
  );
}
