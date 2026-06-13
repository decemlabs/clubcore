import { FilterTabs } from '@/components/data/FilterTabs';
import type { ClientFilter, ClientFilterTab } from '@/features/clients/types';

/** Вкладки-фильтры статуса клиента поверх общего FilterTabs. */
export function ClientFilterTabs({
  tabs,
  value,
  onChange,
}: {
  tabs: ClientFilterTab[];
  value: ClientFilter;
  onChange: (value: ClientFilter) => void;
}) {
  return (
    <FilterTabs<ClientFilter>
      ariaLabel="Фильтр по статусу"
      tabs={tabs.map((t) => ({ value: t.filter, label: t.label, count: t.count, tone: t.tone }))}
      value={value}
      onChange={onChange}
    />
  );
}
