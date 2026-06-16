/**
 * VisitsList — список визитов с реальными данными (Phase 103-02 ATT-01).
 *
 * Рендерит строки из реального VisitResponse: инициалы + clientName + дата/канал +
 * время + чекедInBy. Оптимистичные строки (_optimistic: true) → opacity-60 + Loader2.
 * Пустые состояния: нет визитов в диапазоне / нет визитов вообще.
 * Серверная пагинация через существующий компонент Pagination.
 */
import { Loader2, Activity } from '@/components/icons';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Pagination } from '@/components/data/Pagination';
import { formatDateRu, formatTime, getInitials } from '@/lib/format';
import { cn } from '@/lib/cn';
import type { VisitData } from '@/features/visits/schemas';

// ---------------------------------------------------------------------------
// Канальные метки
// ---------------------------------------------------------------------------

const CHANNEL_LABELS: Record<string, string> = {
  reception: 'Ресепшн',
  qr: 'QR',
  app: 'Приложение',
};

// ---------------------------------------------------------------------------
// Строка визита
// ---------------------------------------------------------------------------

interface VisitRowProps {
  visit: VisitData & { _optimistic?: boolean; clientName?: string };
}

function VisitRow({ visit }: VisitRowProps) {
  const isOptimistic = visit._optimistic === true;
  const name = visit.clientName ?? `Клиент ${visit.clientId.slice(0, 8)}`;
  const initials = getInitials(name);
  const channelLabel = CHANNEL_LABELS[visit.channel] ?? visit.channel;

  return (
    <div
      className={cn(
        'flex items-center gap-3 border-t-[0.5px] border-border px-4 py-3 transition-colors hover:bg-surface-2 first:border-t-0',
        isOptimistic && 'opacity-60',
      )}
    >
      {/* Инициалы */}
      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-surface-3 text-[12px] font-semibold text-fg-muted">
        {initials}
      </span>

      {/* Имя и дата·канал */}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13.5px] font-semibold tracking-[-0.1px]">{name}</span>
        <span className="mt-0.5 block truncate text-[11.5px] text-fg-subtle">
          {formatDateRu(visit.gymDate, 'dd.MM.yy')} · {channelLabel}
        </span>
      </span>

      {/* Время / спиннер */}
      <span className="shrink-0 text-right">
        {isOptimistic ? (
          <Loader2 className="size-3.5 animate-spin text-fg-subtle" />
        ) : (
          <span className="text-[12.5px] font-semibold tabular-nums text-fg-muted">
            {formatTime(visit.checkedInAt)}
          </span>
        )}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// VisitsList
// ---------------------------------------------------------------------------

interface VisitsListProps {
  items: (VisitData & { _optimistic?: boolean; clientName?: string })[];
  total: number;
  page: number;
  pageSize: number;
  hasFilter: boolean;
  onPageChange: (page: number) => void;
}

export function VisitsList({
  items,
  total,
  page,
  pageSize,
  hasFilter,
  onPageChange,
}: VisitsListProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  if (items.length === 0) {
    if (hasFilter) {
      return (
        <EmptyState
          icon={Activity}
          title="Нет визитов"
          message="За выбранный период визитов не зафиксировано."
        />
      );
    }
    return (
      <EmptyState
        icon={Activity}
        title="Визитов пока нет"
        message="Зафиксируйте первый визит, нажав «Чек-ин»."
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border-[0.5px] border-border bg-surface">
      {items.map((visit) => (
        <VisitRow key={visit.id} visit={visit} />
      ))}
      {pageCount > 1 && (
        <Pagination
          page={page}
          pageCount={pageCount}
          shown={items.length}
          total={total}
          noun="визитов"
          onPageChange={onPageChange}
        />
      )}
    </div>
  );
}
