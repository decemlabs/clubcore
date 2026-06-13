import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/layout/PageHeader';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { Download } from '@/components/icons';
import type { TrainersSummary } from '@/features/trainers/types';

export type RosterView = 'cards' | 'table';

const VIEW_OPTIONS: SegmentedOption<RosterView>[] = [
  { value: 'cards', label: 'Карточки' },
  { value: 'table', label: 'Таблица' },
];

export function TrainersPageHead({
  summary,
  view,
  onViewChange,
}: {
  summary: TrainersSummary;
  view: RosterView;
  onViewChange: (view: RosterView) => void;
}) {
  return (
    <PageHeader
      title="Тренеры"
      subtitle={
        <>
          <b className="font-semibold text-fg">{summary.total}</b> в составе ·{' '}
          <b className="font-semibold text-fg">{summary.inGymToday}</b> сегодня в зале ·{' '}
          <b className="font-semibold text-fg">{summary.ptMonth} ПТ</b> в апреле · средний рейтинг{' '}
          <b className="font-semibold text-fg">{summary.avgRating.toFixed(2)}</b>
        </>
      }
      actionsClassName="max-sm:-mx-4 max-sm:overflow-x-auto max-sm:px-4 max-sm:[scrollbar-width:none]"
      actions={
        <>
          <Segmented
            options={VIEW_OPTIONS}
            value={view}
            onChange={onViewChange}
            ariaLabel="Вид списка"
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
