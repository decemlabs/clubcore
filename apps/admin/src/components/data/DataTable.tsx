import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { ChevronDown } from '@/components/icons';
import { Checkbox } from '@/components/ui/Checkbox';
import type { TableSelection } from './useTableSelection';

export interface DataTableSort {
  key: string;
  dir: 'asc' | 'desc';
}

export interface ColumnDef<T> {
  id: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** Если задан — заголовок кликабельный, сортирует по этому ключу. */
  sortKey?: string;
  /** Доп. классы для <th> (ширина, скрытие по container-query и т.п.). */
  headClassName?: string;
  /** Доп. классы для <td>. */
  cellClassName?: string;
}

const TH_BASE =
  'bg-surface-2 px-3.5 py-3 text-left text-[11.5px] font-semibold uppercase tracking-[0.5px] text-fg-subtle whitespace-nowrap border-b-[0.5px] border-border';
const TD_BASE = 'border-b-[0.5px] border-border px-3.5 py-3 align-middle';

interface HeadCellProps {
  children: ReactNode;
  sortKey?: string;
  sort?: DataTableSort;
  onSort?: (key: string) => void;
  className?: string;
}

function HeadCell({ children, sortKey, sort, onSort, className }: HeadCellProps) {
  const sortable = sortKey != null && onSort != null;
  const active = sortKey != null && sort?.key === sortKey;
  return (
    <th
      scope="col"
      aria-sort={active ? (sort?.dir === 'asc' ? 'ascending' : 'descending') : undefined}
      className={cn(
        TH_BASE,
        sortable && 'cursor-pointer select-none hover:text-fg-muted',
        active && 'text-fg',
        className,
      )}
      onClick={sortable ? () => onSort(sortKey) : undefined}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        {active && (
          <ChevronDown
            className={cn('size-2.5 transition-transform', sort?.dir === 'asc' && 'rotate-180')}
            strokeWidth={2.4}
          />
        )}
      </span>
    </th>
  );
}

export interface DataTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  getRowId: (row: T) => string;
  sort?: DataTableSort;
  onSort?: (key: string) => void;
  /** Выбор строк: чекбокс-колонка слева + подсветка выбранных. */
  selection?: TableSelection;
  selectAllLabel?: string;
  rowLabel?: (row: T) => string;
  onRowClick?: (row: T) => void;
  rowClassName?: (row: T) => string;
  className?: string;
}

/**
 * Общая таблица данных: колонки задаются ColumnDef[] (header + render-prop cell),
 * опциональны сортировка по заголовку, выбор строк и клик по строке.
 * Семантическая разметка ради точного контроля стиля прототипов.
 */
export function DataTable<T>({
  data,
  columns,
  getRowId,
  sort,
  onSort,
  selection,
  selectAllLabel = 'Выбрать всё',
  rowLabel,
  onRowClick,
  rowClassName,
  className,
}: DataTableProps<T>) {
  const handleRowClick = (row: T) => (e: React.MouseEvent<HTMLTableRowElement>) => {
    if (
      (e.target as HTMLElement).closest(
        'a,button,input,label,[role="menu"],[data-slot="dropdown-menu-trigger"]',
      )
    )
      return;
    onRowClick?.(row);
  };

  return (
    <table className={cn('w-full border-separate border-spacing-0 text-[13px]', className)}>
      <thead>
        <tr>
          {selection && (
            <th className={cn(TH_BASE, 'w-9 pl-4 pr-0')}>
              <Checkbox
                checked={selection.allChecked}
                indeterminate={selection.someChecked && !selection.allChecked}
                onCheckedChange={selection.toggleAll}
                aria-label={selectAllLabel}
              />
            </th>
          )}
          {columns.map((col) => (
            <HeadCell
              key={col.id}
              sortKey={col.sortKey}
              sort={sort}
              onSort={onSort}
              className={col.headClassName}
            >
              {col.header}
            </HeadCell>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row) => {
          const id = getRowId(row);
          const checked = selection?.isSelected(id) ?? false;
          return (
            <tr
              key={id}
              onClick={onRowClick ? handleRowClick(row) : undefined}
              className={cn(
                'transition-colors [&>td]:bg-surface',
                onRowClick && 'cursor-pointer hover:[&>td]:bg-surface-2',
                checked && '[&>td]:!bg-[color-mix(in_oklab,var(--primary-soft)_50%,transparent)]',
                rowClassName?.(row),
              )}
            >
              {selection && (
                <td className={cn(TD_BASE, 'pl-4 pr-0')}>
                  <Checkbox
                    checked={checked}
                    onCheckedChange={() => selection.toggle(id)}
                    aria-label={rowLabel ? `Выбрать ${rowLabel(row)}` : 'Выбрать строку'}
                  />
                </td>
              )}
              {columns.map((col) => (
                <td key={col.id} className={cn(TD_BASE, col.cellClassName)}>
                  {col.cell(row)}
                </td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
