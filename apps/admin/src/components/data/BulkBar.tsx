import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Checkbox } from '@/components/ui/Checkbox';

export interface BulkAction {
  key: string;
  label: string;
  icon: LucideIcon;
  danger?: boolean;
  onClick?: () => void;
}

/**
 * Панель массовых действий над выбранными строками: чекбокс снятия выделения,
 * счётчик и кнопки-действия. Появляется над таблицей при наличии выбора.
 */
export function BulkBar({
  count,
  label,
  onClear,
  actions,
}: {
  count: number;
  /** Готовая подпись («3 выбрано»). По умолчанию — само число. */
  label?: string;
  onClear: () => void;
  actions: BulkAction[];
}) {
  return (
    <div className="flex items-center gap-3 overflow-x-auto border-b-[0.5px] border-border bg-surface-2 px-4 py-2.5 text-[13px] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <Checkbox
        checked
        onCheckedChange={(c) => {
          if (!c) onClear();
        }}
        aria-label="Снять выделение"
      />
      <span className="shrink-0 rounded-full bg-fg px-2.5 py-[3px] text-xs font-bold tabular-nums text-bg">
        {label ?? count}
      </span>

      <div className="ml-auto flex shrink-0 items-center gap-2">
        {actions.map(({ key, label: actionLabel, icon: Icon, danger, onClick }) => (
          <button
            key={key}
            type="button"
            onClick={onClick}
            className={cn(
              'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border-[0.5px] border-border bg-surface px-3.5 py-1.5 text-[12.5px] font-semibold transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              danger ? 'text-danger' : 'text-fg',
            )}
          >
            <Icon className="size-3" strokeWidth={2} />
            {actionLabel}
          </button>
        ))}
      </div>
    </div>
  );
}
