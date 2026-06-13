/**
 * AuditPage — Phase 104-01 stub.
 *
 * Wave 1 wired the domain layer (useAuditLog, AuditLogResponseSchema).
 * Wave 2 (104-02) will replace this stub with the full wired implementation:
 * filters, pagination, CSV download, RBAC Lock-EmptyState for reception.
 *
 * TODO Phase 104-02: wire useAuditLog(filter, role) + AuditRow + CSV export.
 */
import { useState } from 'react';
import { toast } from 'sonner';
import { useAuditLog } from '@/features/audit/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import type { AuditEvent as LegacyAuditEvent } from '@/features/audit/types';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/layout/Card';
import { SearchInput, FilterSelect } from '@/components/data/Toolbar';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Download, User, SlidersHorizontal, Calendar, Search } from '@/components/icons';
import { AuditDetailModal } from './components/AuditDetailModal';
import { useSession } from '@/features/auth/api';

const EMPLOYEES = [
  { value: 'all', label: 'Все сотрудники' },
  { value: 'Артём Лебедев', label: 'Артём Лебедев' },
  { value: 'Маша Костина', label: 'Маша Костина' },
  { value: 'Дмитрий Сомов', label: 'Дмитрий Сомов' },
];
const ACTIONS = [
  { value: 'all', label: 'Все действия' },
  { value: 'create', label: 'Создание' },
  { value: 'edit', label: 'Изменение' },
  { value: 'delete', label: 'Удаление' },
  { value: 'login', label: 'Вход' },
];
const RANGES = [
  { value: '7d', label: 'За 7 дней' },
  { value: 'today', label: 'Сегодня' },
  { value: '30d', label: 'За 30 дней' },
];

export function AuditPage() {
  const { data: session } = useSession();
  const role = session?.role ?? 'reception';

  // Wave 2 will add full filter state + pagination
  const { data, isPending, isError, refetch } = useAuditLog({}, role);

  const [search, setSearch] = useState('');
  const [employee, setEmployee] = useState('all');
  const [action, setAction] = useState('all');
  const [range, setRange] = useState('7d');
  const [selected, setSelected] = useState<{ event: LegacyAuditEvent; date: string } | null>(null);
  const [open, setOpen] = useState(false);

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  // Wave 2 will render real data.items with AuditRow.
  // For now: show an EmptyState so the page compiles and routes work.
  void search;
  void employee;
  void action;
  void range;

  const openEvent = (_event: LegacyAuditEvent, _date: string) => {
    setSelected({ event: _event, date: _date });
    setOpen(true);
  };
  void openEvent;

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHeader
        title="Журнал действий"
        subtitle="Кто, что и когда менял в системе. Записи хранятся 12 месяцев."
        actions={
          <button
            type="button"
            onClick={() => toast('Экспорт журнала')}
            className="inline-flex h-[38px] shrink-0 items-center gap-[7px] rounded-full border-[0.5px] border-border bg-surface px-[14px] text-[13px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Download className="size-[14px]" />
            Экспорт
          </button>
        }
      />

      <Card>
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-2.5 border-b-[0.5px] border-border bg-surface-2 px-4 py-3">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Поиск по объекту, действию…"
            className="min-w-[180px] flex-1"
          />
          <FilterSelect
            icon={User}
            label="Сотрудник"
            options={EMPLOYEES}
            value={employee}
            onChange={setEmployee}
          />
          <FilterSelect
            icon={SlidersHorizontal}
            label="Действие"
            options={ACTIONS}
            value={action}
            onChange={setAction}
          />
          <FilterSelect
            icon={Calendar}
            label="Период"
            options={RANGES}
            value={range}
            onChange={setRange}
          />
        </div>

        {/* Wave 2 TODO: render data.items via AuditRow components */}
        <EmptyState
          icon={Search}
          title="Записей не найдено"
          message="Фильтрация и список будут доступны в следующей версии."
        />
      </Card>

      <AuditDetailModal
        event={selected?.event ?? null}
        date={selected?.date ?? ''}
        open={open}
        onOpenChange={setOpen}
      />
    </div>
  );
}
