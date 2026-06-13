/**
 * AuditPage — owner-only audit log with real server-side filters + keyset pagination
 * + CSV export (Phase 104-03 RPT-03).
 *
 * RBAC: early-return Lock-EmptyState BEFORE any data hook fires.
 * Reception makes ZERO API calls — Threat T-104-06.
 *
 * Payload JSONB rendered as escaped JSON.stringify only — Threat T-104-07.
 *
 * Filters: actorEmailSnapshot (400ms debounce), resourceType, action, date range.
 * Filter changes reset page→1.
 * Pagination: pageSize=25, keyset order created_at DESC,id DESC.
 * CSV: «Экспорт CSV» → downloadCsv('/api/v1/audit-log.csv', ...).
 */
import { useState } from 'react';
import { toast } from 'sonner';
import { useSession } from '@/features/auth/api';
import { useAuditLog } from '@/features/audit/api';
import { downloadCsv } from '@/api/csv';
import { can } from '@/shared/session/can';
import { useDebounce } from '@/lib/useDebounce';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/ui/skeleton';
import { Lock, Download, Loader2, Search, Activity, SlidersHorizontal } from '@/components/icons';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/layout/Card';
import { SearchInput, FilterSelect } from '@/components/data/Toolbar';
import { Pagination } from '@/components/data/Pagination';
import { DateRangePicker } from '@/components/common/DateRangePicker';
import { AuditDetailModal } from './components/AuditDetailModal';
import { RealAuditRow } from './components/parts';
import { mskTodayISO, mskDaysAgoISO, formatDateRu } from '@/lib/format';
import type { Role } from '@/shared/session/types';
import type { AuditEvent, AuditFilter } from '@/features/audit/schemas';

const PAGE_SIZE = 25;

// ---------------------------------------------------------------------------
// Filter option lists (static, UI-SPEC §3.1)
// ---------------------------------------------------------------------------

const RESOURCE_TYPE_OPTIONS = [
  { value: '', label: 'Все ресурсы' },
  { value: 'membership', label: 'Абонемент' },
  { value: 'client', label: 'Клиент' },
  { value: 'user', label: 'Пользователь' },
  { value: 'booking', label: 'Бронирование' },
  { value: 'payment', label: 'Платёж' },
  { value: 'trainer', label: 'Тренер' },
  { value: 'schedule_slot', label: 'Слот расписания' },
];

const ACTION_OPTIONS = [
  { value: '', label: 'Все действия' },
  { value: 'create', label: 'Создание' },
  { value: 'update', label: 'Изменение' },
  { value: 'delete', label: 'Удаление' },
  { value: 'login', label: 'Вход' },
  { value: 'logout', label: 'Выход' },
];

// ---------------------------------------------------------------------------
// CSV export button — idle / downloading / error
// ---------------------------------------------------------------------------

function CsvButton({ onClick }: { onClick: () => Promise<void> }) {
  const [downloading, setDownloading] = useState(false);

  async function handleClick() {
    if (downloading) return;
    setDownloading(true);
    try {
      await onClick();
    } catch {
      toast.error('Не удалось скачать файл', {
        description: 'Проверьте соединение и попробуйте ещё раз.',
      });
    } finally {
      setDownloading(false);
    }
  }

  return (
    <button
      type="button"
      disabled={downloading}
      onClick={() => void handleClick()}
      className="inline-flex h-[38px] shrink-0 items-center gap-[7px] rounded-full border-[0.5px] border-border bg-surface px-[14px] text-[13px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-75"
    >
      {downloading ? (
        <Loader2 className="size-[14px] animate-spin text-fg-subtle" />
      ) : (
        <Download className="size-[14px]" />
      )}
      Экспорт CSV
    </button>
  );
}

// ---------------------------------------------------------------------------
// Outer guard component — only calls useSession (Rules of Hooks safe)
// ---------------------------------------------------------------------------

export function AuditPage() {
  // RBAC guard: MUST be FIRST — before any data hook fires (T-104-06).
  const session = useSession();
  const role = session.data?.role ?? 'reception';

  if (!can(role, 'view', 'audit-log')) {
    return (
      <EmptyState
        icon={Lock}
        title="Недостаточно прав"
        message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
        className="py-24"
      />
    );
  }

  return <AuditPageContent role={role} />;
}

// ---------------------------------------------------------------------------
// Inner content component — data hooks only called when RBAC guard passes
// ---------------------------------------------------------------------------

function AuditPageContent({ role }: { role: Role }) {
  // Filter state
  const [actorEmail, setActorEmail] = useState('');
  const [resourceType, setResourceType] = useState('');
  const [action, setAction] = useState('');
  const [fromDate, setFromDate] = useState(() => mskDaysAgoISO(29));
  const [toDate, setToDate] = useState(() => mskTodayISO());
  const [page, setPage] = useState(1);

  // Detail modal state
  const [selected, setSelected] = useState<AuditEvent | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  // 400ms debounce on actor email search (UI-SPEC §3.1)
  const debouncedEmail = useDebounce(actorEmail, 400);

  // Build server-side filter (undefined values are NOT sent — per audit/api.ts)
  const filter: AuditFilter = {
    ...(debouncedEmail ? { actorEmailSnapshot: debouncedEmail } : {}),
    ...(resourceType ? { resourceType } : {}),
    ...(action ? { action } : {}),
    ...(fromDate ? { from: fromDate } : {}),
    ...(toDate ? { to: toDate } : {}),
    page,
  };

  const { data, isPending, isFetching, isError, refetch } = useAuditLog(filter, role);

  // Track if any filter is active (to distinguish "no events ever" vs "no results for filter")
  const hasFilter = Boolean(debouncedEmail || resourceType || action);

  function handleRangeChange(from: string, to: string) {
    setFromDate(from);
    setToDate(to);
    setPage(1);
  }

  function handleEmailChange(value: string) {
    setActorEmail(value);
    setPage(1);
  }

  function handleResourceTypeChange(value: string) {
    setResourceType(value);
    setPage(1);
  }

  function handleActionChange(value: string) {
    setAction(value);
    setPage(1);
  }

  function handlePageChange(p: number) {
    setPage(p);
  }

  function openEvent(event: AuditEvent) {
    setSelected(event);
    setModalOpen(true);
  }

  function handleCsv() {
    return downloadCsv(
      '/api/v1/audit-log.csv',
      `audit-log-${fromDate}-${toDate}.csv`,
      {
        ...(debouncedEmail ? { actorEmailSnapshot: debouncedEmail } : {}),
        ...(resourceType ? { resourceType } : {}),
        ...(action ? { action } : {}),
        ...(fromDate ? { from: fromDate } : {}),
        ...(toDate ? { to: toDate } : {}),
      },
    );
  }

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHeader
        title="Журнал действий"
        subtitle="Кто, что и когда менял в системе. Записи хранятся 12 месяцев."
        actions={<CsvButton onClick={handleCsv} />}
      />

      <Card>
        {/* Filter toolbar */}
        <div className="flex flex-wrap items-center gap-2.5 border-b-[0.5px] border-border bg-surface-2 px-4 py-3">
          <SearchInput
            value={actorEmail}
            onChange={handleEmailChange}
            placeholder="Email сотрудника…"
            className="min-w-[180px] flex-1"
          />
          <FilterSelect
            icon={SlidersHorizontal}
            label="Тип ресурса"
            options={RESOURCE_TYPE_OPTIONS}
            value={resourceType}
            onChange={handleResourceTypeChange}
          />
          <FilterSelect
            icon={Activity}
            label="Действие"
            options={ACTION_OPTIONS}
            value={action}
            onChange={handleActionChange}
          />
          <DateRangePicker from={fromDate} to={toDate} onChange={handleRangeChange} />
        </div>

        {/* Content area */}
        {isPending ? (
          <PageLoading />
        ) : isError ? (
          <PageError onRetry={() => void refetch()} />
        ) : isFetching ? (
          <Skeleton className="h-[400px] w-full rounded-none" />
        ) : items.length === 0 ? (
          hasFilter ? (
            <EmptyState
              icon={Search}
              title="Записей не найдено"
              message="Измените фильтры или сократите диапазон дат."
              className="py-16"
            />
          ) : (
            <EmptyState
              icon={Activity}
              title="Журнал пуст"
              message="Действия сотрудников будут появляться здесь."
              className="py-16"
            />
          )
        ) : (
          <AuditItemList items={items} onOpenEvent={openEvent} fromDate={fromDate} />
        )}

        {/* Pagination */}
        {!isPending && !isError && total > PAGE_SIZE ? (
          <Pagination
            page={page}
            pageCount={pageCount}
            onPageChange={handlePageChange}
            shown={items.length}
            total={total}
            noun="записей"
          />
        ) : null}
      </Card>

      <AuditDetailModal
        event={selected}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Audit item list — groups items by date
// ---------------------------------------------------------------------------

function AuditItemList({
  items,
  onOpenEvent,
  fromDate,
}: {
  items: AuditEvent[];
  onOpenEvent: (event: AuditEvent) => void;
  fromDate: string;
}) {
  // Group items by date (createdAt date portion)
  const groups: { dateLabel: string; events: AuditEvent[] }[] = [];
  const seen = new Map<string, number>();

  for (const item of items) {
    const dateStr = item.createdAt.slice(0, 10); // 'YYYY-MM-DD'
    const label = formatDateRu(dateStr, 'd MMMM yyyy');
    if (!seen.has(dateStr)) {
      seen.set(dateStr, groups.length);
      groups.push({ dateLabel: label, events: [] });
    }
    groups[seen.get(dateStr)!]!.events.push(item);
  }

  void fromDate;

  return (
    <div>
      {groups.map((group) => (
        <div key={group.dateLabel}>
          <div className="border-b-[0.5px] border-border px-[18px] pb-1 pt-3.5 text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
            {group.dateLabel}
          </div>
          {group.events.map((event) => (
            <RealAuditRow
              key={event.id}
              event={event}
              onClick={() => onOpenEvent(event)}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
