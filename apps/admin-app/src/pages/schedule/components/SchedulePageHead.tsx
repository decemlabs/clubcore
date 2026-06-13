import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/layout/PageHeader';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { Download } from '@/components/icons';
import type { ScheduleData } from '@/features/schedule/types';

export type CalView = 'day' | 'week' | 'month';

const VIEW_OPTIONS: SegmentedOption<CalView>[] = [
  { value: 'day', label: 'День' },
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
];

export function SchedulePageHead({
  data,
  view,
  onViewChange,
}: {
  data: ScheduleData;
  view: CalView;
  onViewChange: (view: CalView) => void;
}) {
  return (
    <PageHeader
      title="Расписание"
      subtitle={
        <>
          <b className="font-semibold text-fg">{data.rangeLabel}</b> · {data.sessionsWeek} сессий за
          неделю · {data.plannedToday} запланировано сегодня
        </>
      }
      actionsClassName="max-sm:-mx-4 max-sm:overflow-x-auto max-sm:px-4 max-sm:[scrollbar-width:none]"
      actions={
        <>
          <Segmented
            options={VIEW_OPTIONS}
            value={view}
            onChange={onViewChange}
            ariaLabel="Вид календаря"
          />
          <Button
            variant="outline"
            className="h-[38px] shrink-0 gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold max-sm:w-[38px] max-sm:px-0"
          >
            <Download className="size-[14px]" />
            <span className="max-sm:hidden">Экспорт</span>
          </Button>
        </>
      }
    />
  );
}
