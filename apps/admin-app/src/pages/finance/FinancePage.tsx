import { useState } from 'react';
import { toast } from 'sonner';
import { formatInt } from '@/lib/format';
import { useFinance } from '@/features/finance/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import type { PayRow, RegRow } from '@/features/finance/types';
import { PageHeader } from '@/components/layout/PageHeader';
import { StatStrip } from '@/components/layout/StatStrip';
import { FilterSelect } from '@/components/data/Toolbar';
import {
  Banknote,
  CheckCircle2,
  CircleX,
  Users,
  Download,
  SlidersHorizontal,
  CreditCard,
} from '@/components/icons';
import {
  FinanceKpi,
  FinanceTabs,
  Panel,
  Toolbar,
  RegTable,
  FailTable,
  PayTable,
} from './components/parts';
import { TxModal, PayoutModal } from './components/FinanceModals';

const STATUS_OPTS = [
  { value: 'all', label: 'Все статусы' },
  { value: 'ok', label: 'Успешные' },
  { value: 'refund', label: 'Возвраты' },
  { value: 'pending', label: 'Ожидание' },
];
const METHOD_OPTS = [
  { value: 'all', label: 'Все способы' },
  { value: 'Карта', label: 'Карта' },
  { value: 'СБП', label: 'СБП' },
  { value: 'Наличные', label: 'Наличные' },
];

export function FinancePage() {
  const { data, isPending, isError, refetch } = useFinance();
  const [tab, setTab] = useState('reg');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [method, setMethod] = useState('all');
  const [tx, setTx] = useState<{ row: RegRow; screen: 'detail' | 'refund' } | null>(null);
  const [payRow, setPayRow] = useState<PayRow | null>(null);

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  const q = search.trim().toLowerCase();
  const reg = data.reg.filter(
    (r) =>
      (status === 'all' || r.status === status) &&
      (method === 'all' || r.method.includes(method)) &&
      (!q || `${r.name} ${r.desc}`.toLowerCase().includes(q)),
  );
  const fail = data.fail.filter((r) => !q || r.name.toLowerCase().includes(q));

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PageHeader
        title="Финансы"
        subtitle="Все платежи, возвраты и выплаты тренерам · апрель 2026"
        actions={
          <button
            type="button"
            onClick={() => toast.success('Реестр выгружен в Excel')}
            className="inline-flex h-[38px] shrink-0 items-center gap-[7px] rounded-full border-[0.5px] border-border bg-surface px-[14px] text-[13px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Download className="size-[14px]" />
            Экспорт
          </button>
        }
      />

      <StatStrip className="grid-cols-2 gap-3 lg:grid-cols-4">
        <FinanceKpi
          icon={Banknote}
          label="Оборот за месяц"
          value={formatInt(data.kpi.turnover)}
          unit=" ₽"
        />
        <FinanceKpi
          icon={CheckCircle2}
          label="Успешных"
          value={formatInt(data.kpi.success)}
          variant="accent"
        />
        <FinanceKpi
          icon={CircleX}
          label="Неудачных"
          value={formatInt(data.kpi.failed)}
          variant="danger"
        />
        <FinanceKpi
          icon={Users}
          label="К выплате тренерам"
          value={formatInt(data.kpi.payout)}
          unit=" ₽"
        />
      </StatStrip>

      <FinanceTabs
        value={tab}
        onChange={(t) => {
          setTab(t);
          setSearch('');
        }}
        tabs={[
          { key: 'reg', label: 'Реестр платежей' },
          { key: 'fail', label: 'Неудачные', badge: data.failCount },
          { key: 'pay', label: 'Выплаты тренерам' },
        ]}
      />

      {tab === 'reg' ? (
        <Panel>
          <Toolbar
            search={search}
            onSearch={setSearch}
            placeholder="Поиск по клиенту, ID…"
            right={
              <>
                <FilterSelect
                  icon={SlidersHorizontal}
                  label="Статус"
                  options={STATUS_OPTS}
                  value={status}
                  onChange={setStatus}
                />
                <FilterSelect
                  icon={CreditCard}
                  label="Способ"
                  options={METHOD_OPTS}
                  value={method}
                  onChange={setMethod}
                />
                <span className="ml-auto text-[12.5px] text-fg-muted">
                  Всего <b className="font-semibold text-fg">{formatInt(data.regCount)}</b>
                </span>
              </>
            }
          />
          <RegTable rows={reg} onRow={(row) => setTx({ row, screen: 'detail' })} />
        </Panel>
      ) : null}

      {tab === 'fail' ? (
        <Panel>
          <Toolbar
            search={search}
            onSearch={setSearch}
            placeholder="Поиск…"
            right={
              <span className="ml-auto text-[12.5px] text-fg-muted">
                Требуют внимания · <b className="font-semibold text-danger">{data.failCount}</b>
              </span>
            }
          />
          <FailTable
            rows={fail}
            onRetry={(r) => toast.success(`Повторный платёж отправлен · ${r.name}`)}
          />
        </Panel>
      ) : null}

      {tab === 'pay' ? (
        <Panel>
          <Toolbar
            right={
              <div className="flex w-full flex-wrap items-center gap-x-4 gap-y-1">
                <span className="text-[13px] font-semibold">Период: апрель 2026</span>
                <span className="ml-auto text-[12.5px] text-fg-muted">
                  К выплате <b className="font-semibold text-fg">{formatInt(data.payoutTotal)} ₽</b>{' '}
                  · {data.payoutTrainers} тренеров
                </span>
              </div>
            }
          />
          <PayTable rows={data.pay} onPayout={setPayRow} />
        </Panel>
      ) : null}

      <TxModal
        row={tx?.row ?? null}
        screen={tx?.screen ?? 'detail'}
        onScreen={(screen) => setTx((p) => (p ? { ...p, screen } : p))}
        onClose={() => setTx(null)}
      />
      <PayoutModal row={payRow} onClose={() => setPayRow(null)} />
    </div>
  );
}
