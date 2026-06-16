/**
 * RosterCard — Phase 102-02 TRN-01.
 *
 * Wired to real TrainerData (fullName, specialization, isActive, photoUrl).
 * Owner-only edit/delete affordances gated by can() props.
 * Avatar: photoUrl if present, otherwise initials via getInitials().
 */
import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/cn'
import { ROUTES } from '@/app/routes'
import { Initials } from '@/components/ui/initials'
import { Calendar, ChevronRight, MessageSquare, Pencil, Trash2 } from '@/components/icons'
import type { TrainerData } from '@/features/trainers/schemas'
import { getInitials } from '@/lib/format'

const FOOT_BTN =
  'inline-flex h-[30px] items-center gap-1.5 rounded-lg px-2.5 text-[12px] font-semibold text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

export function RosterCard({
  trainer: t,
  canEdit,
  canDelete,
  onEdit,
  onDelete,
}: {
  trainer: TrainerData
  canEdit: boolean
  canDelete: boolean
  onEdit: (trainer: TrainerData) => void
  onDelete: (trainer: TrainerData) => void
}) {
  const navigate = useNavigate()
  const initials = getInitials(t.fullName)

  return (
    <article
      onClick={() => navigate(ROUTES.trainer(t.id))}
      className="group/card relative flex cursor-pointer flex-col overflow-hidden rounded-lg border-[0.5px] border-border bg-surface shadow-1 transition-[border-color,box-shadow] hover:border-border-strong hover:shadow-2"
    >
      {/* Owner-only edit/delete actions — top-right corner */}
      {(canEdit || canDelete) && (
        <div
          className="absolute right-3 top-3 z-10 flex gap-1"
          onClick={(e) => e.stopPropagation()}
        >
          {canEdit && (
            <button
              type="button"
              aria-label="Редактировать тренера"
              onClick={(e) => {
                e.stopPropagation()
                onEdit(t)
              }}
              className="grid size-8 place-items-center rounded-full border-[0.5px] border-border bg-surface text-fg-muted transition-colors hover:border-border-strong hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Pencil className="size-[15px]" />
            </button>
          )}
          {canDelete && (
            <button
              type="button"
              aria-label="Удалить тренера"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(t)
              }}
              className="grid size-8 place-items-center rounded-full border-[0.5px] border-border bg-surface text-fg-muted transition-colors hover:border-danger hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Trash2 className="size-[15px]" />
            </button>
          )}
        </div>
      )}

      <div className="flex items-start gap-3 p-[18px] pb-3.5">
        <div className="relative shrink-0">
          {t.photoUrl ? (
            <img
              src={t.photoUrl}
              alt={t.fullName}
              className="size-[52px] rounded-2xl object-cover"
            />
          ) : (
            <Initials
              initials={initials}
              color="linear-gradient(135deg,#8b5cf6,#ec4899)"
              className="size-[52px] rounded-2xl text-[18px]"
            />
          )}
          <span
            className={cn(
              'absolute -bottom-0.5 -right-0.5 size-3.5 rounded-full ring-[2.5px] ring-surface',
              t.isActive ? 'bg-primary' : 'bg-fg-subtle',
            )}
          />
        </div>

        <div className="min-w-0 flex-1">
          <div className="truncate text-[15.5px] font-bold leading-tight tracking-[-0.2px]">
            {t.fullName}
          </div>
          <div className="mt-0.5 truncate text-[12.5px] text-fg-muted">
            {t.specialization ?? '—'}
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-1 gap-y-0.5 text-[11.5px] text-fg-subtle">
            <span
              className={cn(
                'rounded-full px-[9px] py-[3px] text-[10.5px] font-bold uppercase tracking-[0.3px]',
                t.isActive
                  ? 'bg-primary-soft text-primary-deep dark:text-primary'
                  : 'bg-surface-3 text-fg-muted',
              )}
            >
              {t.isActive ? 'Активна' : 'Неактивна'}
            </span>
          </div>
        </div>
      </div>

      {t.bio ? (
        <div className="px-[18px] pb-3.5 text-[12.5px] leading-relaxed text-fg-muted line-clamp-2">
          {t.bio}
        </div>
      ) : null}

      <div className="mt-auto flex items-center gap-1 border-t-[0.5px] border-border px-3 py-2">
        <button
          type="button"
          className={FOOT_BTN}
          onClick={(e) => {
            e.stopPropagation()
            navigate(ROUTES.schedule)
          }}
        >
          <Calendar className="size-3.5" />
          Расписание
        </button>
        <button
          type="button"
          className={FOOT_BTN}
          onClick={(e) => {
            e.stopPropagation()
            navigate(ROUTES.messages)
          }}
        >
          <MessageSquare className="size-3.5" />
          Написать
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            navigate(ROUTES.trainer(t.id))
          }}
          className="ml-auto inline-flex h-[30px] items-center gap-1 rounded-lg px-3 text-[12px] font-semibold text-fg transition-colors hover:bg-fg hover:text-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-primary dark:hover:text-[#06120c]"
        >
          Профиль
          <ChevronRight className="size-3.5" strokeWidth={2.4} />
        </button>
      </div>
    </article>
  )
}
