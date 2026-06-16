/**
 * TrainersPageHead — Phase 102-02 TRN-01.
 *
 * Replaces mock TrainersSummary with real total count from GET /api/v1/trainers.
 * Adds owner-only create button.
 */
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/layout/PageHeader'
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented'
import { Download, UserPlus } from '@/components/icons'

export type RosterView = 'cards' | 'table'

const VIEW_OPTIONS: SegmentedOption<RosterView>[] = [
  { value: 'cards', label: 'Карточки' },
  { value: 'table', label: 'Таблица' },
]

export function TrainersPageHead({
  total,
  view,
  onViewChange,
  canCreate,
  onCreateClick,
}: {
  total: number
  view: RosterView
  onViewChange: (view: RosterView) => void
  canCreate: boolean
  onCreateClick: () => void
}) {
  return (
    <PageHeader
      title="Тренеры"
      subtitle={`Тренеров: ${total}`}
      actionsClassName="max-sm:-mx-4 max-sm:overflow-x-auto max-sm:px-4 max-sm:[scrollbar-width:none]"
      actions={
        <>
          <Segmented
            options={VIEW_OPTIONS}
            value={view}
            onChange={onViewChange}
            ariaLabel="Вид списка"
          />
          {canCreate && (
            <Button
              variant="outline"
              className="h-[38px] shrink-0 gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold max-sm:w-[38px] max-sm:px-0"
              onClick={onCreateClick}
            >
              <UserPlus className="size-[14px]" />
              <span className="max-sm:hidden">Добавить тренера</span>
            </Button>
          )}
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
  )
}
