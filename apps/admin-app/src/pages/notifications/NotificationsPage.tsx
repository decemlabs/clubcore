import { useState } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { useNotifications } from '@/features/notifications/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import type { NotificationsData, NotifItem } from '@/features/notifications/types';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/button';
import { Send, Check, Download, Plus } from '@/components/icons';
import {
  NotifTabs,
  Panel,
  PanelHead,
  NotifRow,
  HistoryTable,
  TemplateCard,
  DeliveryStats,
  RecipientRow,
  GHOST_SM,
} from './components/parts';
import { Composer } from './components/Composer';

const CHIPS = [
  { key: 'all', label: 'Все' },
  { key: 'unread', label: 'Непрочитанные' },
  { key: 'finance', label: 'Финансы' },
  { key: 'clients', label: 'Клиенты' },
  { key: 'system', label: 'Система' },
];

const DLV_FILTER = [
  { value: 'all', label: 'Все' },
  { value: 'read', label: 'Прочитано' },
  { value: 'deliv', label: 'Доставлено' },
  { value: 'fail', label: 'Ошибка' },
];

export function NotificationsPage() {
  const { data, isPending, isError, refetch } = useNotifications();

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;
  return <NotificationsView data={data} />;
}

function NotificationsView({ data }: { data: NotificationsData }) {
  const [tab, setTab] = useState('center');
  const [notifs, setNotifs] = useState<NotifItem[]>(data.notifications);
  const [chip, setChip] = useState('all');
  const [tplOn, setTplOn] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(data.templates.map((t) => [t.id, t.on])),
  );
  const [dlvFilter, setDlvFilter] = useState('all');

  const unread = notifs.filter((n) => n.unread).length;

  const feed = notifs.filter((n) =>
    chip === 'all' ? true : chip === 'unread' ? n.unread : n.cat === chip,
  );
  const today = feed.filter((n) => n.day === 'today');
  const earlier = feed.filter((n) => n.day === 'earlier');

  const markAllRead = () => {
    setNotifs((prev) => prev.map((n) => ({ ...n, unread: false })));
    toast.success('Все уведомления прочитаны');
  };

  const recipients = data.delivery.recipients.filter(
    (r) => dlvFilter === 'all' || r.status === dlvFilter,
  );

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHeader
        title="Уведомления и сообщения"
        subtitle="Системные оповещения, рассылки клиентам, шаблоны и отчёты по доставке."
        actions={
          <Button
            onClick={() => setTab('broadcast')}
            className="h-[38px] gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold"
          >
            <Send className="size-[15px]" strokeWidth={2.2} />
            Новая рассылка
          </Button>
        }
      />

      <NotifTabs
        value={tab}
        onChange={setTab}
        tabs={[
          { key: 'center', label: 'Центр уведомлений', badge: unread },
          { key: 'history', label: 'История' },
          { key: 'templates', label: 'Шаблоны' },
          { key: 'broadcast', label: 'Рассылка' },
          { key: 'delivery', label: 'Доставка' },
        ]}
      />

      {tab === 'center' ? (
        <Panel>
          <PanelHead
            title="Центр уведомлений"
            action={
              <button type="button" onClick={markAllRead} className={GHOST_SM}>
                <Check className="size-3.5" strokeWidth={2.4} />
                Прочитать все
              </button>
            }
          />
          <div className="flex gap-1.5 overflow-x-auto border-b-[0.5px] border-border px-[18px] py-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {CHIPS.map((c) => {
              const active = c.key === chip;
              return (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => setChip(c.key)}
                  className={cn(
                    'shrink-0 whitespace-nowrap rounded-full border-[0.5px] px-3 py-1.5 text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    active
                      ? 'border-fg bg-fg text-bg dark:border-border-strong dark:bg-surface-3 dark:text-fg'
                      : 'border-border bg-surface text-fg-muted hover:border-border-strong hover:text-fg',
                  )}
                >
                  {c.label}
                </button>
              );
            })}
          </div>
          {feed.length === 0 ? (
            <div className="flex flex-col items-center px-6 py-14 text-center">
              <span className="mb-3.5 grid size-[52px] place-items-center rounded-[15px] bg-primary-soft text-primary-deep dark:text-primary">
                <Check className="size-6" strokeWidth={2.4} />
              </span>
              <div className="text-[15px] font-bold">Всё прочитано</div>
              <div className="mt-1 text-[12.5px] text-fg-subtle">
                Новых уведомлений по этому фильтру нет.
              </div>
            </div>
          ) : (
            <>
              {today.length ? (
                <>
                  <div className="px-[18px] pb-1.5 pt-3.5 text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
                    Сегодня
                  </div>
                  {today.map((n) => (
                    <NotifRow key={n.id} n={n} />
                  ))}
                </>
              ) : null}
              {earlier.length ? (
                <>
                  <div className="px-[18px] pb-1.5 pt-3.5 text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
                    Ранее
                  </div>
                  {earlier.map((n) => (
                    <NotifRow key={n.id} n={n} />
                  ))}
                </>
              ) : null}
            </>
          )}
        </Panel>
      ) : null}

      {tab === 'history' ? (
        <Panel>
          <PanelHead
            title="История сообщений"
            action={
              <button
                type="button"
                onClick={() => toast.success('Экспорт в CSV')}
                className={GHOST_SM}
              >
                <Download className="size-3.5" strokeWidth={2} />
                Экспорт
              </button>
            }
          />
          <HistoryTable rows={data.history} onRow={(r) => toast(`Открыт отчёт: ${r.name}`)} />
        </Panel>
      ) : null}

      {tab === 'templates' ? (
        <Panel>
          <PanelHead
            title="Шаблоны сообщений"
            action={
              <button type="button" onClick={() => toast('Новый шаблон')} className={GHOST_SM}>
                <Plus className="size-3.5" strokeWidth={2.4} />
                Шаблон
              </button>
            }
          />
          <div className="grid grid-cols-1 gap-3 p-[18px] md:grid-cols-2">
            {data.templates.map((t) => (
              <TemplateCard
                key={t.id}
                tpl={t}
                on={!!tplOn[t.id]}
                onToggle={(v) => setTplOn((prev) => ({ ...prev, [t.id]: v }))}
                onEdit={() => toast('Редактирование шаблона')}
              />
            ))}
          </div>
        </Panel>
      ) : null}

      {tab === 'broadcast' ? (
        <Panel>
          <Composer audiences={data.audiences} defaultMessage={data.defaultMessage} />
        </Panel>
      ) : null}

      {tab === 'delivery' ? (
        <Panel>
          <div className="border-b-[0.5px] border-border px-[18px] py-4">
            <div className="text-[15px] font-bold">{data.delivery.name}</div>
            <div className="mt-0.5 text-[12px] text-fg-subtle">{data.delivery.meta}</div>
          </div>
          <DeliveryStats stats={data.delivery.stats} />
          <div className="flex items-center gap-2.5 border-y-[0.5px] border-border px-[18px] py-3">
            <h3 className="text-[13px] font-bold">Получатели</h3>
            <select
              value={dlvFilter}
              onChange={(e) => setDlvFilter(e.target.value)}
              className="ml-auto h-8 cursor-pointer appearance-none rounded-[9px] border-[0.5px] border-border-strong bg-surface px-3 pr-7 text-[12.5px] font-semibold text-fg outline-none focus:border-primary"
            >
              {DLV_FILTER.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          {recipients.map((r) => (
            <RecipientRow key={r.id} r={r} />
          ))}
        </Panel>
      ) : null}
    </div>
  );
}
