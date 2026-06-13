import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ROUTES } from '@/app/routes';
import { Initials } from '@/components/ui/initials';
import { Button } from '@/components/ui/button';
import { useModals } from '@/components/modals/modals-context';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Building2,
  Calendar,
  ChevronLeft,
  MessageSquare,
  MoreHorizontal,
  Phone,
  SquarePen,
  Star,
} from '@/components/icons';
import type { TrainerDetail } from '@/features/trainers/detail';

const HERO_BTN = 'h-[38px] gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold';

function Meta({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Icon className="size-[13px] shrink-0 text-fg-subtle" />
      {children}
    </span>
  );
}

export function TrainerHero({ trainer: t }: { trainer: TrainerDetail }) {
  const { open } = useModals();
  const navigate = useNavigate();

  const archive = () =>
    open('confirm', {
      confirm: {
        title: 'Архивировать тренера?',
        message: (
          <>
            «{t.name}» переместится в архив. Текущие записи нужно будет перенести другим тренерам
            вручную.
          </>
        ),
        tone: 'danger',
        confirmLabel: 'Архивировать',
        onConfirm: () => {
          toast.success('Тренер архивирован', { description: t.name });
        },
      },
    });

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
          <Initials
            initials={t.initials}
            color={t.avatarGradient}
            className="size-[72px] rounded-[22px] text-[26px] sm:size-[84px] sm:text-[30px]"
          />
          <span className="absolute -bottom-1 -right-1 size-5 rounded-full bg-primary ring-[3px] ring-surface" />
        </div>

        <div className="min-w-[240px] flex-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-[22px] font-bold leading-[1.1] tracking-[-0.5px] sm:text-[24px]">
              {t.name}
            </h1>
            <span className="rounded-full bg-primary-soft px-[9px] py-[3px] text-[10.5px] font-bold uppercase tracking-[0.3px] text-primary-deep dark:text-primary">
              {t.statusLabel}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-3.5 gap-y-1.5 text-[12.5px] text-fg-muted">
            <span className="inline-flex items-center gap-1 font-semibold text-warning-deep">
              <Star className="size-3.5 fill-warning text-warning" />
              {t.rating.toFixed(1)}
            </span>
            <Meta icon={Building2}>{t.branch}</Meta>
            <Meta icon={Calendar}>{t.memberSince}</Meta>
            <Meta icon={Phone}>{t.phone}</Meta>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {t.specs.map((s) => (
              <span
                key={s}
                className="rounded-full bg-surface-3 px-[11px] py-[5px] text-[12px] font-semibold text-fg-muted"
              >
                {s}
              </span>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start max-sm:w-full">
          <Button variant="outline" className={HERO_BTN} onClick={() => navigate(ROUTES.messages)}>
            <MessageSquare className="size-[14px]" />
            <span className="max-sm:hidden">Написать</span>
          </Button>
          <Button
            className={HERO_BTN}
            onClick={() => open('trainer-form', { trainerForm: { trainerId: t.id } })}
          >
            <SquarePen className="size-[14px]" />
            <span className="max-sm:hidden">Редактировать</span>
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                aria-label="Ещё"
                className="size-[38px] shrink-0 rounded-full"
              >
                <MoreHorizontal className="size-[15px]" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[200px]">
              <DropdownMenuItem onSelect={() => navigate(ROUTES.schedule)}>
                Расписание тренера
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() => toast.success('Филиал изменён', { description: t.name })}
              >
                Сменить филиал
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() =>
                  toast.success('Экспорт готов', { description: 'PDF · профиль и выплаты' })
                }
              >
                Экспорт профиля
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-danger focus:text-danger" onSelect={archive}>
                Архивировать
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
}
