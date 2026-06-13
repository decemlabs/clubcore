import { FilterTabs } from '@/components/data/FilterTabs';
import type { TrainerFilterTab, TrainerTab } from '@/features/trainers/types';

/** Вкладки-разделы тренеров поверх общего FilterTabs. */
export function TrainerFilterTabs({
  tabs,
  value,
  onChange,
}: {
  tabs: TrainerFilterTab[];
  value: TrainerTab;
  onChange: (value: TrainerTab) => void;
}) {
  return (
    <FilterTabs<TrainerTab>
      ariaLabel="Разделы тренеров"
      tabs={tabs.map((t) => ({ value: t.tab, label: t.label, count: t.count, tone: t.tone }))}
      value={value}
      onChange={onChange}
    />
  );
}
