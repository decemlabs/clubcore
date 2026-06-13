import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ROUTES } from '@/app/routes';
import { Initials } from '@/components/ui/initials';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useModals } from '@/components/modals/modals-context';
import { StatusPill } from '@/features/clients/components/StatusPill';
import {
  Calendar,
  ChevronLeft,
  Clock,
  CreditCard,
  Mail,
  MessageSquare,
  MoreHorizontal,
  Phone,
} from '@/components/icons';
import type { LucideIcon } from 'lucide-react';
import type { ClientDetail } from '@/features/clients/detail';

function Meta({ icon: Icon, children }: { icon: LucideIcon; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Icon className="size-[13px] shrink-0 text-fg-subtle" />
      {children}
    </span>
  );
}

const HERO_BTN = 'h-[38px] gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold';

export function ProfileHero({ client }: { client: ClientDetail }) {
  const { open } = useModals();
  const navigate = useNavigate();

  const archive = () =>
    open('confirm', {
      confirm: {
        title: 'Архивировать клиента?',
        message: <>«{client.name}» переместится в архив. Активный абонемент будет приостановлен.</>,
        tone: 'danger',
        confirmLabel: 'Архивировать',
        onConfirm: () => {
          toast.success('Клиент архивирован', { description: client.name });
        },
      },
    });

  return (
    <div>
      <Link
        to={ROUTES.clients}
        className="mb-3.5 inline-flex items-center gap-1.5 text-[12.5px] font-semibold tracking-[-0.1px] text-fg-muted transition-colors hover:text-fg"
      >
        <ChevronLeft className="size-3.5" strokeWidth={2.4} />
        Все клиенты
      </Link>

      <div className="flex flex-wrap items-start gap-5 rounded-lg border-[0.5px] border-border bg-surface p-5 shadow-1 sm:p-[22px]">
        <Initials
          initials={client.initials}
          color={client.color}
          className="size-14 text-xl sm:size-[72px] sm:text-[26px]"
        />

        <div className="min-w-[240px] flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[22px] font-bold leading-[1.1] tracking-[-0.6px] sm:text-[26px]">
              {client.name}
            </h1>
            <StatusPill status={client.status} label={client.statusLabel} />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12.5px] text-fg-muted">
            <Meta icon={Phone}>{client.phone}</Meta>
            <Meta icon={Mail}>{client.email}</Meta>
            <Meta icon={Calendar}>{client.birthday}</Meta>
            <Meta icon={Clock}>
              {client.memberSinceLabel} · <b className="font-semibold text-fg">{client.tenure}</b>
            </Meta>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-center max-sm:w-full">
          <Button
            className={HERO_BTN}
            onClick={() => open('extend', { extend: { clientName: client.name } })}
          >
            <CreditCard className="size-[14px]" />
            <span className="max-sm:hidden">Продлить со скидкой</span>
          </Button>
          <Button variant="outline" className={HERO_BTN} onClick={() => navigate(ROUTES.messages)}>
            <MessageSquare className="size-[14px]" />
            <span className="max-sm:hidden">Написать</span>
          </Button>
          <Button variant="outline" className={HERO_BTN} onClick={() => open('book')}>
            <Calendar className="size-[14px]" />
            <span className="max-sm:hidden">Записать</span>
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
              <DropdownMenuItem
                onSelect={() => open('edit-client', { editClient: { clientId: client.id } })}
              >
                Редактировать
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() => open('subscription', { subscription: { screen: 'history' } })}
              >
                История абонемента
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() =>
                  toast.success('Экспорт готов', { description: 'PDF · карточка клиента' })
                }
              >
                Экспорт карточки
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
