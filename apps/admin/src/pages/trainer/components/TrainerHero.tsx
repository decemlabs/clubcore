/**
 * TrainerHero — Phase 102-02 TRN-01.
 *
 * Wired to real TrainerData: fullName, specialization, photoUrl (fallback to initials),
 * isActive badge. Phone shown when available.
 * Owner edit opens TrainerFormModal via local state (not global modals context).
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ROUTES } from '@/app/routes';
import { Initials } from '@/components/ui/initials';
import { Button } from '@/components/ui/button';
import { ChevronLeft, MessageSquare, Phone, SquarePen } from '@/components/icons';
import { getInitials } from '@/lib/format';
import type { TrainerData } from '@/features/trainers/schemas';
import { TrainerFormModal } from '@/components/modals/TrainerFormModal';
import { can } from '@/shared/session/can';
import type { Role } from '@/shared/session/types';

const HERO_BTN = 'h-[38px] gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold';

export function TrainerHero({ trainer: t, role }: { trainer: TrainerData; role: Role }) {
  const navigate = useNavigate();
  const [editOpen, setEditOpen] = useState(false);
  const initials = getInitials(t.fullName);

  return (
    <div>
      <Link
        to={ROUTES.trainers}
        className="mb-3.5 inline-flex items-center gap-1.5 text-[12.5px] font-semibold tracking-[-0.1px] text-fg-muted transition-colors hover:text-fg"
      >
        <ChevronLeft className="size-3.5" strokeWidth={2.4} />
        Все тренеры
      </Link>

      <div className="flex flex-wrap items-start gap-5 rounded-lg border-[0.5px] border-border bg-surface p-5 shadow-2 sm:p-[22px]">
        <div className="relative shrink-0">
          {t.photoUrl ? (
            <img
              src={t.photoUrl}
              alt={t.fullName}
              className="size-[72px] rounded-[22px] object-cover sm:size-[84px]"
            />
          ) : (
            <Initials
              initials={initials}
              color="linear-gradient(135deg,#8b5cf6,#ec4899)"
              className="size-[72px] rounded-[22px] text-[26px] sm:size-[84px] sm:text-[30px]"
            />
          )}
          <span
            className={`absolute -bottom-1 -right-1 size-5 rounded-full ring-[3px] ring-surface ${t.isActive ? 'bg-primary' : 'bg-fg-subtle'}`}
          />
        </div>

        <div className="min-w-[240px] flex-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-[22px] font-bold leading-[1.1] tracking-[-0.5px] sm:text-[24px]">
              {t.fullName}
            </h1>
            <span
              className={`rounded-full px-[9px] py-[3px] text-[10.5px] font-bold uppercase tracking-[0.3px] ${t.isActive ? 'bg-primary-soft text-primary-deep dark:text-primary' : 'bg-surface-3 text-fg-muted'}`}
            >
              {t.isActive ? 'Активна' : 'Неактивна'}
            </span>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-3.5 gap-y-1.5 text-[12.5px] text-fg-muted">
            {t.phone ? (
              <span className="inline-flex items-center gap-1.5">
                <Phone className="size-[13px] shrink-0 text-fg-subtle" />
                {t.phone}
              </span>
            ) : null}
          </div>

          {t.specialization ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {t.specialization
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean)
                .map((s) => (
                  <span
                    key={s}
                    className="rounded-full bg-surface-3 px-[11px] py-[5px] text-[12px] font-semibold text-fg-muted"
                  >
                    {s}
                  </span>
                ))}
            </div>
          ) : null}

          {t.bio ? <p className="mt-3 text-[13px] leading-relaxed text-fg-muted">{t.bio}</p> : null}
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start max-sm:w-full">
          <Button variant="outline" className={HERO_BTN} onClick={() => navigate(ROUTES.messages)}>
            <MessageSquare className="size-[14px]" />
            <span className="max-sm:hidden">Написать</span>
          </Button>
          {can(role, 'edit', 'trainers') && (
            <Button className={HERO_BTN} onClick={() => setEditOpen(true)}>
              <SquarePen className="size-[14px]" />
              <span className="max-sm:hidden">Редактировать</span>
            </Button>
          )}
        </div>
      </div>

      <TrainerFormModal open={editOpen} onOpenChange={setEditOpen} trainer={t} />
    </div>
  );
}
