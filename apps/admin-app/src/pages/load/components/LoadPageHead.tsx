/**
 * LoadPageHead — page header for the visits load dashboard (Phase 103-03).
 *
 * Removed: mock avg/peak subtitle props — replaced with period subtitle.
 * Actions: DateRangePicker passed as ReactNode.
 */
import type { ReactNode } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { formatDateRu } from '@/lib/format';

export function LoadPageHead({
  from,
  to,
  dateRangePicker,
}: {
  from: string;
  to: string;
  dateRangePicker: ReactNode;
}) {
  const fromLabel = formatDateRu(from, 'd MMM yyyy');
  const toLabel = formatDateRu(to, 'd MMM yyyy');

  return (
    <PageHeader
      title="Загруженность"
      subtitle={<>{fromLabel} – {toLabel}</>}
      actions={dateRangePicker}
      actionsClassName="items-start"
    />
  );
}
