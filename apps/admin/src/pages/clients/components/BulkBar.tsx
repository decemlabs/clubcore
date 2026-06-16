import { CreditCard, Download, MessageSquare, Trash2 } from '@/components/icons';
import { useModals } from '@/components/modals/modals-context';
import { BulkBar as BaseBulkBar, type BulkAction } from '@/components/data/BulkBar';

/** Русская плюрализация «выбран / выбрано». */
function selectedLabel(n: number): string {
  const n1 = n % 10;
  const n100 = n % 100;
  let word = 'выбрано';
  if (n100 < 10 || n100 > 20) {
    if (n1 === 1) word = 'выбран';
    else if (n1 >= 2 && n1 <= 4) word = 'выбрано';
  }
  return `${n} ${word}`;
}

export function BulkBar({ count, onClear }: { count: number; onClear: () => void }) {
  const { open } = useModals();
  const actions: BulkAction[] = [
    { key: 'message', label: 'Сообщение', icon: MessageSquare },
    { key: 'extend', label: 'Продлить', icon: CreditCard, onClick: () => open('extend') },
    { key: 'export', label: 'Экспорт', icon: Download },
    { key: 'archive', label: 'Архив', icon: Trash2, danger: true },
  ];
  return (
    <BaseBulkBar count={count} label={selectedLabel(count)} onClear={onClear} actions={actions} />
  );
}
