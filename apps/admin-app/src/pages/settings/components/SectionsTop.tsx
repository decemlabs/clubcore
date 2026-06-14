import { useState } from 'react'
import { toast } from 'sonner'
import { cn } from '@/lib/cn'
import { Initials } from '@/components/ui/initials'
import { Skeleton } from '@/components/ui/skeleton'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { useModals } from '@/components/modals/modals-context'
import {
  Activity,
  Building2,
  Calendar,
  Check,
  ChevronDown,
  Clock,
  CreditCard,
  Loader2,
  Lock,
  Monitor,
  Smartphone,
  Trash2,
  User,
} from '@/components/icons'
import {
  Chip,
  GhostBtn,
  RadioGroup,
  SectionCard,
  SelectField,
  SettingRow,
  Stepper,
  TextArea,
  TextField,
  Toggle,
} from '@/components/settings/controls'
import { useSession } from '@/features/auth/api'
import { useSessions, useRevokeSession, useRevokeCurrentSession } from '@/features/settings/api'
import { formatRelativeRu, getInitials } from '@/lib/format'

const ID_PROFILE = 'profile'
const ID_SECURITY = 'security'
const ID_BRANCH = 'branch'
const ID_HOURS = 'hours'
const ID_BOOKING = 'booking'
const ID_PAYMENTS = 'payments'

function ActionPill({ icon: Icon, children }: { icon?: typeof Check; children: React.ReactNode }) {
  return (
    <span className="inline-flex h-[30px] items-center gap-1.5 rounded-full border-[0.5px] border-border bg-surface-2 px-3 text-[12px] font-semibold text-fg">
      {Icon ? <Icon className="size-3.5" /> : null}
      {children}
    </span>
  )
}

// Profile edit deferred — no PATCH /auth/me endpoint (Phase 104).
export function ProfileSection() {
  const { data, isPending, isError, refetch } = useSession()

  const ROLE_LABEL: Record<string, string> = {
    owner: 'Владелец',
    reception: 'Ресепшн',
  }

  return (
    <SectionCard
      id={ID_PROFILE}
      icon={User}
      title="Профиль"
      desc="Личные данные. Редактирование недоступно — обратитесь к владельцу."
    >
      {isPending ? (
        <div className="flex items-center gap-4 py-4">
          <Skeleton className="size-16 rounded-full" />
          <div className="flex flex-col gap-2">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-3 w-36" />
          </div>
        </div>
      ) : isError || !data ? (
        <div className="py-4 text-[12px] text-fg-muted">
          Не удалось загрузить профиль.{' '}
          <button
            type="button"
            onClick={() => void refetch()}
            className="font-semibold text-fg hover:underline"
          >
            Повторить
          </button>
        </div>
      ) : (
        <>
          <SettingRow first label="Имя и должность">
            <div className="flex items-center gap-3">
              <Initials
                initials={getInitials(data.fullName)}
                color="linear-gradient(135deg,#2dd4a4,#059669)"
                className="size-16 text-[20px]"
              />
              <div className="min-w-0">
                <div className="text-[14px] font-bold text-fg">{data.fullName}</div>
                <div className="mt-0.5 text-[13px] text-fg-muted">{data.email}</div>
                <div className="mt-1.5">
                  <span
                    className={cn(
                      'inline-flex h-[22px] items-center rounded-full px-2.5 text-[11.5px] font-semibold',
                      data.role === 'owner'
                        ? 'bg-primary-soft text-primary-deep dark:text-primary'
                        : 'bg-surface-3 text-fg-muted',
                    )}
                  >
                    {ROLE_LABEL[data.role] ?? data.role}
                  </span>
                </div>
              </div>
            </div>
            <p className="mt-3 text-[11.5px] text-fg-subtle">
              Для изменения данных обратитесь к владельцу.
            </p>
          </SettingRow>
          <SettingRow label="Тема оформления" hint="Смена между светлой и тёмной темой.">
            <ThemeToggle />
          </SettingRow>
        </>
      )}
    </SectionCard>
  )
}

/** Map session channel code to a human-readable label. */
function channelLabel(channel: string): string {
  if (channel === 'admin_web') return 'Браузер'
  if (channel === 'api') return 'API'
  return 'Браузер'
}

export function SecuritySection() {
  const { data: sessionsData, isPending, isError, refetch } = useSessions()
  const revokeSession = useRevokeSession()
  const revokeCurrentSession = useRevokeCurrentSession()
  const [revokingId, setRevokingId] = useState<string | null>(null)
  const { open } = useModals()

  const currentSession = sessionsData?.items.find((s) => s.isCurrent)

  function handleRevoke(familyId: string) {
    setRevokingId(familyId)
    revokeSession.mutate(familyId, {
      onSuccess: () => {
        toast.success('Сессия завершена')
      },
      onError: () => {
        toast.error('Не удалось завершить сессию. Попробуйте ещё раз.')
      },
      onSettled: () => {
        setRevokingId(null)
      },
    })
  }

  function handleLogoutEverywhere() {
    open('confirm', {
      confirm: {
        title: 'Завершить все сессии?',
        message: 'Все активные сессии, включая эту, будут завершены. Вам потребуется войти снова.',
        confirmLabel: 'Да, выйти',
        cancelLabel: 'Отмена',
        tone: 'danger',
        onConfirm: () => {
          if (!currentSession) return
          revokeCurrentSession.mutate(currentSession.familyId, {
            onError: () => {
              toast.error('Не удалось завершить сессию. Попробуйте ещё раз.')
            },
          })
        },
      },
    })
  }

  return (
    <SectionCard
      id={ID_SECURITY}
      icon={Lock}
      title="Безопасность"
      desc="Пароль, двухфакторная аутентификация, активные сессии и журнал входов."
      action={<ActionPill icon={Check}>2FA включён</ActionPill>}
    >
      <SettingRow
        first
        label="Пароль"
        hint="Последняя смена — 47 дней назад. Рекомендуем менять каждые 90 дней."
      >
        <GhostBtn>Сменить пароль</GhostBtn>
      </SettingRow>
      <SettingRow
        label="Двухфакторная аутентификация"
        hint="SMS-код приходит при входе с нового устройства."
      >
        <Toggle
          defaultChecked
          sectionId={ID_SECURITY}
          label="Включена · SMS на +7 (985) ••• 08-90"
          sub={
            <>
              Резервные коды сгенерированы 12 фев.{' '}
              <button
                type="button"
                onClick={() => toast.success('Резервные коды скачаны')}
                className="font-semibold text-primary-deep hover:underline dark:text-primary"
              >
                Скачать ещё раз
              </button>
            </>
          }
        />
      </SettingRow>
      <SettingRow label="Активные сессии" hint="Устройства, где вы вошли в систему.">
        <div className="flex flex-col gap-2">
          {isPending ? (
            <>
              <Skeleton className="h-[52px] w-full rounded-xl" />
              <Skeleton className="h-[52px] w-full rounded-xl" />
              <Skeleton className="h-[52px] w-full rounded-xl" />
            </>
          ) : isError || !sessionsData ? (
            <div className="text-[12px] text-fg-muted">
              Не удалось загрузить сессии.{' '}
              <button
                type="button"
                onClick={() => void refetch()}
                className="font-semibold text-fg hover:underline"
              >
                Повторить
              </button>
            </div>
          ) : (
            sessionsData.items.map((s) => {
              const isMobile = /mobile/i.test(s.userAgent ?? '')
              const Icon = isMobile ? Smartphone : Monitor
              const isRevoking = revokingId === s.familyId

              return (
                <div
                  key={s.familyId}
                  className="flex items-center gap-3 rounded-xl border-[0.5px] border-border bg-surface-2 px-3 py-2.5"
                >
                  <span
                    className={cn(
                      'grid size-8 shrink-0 place-items-center rounded-lg',
                      s.isCurrent
                        ? 'bg-primary-soft text-primary-deep dark:text-primary'
                        : 'bg-surface-3 text-fg-muted',
                    )}
                  >
                    <Icon className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-[12.5px] font-semibold">
                      <span className="truncate">{s.userAgent || 'Неизвестное устройство'}</span>
                      {s.isCurrent ? (
                        <span className="shrink-0 rounded-full bg-primary-soft px-1.5 py-px text-[9.5px] font-bold uppercase text-primary-deep dark:text-primary">
                          Сейчас
                        </span>
                      ) : null}
                    </div>
                    <div className="truncate text-[11px] text-fg-subtle">
                      {channelLabel(s.channel)} · {formatRelativeRu(s.lastUsedAt)}
                    </div>
                  </div>
                  {s.isCurrent ? (
                    <span className="shrink-0 text-[12px] text-fg-subtle">—</span>
                  ) : (
                    <button
                      type="button"
                      disabled={isRevoking}
                      onClick={() => handleRevoke(s.familyId)}
                      className="flex shrink-0 items-center gap-1 text-[12px] font-semibold text-danger hover:underline disabled:opacity-50"
                    >
                      {isRevoking ? <Loader2 className="size-3 animate-spin" /> : null}
                      Завершить
                    </button>
                  )}
                </div>
              )
            })
          )}
        </div>
        {!isPending && !isError && sessionsData && currentSession ? (
          <div className="mt-3">
            <GhostBtn danger onClick={handleLogoutEverywhere}>
              Выйти везде
            </GhostBtn>
          </div>
        ) : null}
      </SettingRow>
    </SectionCard>
  )
}

const DAYS: [string, string, string, boolean?, string?][] = [
  ['Понедельник', '07:00', '23:00', false, '— клуб «жаворонок» с 6:30'],
  ['Вторник', '07:00', '23:00'],
  ['Среда', '07:00', '23:00'],
  ['Четверг', '07:00', '23:00'],
  ['Пятница', '07:00', '22:00', false, '— раньше из-за уборки'],
  ['Суббота', '09:00', '22:00', true],
  ['Воскресенье', '09:00', '21:00', true, '— санитарный день первое вс месяца'],
]

export function BranchSection() {
  return (
    <SectionCard
      id={ID_BRANCH}
      icon={Building2}
      title="Филиал «Тверская»"
      desc="Карточка зала, которую видят клиенты в приложении и на сайте."
      action={<ActionPill icon={ChevronDown}>Тверская</ActionPill>}
    >
      <SettingRow first label="Название" hint="Используется в чеках, рассылках и на странице зала.">
        <div className="grid gap-2 sm:grid-cols-[110px_minmax(0,1fr)]">
          <TextField defaultValue="Тверская" placeholder="Короткое" sectionId={ID_BRANCH} />
          <TextField defaultValue="Мой зал · Тверская — Москва" sectionId={ID_BRANCH} />
        </div>
      </SettingRow>
      <SettingRow label="Адрес и координаты">
        <TextField
          defaultValue="Москва, ул. Тверская, 12, корп. 2, этаж −1"
          sectionId={ID_BRANCH}
        />
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <TextField defaultValue="55.764215" placeholder="широта" sectionId={ID_BRANCH} />
          <TextField defaultValue="37.605362" placeholder="долгота" sectionId={ID_BRANCH} />
        </div>
      </SettingRow>
      <SettingRow label="Контакты для клиентов">
        <div className="grid gap-2 sm:grid-cols-2">
          <TextField defaultValue="+7 (495) 411-08-90" sectionId={ID_BRANCH} />
          <TextField defaultValue="hello@moy-zal.ru" sectionId={ID_BRANCH} />
        </div>
      </SettingRow>
      <SettingRow label="Описание" hint="Показывается при выборе филиала и при первом визите.">
        <TextArea
          sectionId={ID_BRANCH}
          hint="347 / 500 символов"
          defaultValue="Камерный зал на 600 м² на Тверской. Силовая зона Hammer Strength, кардио TechnoGym, два зала групповых, сауна и хамам. Открыты с 2019 года, держим вместимость до 60 человек — без очередей к стойкам."
        />
      </SettingRow>
      <SettingRow label="Возможности зала" hint="Иконки показываются на карточке филиала.">
        <div className="flex flex-wrap items-center gap-1.5">
          {['Душевые', 'Сауна', 'Хамам', 'Парковка', 'Wi-Fi', 'Бассейн 25 м', 'Кафе'].map((c) => (
            <Chip key={c} tone="accent">
              {c}
            </Chip>
          ))}
          <Chip>Детская комната</Chip>
          <Chip>Беспл. полотенца</Chip>
          <GhostBtn>+ Возможность</GhostBtn>
        </div>
      </SettingRow>
      <SettingRow
        label="Вместимость"
        hint="Используется для тепловой карты загруженности и предупреждений."
      >
        <div className="flex flex-wrap items-center gap-3">
          <Stepper defaultValue={60} unit="человек" sectionId={ID_BRANCH} />
          <span className="text-[12px] text-fg-muted">
            Сейчас в зале — <b className="font-semibold text-fg">42</b> · среднее в час пик —{' '}
            <b className="font-semibold text-fg">54</b>
          </span>
        </div>
      </SettingRow>
    </SectionCard>
  )
}

export function HoursSection() {
  return (
    <SectionCard
      id={ID_HOURS}
      icon={Clock}
      title="График работы"
      desc="Часы открытия и плановые закрытия. Расписание тренировок ограничено этим окном."
      action={<ActionPill icon={Activity}>Копировать из «Парк»</ActionPill>}
    >
      <SettingRow first label="Режим работы зала">
        <div className="flex flex-col">
          {DAYS.map(([day, open, close, weekend, note], i) => (
            <div
              key={day}
              className={cn(
                'flex flex-wrap items-center gap-2 py-2 text-[12.5px]',
                i > 0 && 'border-t-[0.5px] border-border',
              )}
            >
              <span
                className={cn(
                  'w-[120px] font-semibold',
                  weekend && 'text-primary-deep dark:text-primary',
                )}
              >
                {day}
              </span>
              <input
                defaultValue={open}
                className={cn(
                  'h-8 w-[72px] rounded-lg border-[0.5px] border-border-strong bg-surface-2 px-2 text-center text-[12.5px] tabular-nums outline-none focus:border-fg-subtle',
                  weekend && 'opacity-60',
                )}
              />
              <span className="text-fg-subtle">—</span>
              <input
                defaultValue={close}
                className={cn(
                  'h-8 w-[72px] rounded-lg border-[0.5px] border-border-strong bg-surface-2 px-2 text-center text-[12.5px] tabular-nums outline-none focus:border-fg-subtle',
                  weekend && 'opacity-60',
                )}
              />
              {note ? <span className="text-[11.5px] text-fg-subtle">{note}</span> : null}
              <button
                type="button"
                aria-label="Закрыть день"
                className="ml-auto grid size-7 place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-danger-soft hover:text-danger"
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
      </SettingRow>
      <SettingRow label="Технические перерывы" hint="Зал закрыт, запись и приход недоступны.">
        <div className="flex flex-wrap items-center gap-1.5">
          <Chip tone="warn">⏸ Ежедн. 14:00–14:30 · уборка</Chip>
          <Chip tone="warn">⏸ Пн 06:00–07:00 · техобслуживание</Chip>
          <GhostBtn>+ Перерыв</GhostBtn>
        </div>
      </SettingRow>
      <SettingRow label="Праздники и закрытия" hint="Видны клиентам в приложении и в чат-боте.">
        <div className="flex flex-wrap items-center gap-1.5">
          <Chip>9 мая · сокращённый, 09:00–18:00</Chip>
          <Chip>12 июня · сокращённый, 09:00–18:00</Chip>
          <Chip>31 дек · 09:00–17:00</Chip>
          <Chip tone="warn">1–2 янв · закрыт</Chip>
          <GhostBtn>+ Дата</GhostBtn>
        </div>
      </SettingRow>
    </SectionCard>
  )
}

export function BookingSection() {
  return (
    <SectionCard
      id={ID_BOOKING}
      icon={Calendar}
      title="Запись и слоты"
      desc="Правила онлайн-записи и групповых тренировок. Влияет на приложение клиента и бота в Telegram."
    >
      <SettingRow first label="Шаг расписания" hint="Минимальная длительность слота тренировки.">
        <RadioGroup
          options={['15 мин', '30 мин', '60 мин', '90 мин']}
          defaultValue="60 мин"
          sectionId={ID_BOOKING}
        />
      </SettingRow>
      <SettingRow label="Окно записи вперёд" hint="За сколько клиент может бронировать слоты.">
        <div className="flex flex-wrap items-center gap-3">
          <Stepper defaultValue={14} unit="дней" sectionId={ID_BOOKING} />
          <span className="text-[12px] text-fg-muted">
            для абонементов · <b className="font-semibold text-fg">30 дней</b> для VIP
          </span>
        </div>
      </SettingRow>
      <SettingRow label="Закрытие записи" hint="За сколько до начала запись недоступна.">
        <Stepper defaultValue={60} unit="минут" sectionId={ID_BOOKING} />
      </SettingRow>
      <SettingRow label="Отмена и перенос">
        <div className="flex flex-col gap-3.5">
          <Toggle
            defaultChecked
            sectionId={ID_BOOKING}
            label="Бесплатная отмена за 6+ часов"
            sub="Позже — списание тренировки или штраф (см. ниже)."
          />
          <Toggle
            defaultChecked
            sectionId={ID_BOOKING}
            label="Перенос в пределах суток"
            sub="Можно перенести на другой слот в этот же день без штрафа."
          />
          <Toggle
            sectionId={ID_BOOKING}
            label="Штраф за неявку — 500 ₽"
            sub="Списывается с депозита, либо блокирует запись на 3 дня."
          />
        </div>
      </SettingRow>
      <SettingRow label="Групповые тренировки">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-4">
            <div>
              <div className="mb-1 text-[11.5px] text-fg-subtle">Лимит участников</div>
              <Stepper defaultValue={12} unit="чел." sectionId={ID_BOOKING} />
            </div>
            <div>
              <div className="mb-1 text-[11.5px] text-fg-subtle">Лист ожидания</div>
              <Stepper defaultValue={5} unit="чел." sectionId={ID_BOOKING} />
            </div>
          </div>
          <Toggle
            defaultChecked
            sectionId={ID_BOOKING}
            label="Авто-перенос из вейтлиста"
            sub="При отмене место получает первый из листа ожидания и push приходит сразу."
          />
        </div>
      </SettingRow>
      <SettingRow label="Персональные тренировки">
        <div className="flex flex-col gap-3.5">
          <Toggle
            defaultChecked
            sectionId={ID_BOOKING}
            label="Самозапись клиента к тренеру"
            sub="Без подтверждения тренера, если у клиента есть пакет ПТ."
          />
          <Toggle
            defaultChecked
            sectionId={ID_BOOKING}
            label="Показывать пустые окна тренеров"
            sub="Клиент видит и может бронировать слоты конкретного тренера."
          />
        </div>
      </SettingRow>
    </SectionCard>
  )
}

const ACQUIRERS: {
  logo: string
  bg: string
  name: string
  desc: string
  chip?: string
  action: string
}[] = [
  {
    logo: 'ЮК',
    bg: '#0095da',
    name: 'ЮKassa · Сбер',
    desc: 'Комиссия 2.5% · карты, СБП, Apple/Google Pay · выплата на р/с *4287 раз в неделю',
    chip: 'основной',
    action: 'Настроить',
  },
  {
    logo: 'Т',
    bg: '#005baa',
    name: 'Тинькофф Касса',
    desc: 'Комиссия 1.9% · СБП-pay по QR на ресепшн · резерв на случай аварии у ЮKassa',
    chip: 'резерв',
    action: 'Настроить',
  },
  {
    logo: 'СБП',
    bg: '#1a1a1a',
    name: 'СБП напрямую',
    desc: 'Без эквайринга · 0.4% · только для рассрочки и переводов > 50 000 ₽',
    action: 'Включить',
  },
]

export function PaymentsSection() {
  return (
    <SectionCard
      id={ID_PAYMENTS}
      icon={CreditCard}
      title="Платежи и касса"
      desc="Эквайринг, валюта и фискализация. Без активного эквайринга оплата абонементов недоступна."
      action={
        <span className="inline-flex h-[30px] items-center gap-1.5 rounded-full border-[0.5px] border-border bg-surface-2 px-3 text-[12px] font-semibold text-fg">
          <span className="size-1.5 rounded-full bg-primary" />
          Касса онлайн
        </span>
      }
    >
      <SettingRow first label="Валюта и НДС">
        <div className="grid gap-2 sm:grid-cols-2">
          <SelectField
            options={['₽ Российский рубль', '₸ Тенге', '€ Евро']}
            sectionId={ID_PAYMENTS}
          />
          <SelectField
            options={['Без НДС · УСН', 'НДС 20% включён', 'НДС 10%']}
            sectionId={ID_PAYMENTS}
          />
        </div>
      </SettingRow>
      <SettingRow label="Эквайринг" hint="Подключённые провайдеры. Первый — основной.">
        <div className="flex flex-col gap-2">
          {ACQUIRERS.map((a) => (
            <div
              key={a.name}
              className="flex flex-wrap items-center gap-3 rounded-xl border-[0.5px] border-border bg-surface-2 p-3"
            >
              <span
                className="grid size-11 shrink-0 place-items-center rounded-xl text-[12px] font-bold text-white"
                style={{ background: a.bg }}
              >
                {a.logo}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold">{a.name}</div>
                <div className="text-[11.5px] text-fg-subtle">{a.desc}</div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {a.chip ? (
                  <Chip tone={a.chip === 'основной' ? 'accent' : 'neutral'}>{a.chip}</Chip>
                ) : null}
                <GhostBtn>{a.action}</GhostBtn>
              </div>
            </div>
          ))}
          <GhostBtn>+ Добавить провайдера</GhostBtn>
        </div>
      </SettingRow>
      <SettingRow label="Фискализация" hint="Отправка чеков по 54-ФЗ.">
        <div className="flex flex-col gap-3.5">
          <Toggle
            defaultChecked
            sectionId={ID_PAYMENTS}
            label="Облачная касса «Атол Онлайн»"
            sub="Чек уходит в ФНС автоматически при оплате. Чек на email — включено."
          />
          <Toggle
            sectionId={ID_PAYMENTS}
            label="Печать чека на ресепшн"
            sub="Запасной режим. Включить, когда касса в зале активна."
          />
        </div>
      </SettingRow>
      <SettingRow label="Депозиты и возвраты">
        <div className="flex flex-col gap-3">
          <Toggle
            defaultChecked
            sectionId={ID_PAYMENTS}
            label="Депозит на счёт клиента"
            sub="Клиент может пополнить и оплачивать ПТ, бар и заморозку без карты."
          />
          <div className="flex flex-wrap items-center gap-2 text-[12px] text-fg-muted">
            Срок возврата абонемента —
            <Stepper defaultValue={14} unit="дней" sectionId={ID_PAYMENTS} />
            по 32-й ст. ЗоЗПП
          </div>
        </div>
      </SettingRow>
      <SettingRow label="Промокоды" hint="Принимаются в приложении и на сайте.">
        <div className="flex flex-wrap items-center gap-1.5">
          <Chip tone="accent">MAY15 · −15% · до 31.05</Chip>
          <Chip tone="accent">FRIEND · −2 000 ₽ · реферал</Chip>
          <Chip>SUMMER · −10% · черновик</Chip>
          <GhostBtn>+ Промокод</GhostBtn>
        </div>
      </SettingRow>
    </SectionCard>
  )
}
