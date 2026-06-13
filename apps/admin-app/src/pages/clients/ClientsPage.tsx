/**
 * Clients list page — wired to real GET /api/v1/clients (Phase 101 CLI-01).
 *
 * Changes from mock version:
 *  - useClients(filter) over staffRequest (server search + server pagination)
 *  - Search: debounced 300ms, min-2-char gate (q<2 → not sent, list unchanged)
 *  - Pagination: server-side {items,total,page,pageSize}; page synced to URL ?page=N
 *  - Filters: backend-supported only — gender, hasTelegram, tag, sort
 *  - REMOVED: ClientFilterTabs (membership-status), planType, trainer, «Ещё фильтры»,
 *    unsupported sort presets (expires/visits/last)
 *  - Two distinct empty states: zero-clients vs filter-empty
 */
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useClients } from '@/features/clients/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { useDebounce } from '@/lib/useDebounce';
import { Pagination } from '@/components/data/Pagination';
import { Users, Search, UserPlus } from '@/components/icons';
import { useModals } from '@/components/modals/modals-context';
import {
  ClientsToolbar,
  type GenderFilter,
  type TelegramFilter,
  type SortPreset,
  type ViewMode,
} from './components/ClientsToolbar';
import { ClientRow } from './components/ClientRow';
import type { FilterOption } from '@/components/data/Toolbar';

const PAGE_SIZE = 25;

export function ClientsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = parseInt(searchParams.get('page') ?? '1', 10) || 1;

  const { open } = useModals();

  // --- filter state ---
  const [searchRaw, setSearchRaw] = useState('');
  const [gender, setGender] = useState<GenderFilter>('all');
  const [telegram, setTelegram] = useState<TelegramFilter>('all');
  const [tag, setTag] = useState('all');
  const [sort, setSort] = useState<SortPreset>('recent:desc');
  const [view, setView] = useState<ViewMode>('table');

  const searchDebounced = useDebounce(searchRaw, 300);
  const q = searchDebounced.length >= 2 ? searchDebounced : undefined;

  const filter = {
    q,
    gender: gender !== 'all' ? (gender as 'male' | 'female') : undefined,
    hasTelegram: telegram === 'yes' ? true : telegram === 'no' ? false : undefined,
    tag: tag !== 'all' ? tag : undefined,
    sort,
    page,
    pageSize: PAGE_SIZE,
  };

  const { data, isPending, isError, refetch } = useClients(filter);

  // Derive tag options from current page items for the tag filter pill
  const tagOptions: FilterOption[] = useMemo(() => {
    const tags = new Set<string>();
    data?.items.forEach((c) => c.tags.forEach((t) => tags.add(t)));
    return [
      { value: 'all', label: 'Все теги' },
      ...Array.from(tags)
        .sort()
        .map((t) => ({ value: t, label: t })),
    ];
  }, [data]);

  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1;

  const handlePageChange = (p: number) => {
    setSearchParams(p === 1 ? {} : { page: String(p) }, { replace: true });
  };

  const resetFilters = () => {
    setSearchRaw('');
    setGender('all');
    setTelegram('all');
    setTag('all');
    handlePageChange(1);
  };

  if (isPending) return <PageLoading />;
  if (isError) return <PageError onRetry={() => void refetch()} />;

  const items = data.items;
  const hasActiveFilter =
    q !== undefined || gender !== 'all' || telegram !== 'all' || tag !== 'all';
  const isFilterEmpty = hasActiveFilter && items.length === 0;
  const isZeroClients = !hasActiveFilter && items.length === 0;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      {/* Page header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-bold tracking-[-0.5px]">Клиенты</h1>
          {data.total > 0 && (
            <p className="mt-0.5 text-[13px] text-fg-muted">
              Всего <b className="font-semibold text-fg">{data.total}</b> клиентов
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => open('new-client')}
          className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full bg-fg px-4 text-[13px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
        >
          <UserPlus className="size-3.5" />
          <span className="max-sm:hidden">Добавить клиента</span>
        </button>
      </div>

      <ClientsToolbar
        search={searchRaw}
        onSearchChange={(v) => {
          setSearchRaw(v);
          handlePageChange(1);
        }}
        gender={gender}
        onGenderChange={(v) => {
          setGender(v);
          handlePageChange(1);
        }}
        telegram={telegram}
        onTelegramChange={(v) => {
          setTelegram(v);
          handlePageChange(1);
        }}
        tag={tag}
        onTagChange={(v) => {
          setTag(v);
          handlePageChange(1);
        }}
        tagOptions={tagOptions}
        sort={sort}
        onSortChange={(v) => {
          setSort(v);
          handlePageChange(1);
        }}
        view={view}
        onViewChange={setView}
      />

      <section className="overflow-hidden rounded-lg border-[0.5px] border-border bg-surface shadow-1">
        {isZeroClients && (
          <EmptyState
            icon={Users}
            title="Клиентов пока нет"
            message="Добавьте первого клиента, чтобы начать работу."
            action={
              <button
                type="button"
                onClick={() => open('new-client')}
                className="mt-1 inline-flex h-9 items-center gap-1.5 rounded-full bg-fg px-4 text-[13px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
              >
                <UserPlus className="size-3.5" />
                Добавить клиента
              </button>
            }
          />
        )}

        {isFilterEmpty && (
          <EmptyState
            icon={Search}
            title="Ничего не найдено"
            message="Под текущие фильтры нет клиентов. Попробуйте изменить запрос."
            action={
              <button
                type="button"
                onClick={resetFilters}
                className="mt-1 inline-flex h-9 items-center rounded-full bg-fg px-4 text-[13px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
              >
                Сбросить фильтры
              </button>
            }
          />
        )}

        {items.length > 0 && (
          <div className="divide-y-0">
            {items.map((c) => (
              <ClientRow key={c.id} client={c} />
            ))}
          </div>
        )}

        {!isZeroClients && (
          <Pagination
            page={data.page}
            pageCount={pageCount}
            onPageChange={handlePageChange}
            shown={items.length}
            total={data.total}
            noun="клиентов"
          />
        )}
      </section>
    </div>
  );
}
