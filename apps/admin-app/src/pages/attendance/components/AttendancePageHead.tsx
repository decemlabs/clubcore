/**
 * AttendancePageHead — шапка страницы «Посещаемость» (Phase 103-02).
 *
 * Добавляет кнопку «Чек-ин» (UserCheck) для обоих ролей (reception + owner).
 * Кнопка открывает CheckInModal через useModals().open('checkin').
 * dateRangePicker — опциональный DateRangePicker, пробрасывается из AttendancePage.
 */
import type { ReactNode } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { UserCheck } from '@/components/icons';
import { useModals } from '@/components/modals/modals-context';

interface AttendancePageHeadProps {
  subtitle?: string;
  dateRangePicker?: ReactNode;
}

export function AttendancePageHead({ subtitle, dateRangePicker }: AttendancePageHeadProps) {
  const { open } = useModals();

  return (
    <PageHeader
      title="Посещаемость"
      subtitle={subtitle}
      actions={
        <div className="flex flex-col items-end gap-2 sm:flex-row sm:items-start">
          {dateRangePicker}
          <button
            type="button"
            onClick={() => open('checkin')}
            className="inline-flex h-[38px] shrink-0 items-center gap-[7px] rounded-full bg-fg px-[14px] text-[13px] font-semibold text-bg transition-colors hover:bg-black dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
          >
            <UserCheck className="size-[14px]" strokeWidth={2.2} />
            Чек-ин
          </button>
        </div>
      }
      actionsClassName="items-start"
    />
  );
}
