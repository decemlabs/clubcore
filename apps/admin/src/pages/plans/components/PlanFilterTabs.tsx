import { FilterTabs } from '@/components/data/FilterTabs';
import type { PlanFilterTab, PlanTab } from '@/features/plans/types';

/** Вкладки разделов абонементов поверх общего FilterTabs. */
export function PlanFilterTabs({
  tabs,
  value,
  onChange,
}: {
  tabs: PlanFilterTab[];
  value: PlanTab;
  onChange: (value: PlanTab) => void;
}) {
  return (
    <FilterTabs<PlanTab>
      ariaLabel="Разделы абонементов"
      tabs={tabs.map((t) => ({ value: t.tab, label: t.label, count: t.count }))}
      value={value}
      onChange={onChange}
    />
  );
}
