/**
 * CashboxPageHead — page header for the cash ledger (Phase 103-03).
 *
 * Shows title «Касса», subtitle with date range + total count,
 * and the DateRangePicker in the actions area.
 * ShiftPill and shift-related state removed — no shift endpoint.
 */
import type { ReactNode } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { formatDateRu } from '@/lib/format';

export function CashboxPageHead({
  from,
  to,
  total,
  dateRangePicker,
}: {
  from: string;
  to: string;
  total: number;
  dateRangePicker: ReactNode;
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
      actions={dateRangePicker}
      actionsClassName="items-start"
    />
  );
}
