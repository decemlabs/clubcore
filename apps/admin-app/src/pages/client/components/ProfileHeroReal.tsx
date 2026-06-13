/**
 * Profile head component wired to real ClientData (Phase 101 CLI-01).
 *
 * Renders name (lastName + firstName + middleName), phone, email, tags,
 * createdAt. Does NOT render mock-only fields (status pill, subscription,
 * memberSinceLabel, tenure) — those stay deferred to Plan 04 when membership
 * data is wired to the client detail page.
 */
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ROUTES } from '@/app/routes'
import { Initials } from '@/components/ui/initials'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useModals } from '@/components/modals/modals-context'
import { formatDateRu } from '@/lib/format'
import {
  Calendar,
  ChevronLeft,
  Mail,
  MessageSquare,
  MoreHorizontal,
  Phone,
  Send,
  Tag,
} from '@/components/icons'
import type { LucideIcon } from 'lucide-react'
import type { ClientData } from '@/features/clients/schemas'

function Meta({ icon: Icon, children }: { icon: LucideIcon; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Icon className="size-[13px] shrink-0 text-fg-subtle" />
      {children}
    </span>
  )
}

const GENDER_LABEL: Record<string, string> = {
  male: 'Мужской',
  female: 'Женский',
}

const HERO_BTN = 'h-[38px] gap-[7px] rounded-full px-[18px] text-[13.5px] font-semibold'

export function ProfileHeroReal({ client }: { client: ClientData }) {
  const { open } = useModals()
  const navigate = useNavigate()

  const initials = [client.lastName, client.firstName]
    .filter(Boolean)
    .map((s) => s[0]?.toUpperCase() ?? '')
    .join('')
    .slice(0, 2)

  const fullName = [client.lastName, client.firstName, client.middleName]
    .filter(Boolean)
    .join(' ')

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
        <Initials initials={initials} color="linear-gradient(135deg,#2dd4a4,#059669)" className="size-14 text-xl sm:size-[72px] sm:text-[26px]" />

        <div className="min-w-[240px] flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[22px] font-bold leading-[1.1] tracking-[-0.6px] sm:text-[26px]">
              {fullName}
            </h1>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12.5px] text-fg-muted">
            <Meta icon={Phone}>{client.phone}</Meta>
            {client.email && <Meta icon={Mail}>{client.email}</Meta>}
            {client.birthday && (
              <Meta icon={Calendar}>
                {formatDateRu(client.birthday, 'd MMMM yyyy')}
              </Meta>
            )}
            {client.gender && (
              <span className="text-[12.5px] text-fg-muted">
                {GENDER_LABEL[client.gender] ?? client.gender}
              </span>
            )}
            {client.telegramUserId && (
              <Meta icon={Send}>Telegram</Meta>
            )}
            <Meta icon={Calendar}>
              с{' '}
              <b className="font-semibold text-fg">
                {formatDateRu(client.createdAt, 'd MMMM yyyy')}
              </b>
            </Meta>
          </div>
          {client.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <Tag className="size-3 text-fg-subtle" />
              {client.tags.map((t) => (
                <span
                  key={t}
                  className="inline-flex h-[22px] items-center rounded-full border-[0.5px] border-border bg-surface-2 px-2 text-[11px] font-medium text-fg-muted"
                >
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 self-center max-sm:w-full">
          <Button variant="outline" className={HERO_BTN} onClick={() => navigate(ROUTES.messages)}>
            <MessageSquare className="size-[14px]" />
            <span className="max-sm:hidden">Написать</span>
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
                onSelect={() =>
                  toast.success('Экспорт готов', { description: 'PDF · карточка клиента' })
                }
              >
                Экспорт карточки
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-danger focus:text-danger" onSelect={() => {
                open('confirm', {
                  confirm: {
                    title: 'Удалить клиента?',
                    message: `«${fullName}» будет помечен как удалённый. Активные абонементы будут аннулированы.`,
                    tone: 'danger',
                    confirmLabel: 'Удалить',
                    onConfirm: () => {
                      toast.info('Удаление доступно из карточки редактирования')
                    },
                  },
                })
              }}>
                Удалить клиента
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  )
}
