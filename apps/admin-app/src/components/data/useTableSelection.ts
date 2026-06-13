import { useState } from 'react';

export interface TableSelection {
  selected: Set<string>;
  count: number;
  isSelected: (id: string) => boolean;
  allChecked: boolean;
  someChecked: boolean;
  toggle: (id: string) => void;
  toggleAll: (checked: boolean) => void;
  clear: () => void;
}

/**
 * Управление выбором строк таблицы. Принимает id текущих видимых строк —
 * «выбрать всё» и индикаторы all/some считаются относительно них.
 */
export function useTableSelection(visibleIds: string[]): TableSelection {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const allChecked = visibleIds.length > 0 && visibleIds.every((id) => selected.has(id));
  const someChecked = visibleIds.some((id) => selected.has(id));

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const toggleAll = (checked: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) visibleIds.forEach((id) => next.add(id));
      else visibleIds.forEach((id) => next.delete(id));
      return next;
    });

  const clear = () => setSelected(new Set());

  return {
    selected,
    count: selected.size,
    isSelected: (id) => selected.has(id),
    allChecked,
    someChecked,
    toggle,
    toggleAll,
    clear,
  };
}
