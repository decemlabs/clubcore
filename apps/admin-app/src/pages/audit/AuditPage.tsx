import { useState } from 'react';
import { toast } from 'sonner';
import { useAuditLog } from '@/features/audit/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import type { AuditEvent } from '@/features/audit/types';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/layout/Card';
import { SearchInput, FilterSelect } from '@/components/data/Toolbar';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Download, User, SlidersHorizontal, Calendar, Search } from '@/components/icons';
import { AuditRow } from './components/parts';
import { AuditDetailModal } from './components/AuditDetailModal';

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
  const { data, isPending, isError, refetch } = useAuditLog();
  const [search, setSearch] = useState('');
  const [employee, setEmployee] = useState('all');
  const [action, setAction] = useState('all');
  const [range, setRange] = useState('7d');
  const [selected, setSelected] = useState<{ event: AuditEvent; date: string } | null>(null);
  const [open, setOpen] = useState(false);

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  const q = search.trim().toLowerCase();
  const groups = data.groups
    .map((g) => ({
      ...g,
      events: g.events.filter((e) => {
        if (employee !== 'all' && e.actor.name !== employee) return false;
        if (action !== 'all' && e.action !== action) return false;
        if (range === 'today' && !g.label.startsWith('Сегодня')) return false;
        if (q && !`${e.lead}${e.obj}${e.tail} ${e.object}`.toLowerCase().includes(q)) return false;
        return true;
      }),
    }))
    .filter((g) => g.events.length > 0);

  const openEvent = (event: AuditEvent, date: string) => {
    setSelected({ event, date });
    setOpen(true);
  };

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

        {/* Log */}
        {groups.length === 0 ? (
          <EmptyState
            icon={Search}
            title="Записей не найдено"
            message="Измените фильтры или поисковый запрос."
          />
        ) : (
          groups.map((g) => (
            <div key={g.label}>
              <div className="px-[18px] pb-1 pt-3.5 text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
                {g.label}
              </div>
              {g.events.map((e) => (
                <AuditRow key={e.id} event={e} onClick={() => openEvent(e, g.date)} />
              ))}
            </div>
          ))
        )}
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
