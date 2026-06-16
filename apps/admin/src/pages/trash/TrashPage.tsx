import { useState } from 'react';
import { toast } from 'sonner';
import { pluralRu } from '@/lib/format';
import { useTrash } from '@/features/trash/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import type { TrashItem } from '@/features/trash/types';
import { useModals } from '@/components/modals/modals-context';
import { useTableSelection } from '@/components/data/useTableSelection';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/layout/Card';
import { SearchInput } from '@/components/data/Toolbar';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Trash2, Undo2, Clock } from '@/components/icons';
import { TrashRow, PillTabs, type PillTab } from './components/parts';

export function TrashPage() {
  const { data, isPending, isError, refetch } = useTrash();

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;
  return <TrashView initial={data.items} />;
}

function TrashView({ initial }: { initial: TrashItem[] }) {
  const { open } = useModals();
  const [items, setItems] = useState<TrashItem[]>(initial);
  const [tab, setTab] = useState('all');
  const [search, setSearch] = useState('');
  const selection = useTableSelection(items.map((i) => i.id));

  const q = search.trim().toLowerCase();
  const visible = items.filter(
    (i) => (tab === 'all' || i.type === tab) && (!q || i.name.toLowerCase().includes(q)),
  );

  const countBy = (t: string) =>
    t === 'all' ? items.length : items.filter((i) => i.type === t).length;
  const tabs: PillTab[] = [
    { key: 'all', label: 'Всё', count: countBy('all') },
    { key: 'client', label: 'Клиенты', count: countBy('client') },
    { key: 'trainer', label: 'Тренеры', count: countBy('trainer') },
    { key: 'plan', label: 'Тарифы', count: countBy('plan') },
    { key: 'session', label: 'Тренировки', count: countBy('session') },
  ];

  const soonCount = items.filter((i) => i.daysLeft <= 3).length;

  const restore = (ids: string[]) => {
    setItems((prev) => prev.filter((i) => !ids.includes(i.id)));
    selection.clear();
    const n = ids.length;
    const msg =
      n === 1
        ? 'Запись восстановлена'
        : `${n} ${pluralRu(n, ['запись', 'записи', 'записей'])} восстановлено`;
    toast.success(msg, {
      action: {
        label: 'Отменить',
        onClick: () =>
          setItems((prev) =>
            initial.filter((i) => prev.some((p) => p.id === i.id) || ids.includes(i.id)),
          ),
      },
    });
  };

  const deleteForever = (item: TrashItem) =>
    open('confirm', {
      confirm: {
        title: `Удалить «${item.name}» навсегда?`,
        message: (
          <>
            Запись будет стёрта <b className="font-semibold text-fg">безвозвратно</b>. Это действие
            нельзя отменить.
          </>
        ),
        tone: 'danger',
        confirmLabel: 'Удалить навсегда',
        onConfirm: () => {
          setItems((prev) => prev.filter((i) => i.id !== item.id));
          toast.success('Удалено безвозвратно');
        },
      },
    });

  const emptyTrash = () =>
    open('confirm', {
      confirm: {
        title: 'Очистить корзину?',
        message: `Все ${items.length} ${pluralRu(items.length, ['запись', 'записи', 'записей'])} будут удалены безвозвратно.`,
        tone: 'danger',
        confirmLabel: 'Удалить навсегда',
        onConfirm: () => {
          setItems([]);
          selection.clear();
          toast.success('Удалено безвозвратно');
        },
      },
    });

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHeader
        title="Корзина"
        subtitle="Удалённые записи хранятся 30 дней, затем стираются безвозвратно. Их можно восстановить."
        actions={
          items.length > 0 ? (
            <button
              type="button"
              onClick={emptyTrash}
              className="inline-flex h-[38px] shrink-0 items-center gap-[7px] rounded-full border-[0.5px] border-danger/35 bg-surface px-[14px] text-[13px] font-semibold text-danger transition-colors hover:bg-danger-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Trash2 className="size-[14px]" />
              Очистить корзину
            </button>
          ) : undefined
        }
      />

      {soonCount > 0 ? (
        <div className="flex items-start gap-2.5 rounded-[14px] bg-warning-soft px-4 py-3 text-[12.5px] leading-relaxed text-warning-deep">
          <Clock className="mt-px size-[17px] shrink-0" strokeWidth={2} />
          <span>
            Автоочистка включена.{' '}
            <b className="font-bold">
              {soonCount} {pluralRu(soonCount, ['запись', 'записи', 'записей'])}
            </b>{' '}
            будут удалены безвозвратно в ближайшие 3 дня.
          </span>
        </div>
      ) : null}

      <PillTabs tabs={tabs} value={tab} onChange={setTab} />

      <Card>
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-3 border-b-[0.5px] border-border bg-surface-2 px-4 py-3">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Поиск в корзине…"
            className="min-w-[180px] max-w-[300px] flex-1"
          />
          <span className="ml-auto text-[12.5px] text-fg-muted">
            В корзине <b className="font-semibold text-fg">{visible.length}</b>
          </span>
        </div>

        {/* Bulk bar */}
        {selection.count > 0 ? (
          <div className="flex items-center gap-3 border-b-[0.5px] border-border bg-primary-soft px-4 py-2.5">
            <span className="text-[13px] font-[650] text-primary-deep dark:text-primary">
              Выбрано {selection.count}
            </span>
            <div className="ml-auto flex shrink-0 gap-2">
              <button
                type="button"
                onClick={selection.clear}
                className="inline-flex h-8 items-center rounded-[9px] border-[0.5px] border-border-strong bg-surface px-3 text-[12.5px] font-semibold text-fg transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                Снять
              </button>
              <button
                type="button"
                onClick={() => restore([...selection.selected])}
                className="inline-flex h-8 items-center gap-1.5 rounded-[9px] bg-fg px-3 text-[12.5px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
              >
                <Undo2 className="size-3.5" strokeWidth={2} />
                Восстановить
              </button>
            </div>
          </div>
        ) : null}

        {/* Rows / empty */}
        {visible.length === 0 ? (
          <EmptyState
            icon={Trash2}
            title="Корзина пуста"
            message="Удалённые записи появятся здесь и будут храниться 30 дней."
          />
        ) : (
          visible.map((item) => (
            <TrashRow
              key={item.id}
              item={item}
              selected={selection.isSelected(item.id)}
              onToggle={() => selection.toggle(item.id)}
              onRestore={() => restore([item.id])}
              onDelete={() => deleteForever(item)}
            />
          ))
        )}
      </Card>
    </div>
  );
}
