import { PageHeader } from '@/components/layout/PageHeader';
import { formatWeekdayLongRu } from '@/lib/format';
import { mskTodayISO } from '@/lib/format';

interface PageHeadProps {
  fullName?: string;
  bookingsToday: number;
}

export function PageHead({ fullName, bookingsToday }: PageHeadProps) {
  const today = mskTodayISO();
  const dateLabel = formatWeekdayLongRu(today);
  const greeting = fullName ? fullName.split(' ')[0] : 'вас';

  return (
    <PageHeader
      title={dateLabel}
      subtitle={
        <>
          Привет, {greeting}! Сегодня в зале{' '}
          <b className="font-semibold text-fg">{bookingsToday} тренировок</b>.
        </>
      }
    />
  );
}
