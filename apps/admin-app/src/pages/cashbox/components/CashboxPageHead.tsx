/**
 * CashboxPageHead — page header for the cash ledger (Phase 103-03, updated Phase 116-03).
 *
 * Shows title «Касса», subtitle with date range + total count,
 * and the DateRangePicker in the actions area.
 * Phase 116-03: optional exportButton slot for owner-gated «Экспорт CSV».
 */
import type { ReactNode } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { formatDateRu } from '@/lib/format';

export function CashboxPageHead({
  from,
  to,
  total,
  dateRangePicker,
  exportButton,
}: {
  from: string;
  to: string;
  total: number;
  dateRangePicker: ReactNode;
  exportButton?: ReactNode;
}) {
  const fromLabel = formatDateRu(from, 'd MMM yyyy');
  const toLabel = formatDateRu(to, 'd MMM yyyy');

  return (
    <PageHeader
      title="Касса"
      subtitle={
        <>
          {fromLabel} – {toLabel} · {total} операций
        </>
      }
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {dateRangePicker}
          {exportButton}
        </div>
      }
      actionsClassName="items-start"
    />
  );
}
