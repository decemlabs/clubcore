import { useRef, useState, type RefObject } from 'react';
import { toast } from 'sonner';
import { usePlans } from '@/features/plans/api';
import { PageLoading, PageError } from '@/components/feedback/PageState';
import type { PlanTab } from '@/features/plans/types';
import { SectionHead } from '@/components/layout/SectionHead';
import { Segmented } from '@/components/ui/Segmented';
import { Plus } from '@/components/icons';
import { PlansPageHead } from './components/PlansPageHead';
import { PlansKpis } from './components/PlansKpis';
import { PlanFilterTabs } from './components/PlanFilterTabs';
import { TariffCard } from './components/TariffCard';
import { SalesChart } from './components/SalesChart';
import { PromoCard } from './components/PromoCard';
import { AddonsCard } from './components/AddonsCard';
import { SALES_UNIT_OPTIONS, type SalesUnit } from './components/sales-unit';

const ADD_BTN =
  'inline-flex h-9 items-center gap-1.5 rounded-full border-[0.5px] border-border bg-surface px-3.5 text-[13px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function AddButton({ children, onClick }: { children: string; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} className={ADD_BTN}>
      <Plus className="size-3.5" strokeWidth={2.4} />
      {children}
    </button>
  );
}

export function PlansPage() {
  const { data, isPending, isError, refetch } = usePlans();

  const [tab, setTab] = useState<PlanTab>('tariffs');
  const [salesUnit, setSalesUnit] = useState<SalesUnit>('count');

  const tariffsRef = useRef<HTMLElement>(null);
  const promosRef = useRef<HTMLElement>(null);
  const addonsRef = useRef<HTMLElement>(null);

  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;

  const sectionRef: Partial<Record<PlanTab, RefObject<HTMLElement>>> = {
    tariffs: tariffsRef,
    promos: promosRef,
    addons: addonsRef,
  };
  const handleTab = (next: PlanTab) => {
    setTab(next);
    sectionRef[next]?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PlansPageHead summary={data.summary} />

      <PlansKpis kpis={data.kpis} />

      <PlanFilterTabs tabs={data.tabs} value={tab} onChange={handleTab} />

      {/* Тарифы */}
      <section ref={tariffsRef} className="flex scroll-mt-24 flex-col gap-3.5">
        <SectionHead
          title="Тарифы"
          subtitle="Что показывается клиентам при оформлении и продлении"
          action={<AddButton onClick={() => toast('Конструктор тарифа')}>Добавить тариф</AddButton>}
        />
        <div className="@container">
          <div className="grid grid-cols-1 gap-4 @min-[640px]:grid-cols-2 @min-[1000px]:grid-cols-3">
            {data.tariffs.map((t) => (
              <TariffCard key={t.id} tariff={t} />
            ))}
          </div>
        </div>
      </section>

      {/* Продажи по тарифам */}
      <section className="flex flex-col gap-3.5">
        <SectionHead
          title="Продажи по тарифам"
          subtitle="Последние 6 месяцев · количество оформленных абонементов"
          action={
            <Segmented
              variant="mini"
              options={SALES_UNIT_OPTIONS}
              value={salesUnit}
              onChange={setSalesUnit}
              ariaLabel="Единицы продаж"
            />
          }
        />
        <SalesChart data={data.sales} unit={salesUnit} />
      </section>

      {/* Скидки и акции */}
      <section ref={promosRef} className="flex scroll-mt-24 flex-col gap-3.5">
        <SectionHead
          title="Скидки и акции"
          subtitle="Активные предложения, видны клиентам в приложении"
          action={<AddButton onClick={() => toast('Создание акции')}>Создать акцию</AddButton>}
        />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {data.promos.map((p) => (
            <PromoCard key={p.id} promo={p} />
          ))}
        </div>
      </section>

      {/* Доп. услуги */}
      <section ref={addonsRef} className="flex scroll-mt-24 flex-col gap-3.5">
        <SectionHead
          title="Доп. услуги"
          subtitle="Продаются отдельно либо включаются в тариф"
          action={<AddButton onClick={() => toast('Добавление услуги')}>Добавить услугу</AddButton>}
        />
        <AddonsCard addons={data.addons} />
      </section>
    </div>
  );
}
