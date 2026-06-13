import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/app/routes';
import { useClients } from '@/features/clients/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import type { ClientFilter, ClientSort, ClientSortKey } from '@/features/clients/types';
import { compare, DEFAULT_DIR } from '@/features/clients/sort';
import { DataTable } from '@/components/data/DataTable';
import { Pagination } from '@/components/data/Pagination';
import { useTableSelection } from '@/components/data/useTableSelection';
import { ClientsPageHead } from './components/ClientsPageHead';
import { ClientFilterTabs } from './components/ClientFilterTabs';
import { ClientsToolbar, type PlanTypeFilter, type ViewMode } from './components/ClientsToolbar';
import { BulkBar } from './components/BulkBar';
import { ClientCard } from './components/ClientCard';
import { clientColumns } from './components/columns';
import { EmptyState } from './components/EmptyState';

export function ClientsPage() {
  const { data, isPending, isError, refetch } = useClients();
  const navigate = useNavigate();

  const [statusFilter, setStatusFilter] = useState<ClientFilter>('all');
  const [search, setSearch] = useState('');
  const [planType, setPlanType] = useState<PlanTypeFilter>('all');
  const [trainer, setTrainer] = useState('all');
  const [sort, setSort] = useState<ClientSort>({ key: 'expires', dir: 'asc' });
  const [view, setView] = useState<ViewMode>('table');

  const clients = data?.clients;

  const trainerOptions = useMemo(() => {
    const names = Array.from(
      new Set((clients ?? []).map((c) => c.trainer?.name).filter((n): n is string => !!n)),
    );
    return [
      { value: 'all', label: 'Любой' },
      ...names.map((n) => ({ value: n, label: n })),
      { value: 'none', label: 'Без тренера' },
    ];
  }, [clients]);

  const visible = useMemo(() => {
    if (!clients) return [];
    const q = search.trim().toLowerCase();
    const qDigits = q.replace(/\D/g, '');
    const rows = clients.filter((c) => {
      if (statusFilter !== 'all' && c.status !== statusFilter) return false;
      if (planType !== 'all' && c.plan?.type !== planType) return false;
      if (trainer === 'none' ? c.trainer != null : trainer !== 'all' && c.trainer?.name !== trainer)
        return false;
      if (q) {
        const byName = c.name.toLowerCase().includes(q);
        const byPhone = qDigits.length > 0 && c.phone.replace(/\D/g, '').includes(qDigits);
        if (!byName && !byPhone) return false;
      }
      return true;
    });
    return [...rows].sort((a, b) => compare(a, b, sort));
  }, [clients, statusFilter, planType, trainer, search, sort]);

  const visibleIds = useMemo(() => visible.map((c) => c.id), [visible]);
  const selection = useTableSelection(visibleIds);

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  const handleSort = (key: ClientSortKey) =>
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: DEFAULT_DIR[key] },
    );

  const resetFilters = () => {
    setStatusFilter('all');
    setSearch('');
    setPlanType('all');
    setTrainer('all');
  };

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <ClientsPageHead summary={data.summary} />

      <ClientFilterTabs tabs={data.filters} value={statusFilter} onChange={setStatusFilter} />

      <ClientsToolbar
        search={search}
        onSearchChange={setSearch}
        planType={planType}
        onPlanTypeChange={setPlanType}
        trainer={trainer}
        onTrainerChange={setTrainer}
        trainerOptions={trainerOptions}
        sort={sort}
        onSortChange={setSort}
        view={view}
        onViewChange={setView}
      />

      <section className="overflow-hidden rounded-lg border-[0.5px] border-border bg-surface shadow-1">
        {selection.count > 0 && <BulkBar count={selection.count} onClear={selection.clear} />}

        <div className="@container">
          {visible.length === 0 ? (
            <EmptyState onReset={resetFilters} />
          ) : view === 'cards' ? (
            <div className="grid gap-3 p-4 @min-[640px]:grid-cols-2 @min-[980px]:grid-cols-3">
              {visible.map((c) => (
                <ClientCard key={c.id} client={c} variant="grid" />
              ))}
            </div>
          ) : (
            <>
              <div className="hidden @min-[640px]:block">
                <DataTable
                  data={visible}
                  columns={clientColumns}
                  getRowId={(c) => c.id}
                  sort={sort}
                  onSort={(key) => handleSort(key as ClientSortKey)}
                  selection={selection}
                  selectAllLabel="Выбрать всех"
                  rowLabel={(c) => c.name}
                  onRowClick={(c) => navigate(ROUTES.client(c.id))}
                />
              </div>
              <div className="@min-[640px]:hidden">
                {visible.map((c) => (
                  <ClientCard key={c.id} client={c} variant="list" />
                ))}
              </div>
            </>
          )}
        </div>

        <Pagination
          page={data.currentPage}
          pageCount={data.totalPages}
          shown={visible.length}
          total={data.totalCount}
          noun="клиентов"
        />
      </section>
    </div>
  );
}
