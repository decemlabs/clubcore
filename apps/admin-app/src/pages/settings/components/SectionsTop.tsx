import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { cn } from '@/lib/cn'
import { Initials } from '@/components/ui/initials'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/EmptyState'
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
  X,
} from '@/components/icons'
import {
  Chip,
  GhostBtn,
  SectionCard,
  SelectField,
  SettingRow,
  Stepper,
  Toggle,
} from '@/components/settings/controls'
import { can } from '@/shared/session/can'
import { useSession } from '@/features/auth/api'
import {
  useSessions,
  useRevokeSession,
  useRevokeCurrentSession,
  useGymInfo,
  useUpdateGymInfo,
  useWorkingHours,
  useUpdateWorkingHours,
  useBookingConfig,
  useUpdateBookingConfig,
  ApiError,
} from '@/features/settings/api'
import {
  GymInfoUpdateSchema,
  WorkingHoursUpdateSchema,
  BookingConfigUpdateSchema,
  type GymInfoData,
  type BookingConfigData,
} from '@/features/settings/schemas'
import { useSettingsDirty } from '@/components/settings/context'
import { formatRelativeRu, getInitials } from '@/lib/format'

const ID_PROFILE = 'profile'
const ID_SECURITY = 'security'
const ID_BRANCH = 'branch'
const ID_HOURS = 'hours'
const ID_BOOKING = 'booking'
const ID_PAYMENTS = 'payments'

// ─── shared inline field class ───────────────────────────────────────────────

const FIELD =
  'h-[38px] w-full rounded-[10px] border-[0.5px] border-border-strong bg-surface-2 px-3 text-[13.5px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-fg-subtle focus:bg-surface'

const FIELD_TIME =
  'h-8 w-[72px] rounded-lg border-[0.5px] border-border-strong bg-surface-2 px-2 text-center text-[12.5px] tabular-nums outline-none focus:border-fg-subtle'

// ─── day names ────────────────────────────────────────────────────────────────

const DAY_NAMES = [
  'Понедельник',
  'Вторник',
  'Среда',
  'Четверг',
  'Пятница',
  'Суббота',
  'Воскресенье',
]

function ActionPill({ icon: Icon, children }: { icon?: typeof Check; children: React.ReactNode }) {
  return (
    <span className="inline-flex h-[30px] items-center gap-1.5 rounded-full border-[0.5px] border-border bg-surface-2 px-3 text-[12px] font-semibold text-fg">
      {Icon ? <Icon className="size-3.5" /> : null}
      {children}
    </span>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// ProfileSection (read-only, Phase 104)
// ─────────────────────────────────────────────────────────────────────────────

export function ProfileSection() {
  const { data, isPending, isError, refetch } = useSession()

  const ROLE_LABEL: Record<string, string> = {
    owner: 'Владелец',
    reception: 'Ресепшн',
  }

  return (
    <SectionCard
      id={ID_PROFILE}
      icon={Building2}
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

// ─────────────────────────────────────────────────────────────────────────────
// SecuritySection (wired Phase 104)
// ─────────────────────────────────────────────────────────────────────────────

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

// ─────────────────────────────────────────────────────────────────────────────
// BranchSection — CFG-01 (wired Phase 108-05)
// ─────────────────────────────────────────────────────────────────────────────

/** Controlled inline toggle (no internal state — caller owns). */
function InlineToggle({
  checked,
  onToggle,
  disabled,
}: {
  checked: boolean
  onToggle: () => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onToggle}
      className={cn(
        'relative h-5 w-9 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        checked ? 'bg-primary' : 'bg-surface-3',
        disabled ? 'cursor-not-allowed opacity-65' : 'cursor-pointer',
      )}
    >
      <span
        className={cn(
          'absolute top-0.5 size-4 rounded-full bg-white shadow-sm transition-[left]',
          checked ? 'left-[18px]' : 'left-0.5',
        )}
      />
    </button>
  )
}

/** Controlled inline stepper (no internal state — caller owns). */
function InlineStepper({
  value,
  unit,
  min = 0,
  max,
  onChange,
}: {
  value: number
  unit: string
  min?: number
  max?: number
  onChange: (v: number) => void
}) {
  const BTN =
    'grid h-[38px] w-9 place-items-center text-fg-muted transition-colors hover:bg-surface-3 hover:text-fg'
  return (
    <div className="inline-flex h-[38px] items-center rounded-[10px] border-[0.5px] border-border-strong bg-surface-2">
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - 1))}
        className={cn(BTN, 'rounded-l-[10px]')}
        aria-label="Меньше"
      >
        <span className="text-base leading-none">−</span>
      </button>
      <span className="grid w-12 place-items-center text-[13.5px] font-semibold tabular-nums">
        {value}
      </span>
      <button
        type="button"
        onClick={() => onChange(max != null ? Math.min(max, value + 1) : value + 1)}
        className={BTN}
        aria-label="Больше"
      >
        <span className="text-base leading-none">+</span>
      </button>
      <span className="px-3 text-[12.5px] text-fg-subtle">{unit}</span>
    </div>
  )
}

type BranchFormState = {
  nameShort: string
  name: string
  address: string
  latitude: string
  longitude: string
  phone: string
  email: string
  description: string
  capacity: number
  amenities: string[]
}

function gymDataToFormState(data: GymInfoData): BranchFormState {
  return {
    nameShort: data.name ?? '',
    name: data.name ?? '',
    address: data.address ?? '',
    latitude: data.latitude != null ? String(data.latitude) : '',
    longitude: data.longitude != null ? String(data.longitude) : '',
    phone: data.phone ?? '',
    email: data.email ?? '',
    description: '',
    capacity: 60,
    amenities: data.amenities ?? [],
  }
}

export function BranchSection({
  registerSave,
  registerCancel,
}: {
  registerSave?: (fn: () => Promise<void>) => void
  registerCancel?: (fn: () => void) => void
}) {
  const session = useSession()
  const role = session.data?.role ?? 'reception'
  const { markDirty } = useSettingsDirty()

  const gymQuery = useGymInfo(role)
  const updateGymInfo = useUpdateGymInfo()

  const [form, setForm] = useState<BranchFormState>({
    nameShort: '',
    name: '',
    address: '',
    latitude: '',
    longitude: '',
    phone: '',
    email: '',
    description: '',
    capacity: 60,
    amenities: [],
  })
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [showAmenityInput, setShowAmenityInput] = useState(false)
  const [amenityInput, setAmenityInput] = useState('')
  const serverDataRef = useRef<BranchFormState | null>(null)

  useEffect(() => {
    if (gymQuery.data) {
      const fs = gymDataToFormState(gymQuery.data)
      serverDataRef.current = fs
      setForm(fs)
    }
  }, [gymQuery.data])

  function patch(partial: Partial<BranchFormState>) {
    setForm((prev) => ({ ...prev, ...partial }))
    markDirty(ID_BRANCH)
  }

  async function handleSave() {
    const body = {
      nameShort: form.nameShort,
      name: form.name,
      address: form.address,
      latitude: form.latitude !== '' ? parseFloat(form.latitude) : null,
      longitude: form.longitude !== '' ? parseFloat(form.longitude) : null,
      phone: form.phone || null,
      email: form.email || null,
      description: form.description || null,
    }
    const result = GymInfoUpdateSchema.safeParse(body)
    if (!result.success) {
      const errs: Record<string, string> = {}
      for (const issue of result.error.issues) {
        const key = issue.path[0]
        if (key) errs[String(key)] = issue.message
      }
      setFieldErrors(errs)
      return
    }
    setFieldErrors({})
    return new Promise<void>((resolve, reject) => {
      updateGymInfo.mutate(result.data, {
        onSuccess: () => {
          serverDataRef.current = form
          resolve()
        },
        onError: (err) => {
          if (err instanceof ApiError && err.fields) {
            const errs: Record<string, string> = {}
            for (const [k, v] of Object.entries(err.fields)) {
              errs[k] = String(v)
            }
            setFieldErrors(errs)
          }
          reject(err)
        },
      })
    })
  }

  function handleCancel() {
    if (serverDataRef.current) {
      setForm(serverDataRef.current)
    }
    setFieldErrors({})
  }

  useEffect(() => {
    registerSave?.(handleSave)
    registerCancel?.(handleCancel)
  }, [form]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <SectionCard
      id={ID_BRANCH}
      icon={Building2}
      title="Филиал «Тверская»"
      desc="Карточка зала, которую видят клиенты в приложении и на сайте."
      action={<ActionPill icon={ChevronDown}>Тверская</ActionPill>}
    >
      {!can(role, 'edit', 'gym') ? (
        <EmptyState
          icon={Lock}
          title="Недостаточно прав"
          message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
          className="py-12"
        />
      ) : gymQuery.isPending ? (
        <div className="flex flex-col gap-3 pt-2">
          <Skeleton className="h-[38px] w-full rounded-[10px] bg-surface-3" />
          <Skeleton className="h-[38px] w-full rounded-[10px] bg-surface-3" />
          <Skeleton className="h-[38px] w-full rounded-[10px] bg-surface-3" />
          <Skeleton className="h-[38px] w-full rounded-[10px] bg-surface-3" />
        </div>
      ) : gymQuery.isError ? (
        <div className="py-4 text-[12px] text-fg-muted">
          Не удалось загрузить настройки.{' '}
          <button
            type="button"
            onClick={() => void gymQuery.refetch()}
            className="font-semibold text-fg hover:underline"
          >
            Повторить
          </button>
        </div>
      ) : (
        <>
          <SettingRow
            first
            label="Название"
            hint="Используется в чеках, рассылках и на странице зала."
          >
            <div className="grid gap-2 sm:grid-cols-[110px_minmax(0,1fr)]">
              <div>
                <input
                  value={form.nameShort}
                  onChange={(e) => patch({ nameShort: e.target.value })}
                  placeholder="Короткое"
                  className={FIELD}
                />
                {fieldErrors.nameShort ? (
                  <div className="mt-1 text-[11px] text-danger">
                    {fieldErrors.nameShort}
                  </div>
                ) : null}
              </div>
              <div>
                <input
                  value={form.name}
                  onChange={(e) => patch({ name: e.target.value })}
                  placeholder="Полное название"
                  className={FIELD}
                />
                {fieldErrors.name ? (
                  <div className="mt-1 text-[11px] text-danger">{fieldErrors.name}</div>
                ) : null}
              </div>
            </div>
          </SettingRow>
          <SettingRow label="Адрес и координаты">
            <div>
              <input
                value={form.address}
                onChange={(e) => patch({ address: e.target.value })}
                placeholder="Адрес"
                className={FIELD}
              />
              {fieldErrors.address ? (
                <div className="mt-1 text-[11px] text-danger">{fieldErrors.address}</div>
              ) : null}
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <div>
                <input
                  value={form.latitude}
                  onChange={(e) => patch({ latitude: e.target.value })}
                  inputMode="numeric"
                  placeholder="широта"
                  className={FIELD}
                />
                {fieldErrors.latitude ? (
                  <div className="mt-1 text-[11px] text-danger">Некорректные координаты</div>
                ) : null}
              </div>
              <div>
                <input
                  value={form.longitude}
                  onChange={(e) => patch({ longitude: e.target.value })}
                  inputMode="numeric"
                  placeholder="долгота"
                  className={FIELD}
                />
                {fieldErrors.longitude ? (
                  <div className="mt-1 text-[11px] text-danger">Некорректные координаты</div>
                ) : null}
              </div>
            </div>
          </SettingRow>
          <SettingRow label="Контакты для клиентов">
            <div className="grid gap-2 sm:grid-cols-2">
              <input
                value={form.phone}
                onChange={(e) => patch({ phone: e.target.value })}
                placeholder="+7 (000) 000-00-00"
                className={FIELD}
              />
              <input
                value={form.email}
                onChange={(e) => patch({ email: e.target.value })}
                type="email"
                placeholder="email@example.com"
                className={FIELD}
              />
            </div>
          </SettingRow>
          <SettingRow
            label="Описание"
            hint="Показывается при выборе филиала и при первом визите."
          >
            <div>
              <textarea
                value={form.description}
                onChange={(e) => patch({ description: e.target.value })}
                maxLength={500}
                className={cn(FIELD, 'min-h-[78px] resize-y py-2 leading-relaxed')}
              />
              <div className="mt-1 text-[11px] text-fg-subtle">
                {form.description.length} / 500 символов
              </div>
            </div>
          </SettingRow>
          <SettingRow
            label="Возможности зала"
            hint="Иконки показываются на карточке филиала."
          >
            <div className="flex flex-wrap items-center gap-1.5">
              {form.amenities.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => {
                    patch({ amenities: form.amenities.filter((a) => a !== c) })
                  }}
                  className="inline-flex h-6 items-center gap-1 rounded-full bg-primary-soft px-2.5 text-[11.5px] font-semibold text-primary-deep hover:bg-danger-soft hover:text-danger dark:text-primary"
                >
                  {c}
                  <X className="size-3" />
                </button>
              ))}
              {showAmenityInput ? (
                <input
                  autoFocus
                  value={amenityInput}
                  onChange={(e) => setAmenityInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      const val = amenityInput.trim()
                      if (val) {
                        patch({ amenities: [...form.amenities, val] })
                      }
                      setAmenityInput('')
                      setShowAmenityInput(false)
                    } else if (e.key === 'Escape') {
                      setAmenityInput('')
                      setShowAmenityInput(false)
                    }
                  }}
                  onBlur={() => {
                    const val = amenityInput.trim()
                    if (val) {
                      patch({ amenities: [...form.amenities, val] })
                    }
                    setAmenityInput('')
                    setShowAmenityInput(false)
                  }}
                  placeholder="Возможность…"
                  className="h-6 rounded-full border-[0.5px] border-border-strong bg-surface-2 px-2.5 text-[11.5px] outline-none focus:border-fg-subtle"
                />
              ) : (
                <GhostBtn onClick={() => setShowAmenityInput(true)}>+ Возможность</GhostBtn>
              )}
            </div>
          </SettingRow>
          <SettingRow
            label="Вместимость"
            hint="Используется для тепловой карты загруженности и предупреждений."
          >
            <InlineStepper
              value={form.capacity}
              unit="человек"
              min={1}
              onChange={(v) => patch({ capacity: v })}
            />
          </SettingRow>
        </>
      )}
    </SectionCard>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// HoursSection — CFG-02 (wired Phase 108-05)
// ─────────────────────────────────────────────────────────────────────────────

type ScheduleDay = {
  day: number
  open: string
  close: string
  closed?: boolean
}

type BreakItem = { label: string; start: string; end: string }
type ClosureItem = { date: string; label?: string }

const DEFAULT_SCHEDULE: ScheduleDay[] = Array.from({ length: 7 }, (_, i) => ({
  day: i,
  open: '07:00',
  close: '23:00',
  closed: false,
}))

export function HoursSection({
  registerSave,
  registerCancel,
}: {
  registerSave?: (fn: () => Promise<void>) => void
  registerCancel?: (fn: () => void) => void
}) {
  const session = useSession()
  const role = session.data?.role ?? 'reception'
  const { markDirty } = useSettingsDirty()

  const hoursQuery = useWorkingHours(role)
  const updateWorkingHours = useUpdateWorkingHours()

  const [schedule, setSchedule] = useState<ScheduleDay[]>(DEFAULT_SCHEDULE)
  const [breaks, setBreaks] = useState<BreakItem[]>([])
  const [closures, setClosures] = useState<ClosureItem[]>([])
  const [showBreakInput, setShowBreakInput] = useState(false)
  const [breakDraft, setBreakDraft] = useState({ label: '', start: '', end: '' })
  const [showClosureInput, setShowClosureInput] = useState(false)
  const [closureDraft, setClosureDraft] = useState({ date: '', label: '' })

  const serverScheduleRef = useRef(DEFAULT_SCHEDULE)
  const serverBreaksRef = useRef<BreakItem[]>([])
  const serverClosuresRef = useRef<ClosureItem[]>([])

  useEffect(() => {
    if (hoursQuery.data) {
      const sch =
        Array.isArray(hoursQuery.data.schedule) && hoursQuery.data.schedule.length > 0
          ? (hoursQuery.data.schedule as ScheduleDay[])
          : DEFAULT_SCHEDULE
      const brks = Array.isArray(hoursQuery.data.breaks)
        ? (hoursQuery.data.breaks as BreakItem[])
        : []
      const cls = Array.isArray(hoursQuery.data.closures)
        ? (hoursQuery.data.closures as ClosureItem[])
        : []
      serverScheduleRef.current = sch
      serverBreaksRef.current = brks
      serverClosuresRef.current = cls
      setSchedule(sch)
      setBreaks(brks)
      setClosures(cls)
    }
  }, [hoursQuery.data])

  function dirty() {
    markDirty(ID_HOURS)
  }

  async function handleSave() {
    const body = {
      schedule: schedule as Array<{ day: number; open: string; close: string; closed?: boolean }>,
      breaks: breaks as unknown[],
      closures: closures as unknown[],
    }
    const result = WorkingHoursUpdateSchema.safeParse(body)
    if (!result.success) {
      toast.error('Проверьте корректность времени в графике работы')
      throw new Error(result.error.message)
    }
    return new Promise<void>((resolve, reject) => {
      updateWorkingHours.mutate(result.data, {
        onSuccess: () => {
          serverScheduleRef.current = schedule
          serverBreaksRef.current = breaks
          serverClosuresRef.current = closures
          resolve()
        },
        onError: (err) => reject(err),
      })
    })
  }

  function handleCancel() {
    setSchedule(serverScheduleRef.current)
    setBreaks(serverBreaksRef.current)
    setClosures(serverClosuresRef.current)
  }

  useEffect(() => {
    registerSave?.(handleSave)
    registerCancel?.(handleCancel)
  }, [schedule, breaks, closures]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <SectionCard
      id={ID_HOURS}
      icon={Clock}
      title="График работы"
      desc="Часы открытия и плановые закрытия. Расписание тренировок ограничено этим окном."
      action={<ActionPill icon={Activity}>Копировать из «Парк»</ActionPill>}
    >
      {!can(role, 'edit', 'settings') ? (
        <EmptyState
          icon={Lock}
          title="Недостаточно прав"
          message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
          className="py-12"
        />
      ) : hoursQuery.isPending ? (
        <div className="flex flex-col gap-2 pt-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full rounded-lg bg-surface-3" />
          ))}
        </div>
      ) : hoursQuery.isError ? (
        <div className="py-4 text-[12px] text-fg-muted">
          Не удалось загрузить настройки.{' '}
          <button
            type="button"
            onClick={() => void hoursQuery.refetch()}
            className="font-semibold text-fg hover:underline"
          >
            Повторить
          </button>
        </div>
      ) : (
        <>
          <SettingRow first label="Режим работы зала">
            <div className="flex flex-col">
              {schedule.map((day, i) => {
                const isWeekend = day.day >= 5
                return (
                  <div
                    key={day.day}
                    className={cn(
                      'flex flex-wrap items-center gap-2 py-2 text-[12.5px]',
                      i > 0 && 'border-t-[0.5px] border-border',
                    )}
                  >
                    <span
                      className={cn(
                        'w-[120px] font-semibold',
                        isWeekend && 'text-primary-deep dark:text-primary',
                      )}
                    >
                      {DAY_NAMES[day.day] ?? `День ${day.day}`}
                    </span>
                    <input
                      type="time"
                      value={day.open}
                      disabled={day.closed}
                      onChange={(e) => {
                        setSchedule((prev) =>
                          prev.map((d) =>
                            d.day === day.day ? { ...d, open: e.target.value } : d,
                          ),
                        )
                        dirty()
                      }}
                      className={cn(FIELD_TIME, day.closed && 'opacity-50')}
                    />
                    <span className="text-fg-subtle">—</span>
                    <input
                      type="time"
                      value={day.close}
                      disabled={day.closed}
                      onChange={(e) => {
                        setSchedule((prev) =>
                          prev.map((d) =>
                            d.day === day.day ? { ...d, close: e.target.value } : d,
                          ),
                        )
                        dirty()
                      }}
                      className={cn(FIELD_TIME, day.closed && 'opacity-50')}
                    />
                    <button
                      type="button"
                      aria-label={day.closed ? 'Открыть день' : 'Закрыть день'}
                      title={day.closed ? 'Открыть день' : 'Закрыть день'}
                      onClick={() => {
                        setSchedule((prev) =>
                          prev.map((d) =>
                            d.day === day.day ? { ...d, closed: !d.closed } : d,
                          ),
                        )
                        dirty()
                      }}
                      className={cn(
                        'ml-auto grid size-7 place-items-center rounded-lg text-fg-subtle transition-colors',
                        day.closed
                          ? 'bg-danger-soft text-danger'
                          : 'hover:bg-danger-soft hover:text-danger',
                      )}
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                )
              })}
            </div>
          </SettingRow>
          <SettingRow
            label="Технические перерывы"
            hint="Зал закрыт, запись и приход недоступны."
          >
            <div className="flex flex-wrap items-center gap-1.5">
              {breaks.map((b, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setBreaks((prev) => prev.filter((_, i) => i !== idx))
                    dirty()
                  }}
                  className="inline-flex h-6 items-center gap-1 rounded-full bg-warning-soft px-2.5 text-[11.5px] font-semibold text-warning-deep hover:bg-danger-soft hover:text-danger"
                >
                  ⏸ {b.label} {b.start}–{b.end}
                  <X className="size-3" />
                </button>
              ))}
              {showBreakInput ? (
                <div className="flex items-center gap-1.5 rounded-lg border-[0.5px] border-border bg-surface-2 px-2 py-1">
                  <input
                    autoFocus
                    value={breakDraft.label}
                    onChange={(e) => setBreakDraft((d) => ({ ...d, label: e.target.value }))}
                    placeholder="Название"
                    className="w-24 bg-transparent text-[12px] outline-none"
                  />
                  <input
                    type="time"
                    value={breakDraft.start}
                    onChange={(e) => setBreakDraft((d) => ({ ...d, start: e.target.value }))}
                    className="w-20 bg-transparent text-[12px] outline-none"
                  />
                  <span className="text-fg-subtle">–</span>
                  <input
                    type="time"
                    value={breakDraft.end}
                    onChange={(e) => setBreakDraft((d) => ({ ...d, end: e.target.value }))}
                    className="w-20 bg-transparent text-[12px] outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (breakDraft.label && breakDraft.start && breakDraft.end) {
                        setBreaks((prev) => [...prev, { ...breakDraft }])
                        dirty()
                      }
                      setBreakDraft({ label: '', start: '', end: '' })
                      setShowBreakInput(false)
                    }}
                    className="text-[11px] font-semibold text-primary-deep dark:text-primary"
                  >
                    ОК
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setBreakDraft({ label: '', start: '', end: '' })
                      setShowBreakInput(false)
                    }}
                    className="text-[11px] font-semibold text-fg-muted"
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <GhostBtn onClick={() => setShowBreakInput(true)}>+ Перерыв</GhostBtn>
              )}
            </div>
          </SettingRow>
          <SettingRow
            label="Праздники и закрытия"
            hint="Видны клиентам в приложении и в чат-боте."
          >
            <div className="flex flex-wrap items-center gap-1.5">
              {closures.map((c, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setClosures((prev) => prev.filter((_, i) => i !== idx))
                    dirty()
                  }}
                  className="inline-flex h-6 items-center gap-1 rounded-full bg-surface-3 px-2.5 text-[11.5px] font-semibold text-fg-muted hover:bg-danger-soft hover:text-danger"
                >
                  {c.date}
                  {c.label ? ` · ${c.label}` : ''}
                  <X className="size-3" />
                </button>
              ))}
              {showClosureInput ? (
                <div className="flex items-center gap-1.5 rounded-lg border-[0.5px] border-border bg-surface-2 px-2 py-1">
                  <input
                    autoFocus
                    type="date"
                    value={closureDraft.date}
                    onChange={(e) => setClosureDraft((d) => ({ ...d, date: e.target.value }))}
                    className="bg-transparent text-[12px] outline-none"
                  />
                  <input
                    value={closureDraft.label}
                    onChange={(e) => setClosureDraft((d) => ({ ...d, label: e.target.value }))}
                    placeholder="Описание"
                    className="w-28 bg-transparent text-[12px] outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (closureDraft.date) {
                        setClosures((prev) => [
                          ...prev,
                          { date: closureDraft.date, label: closureDraft.label || undefined },
                        ])
                        dirty()
                      }
                      setClosureDraft({ date: '', label: '' })
                      setShowClosureInput(false)
                    }}
                    className="text-[11px] font-semibold text-primary-deep dark:text-primary"
                  >
                    ОК
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setClosureDraft({ date: '', label: '' })
                      setShowClosureInput(false)
                    }}
                    className="text-[11px] font-semibold text-fg-muted"
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <GhostBtn onClick={() => setShowClosureInput(true)}>+ Дата</GhostBtn>
              )}
            </div>
          </SettingRow>
        </>
      )}
    </SectionCard>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// BookingSection — CFG-03 (wired Phase 108-05)
// ─────────────────────────────────────────────────────────────────────────────

const STEP_OPTIONS: Array<{ label: string; value: 15 | 30 | 60 | 90 }> = [
  { label: '15 мин', value: 15 },
  { label: '30 мин', value: 30 },
  { label: '60 мин', value: 60 },
  { label: '90 мин', value: 90 },
]

type BookingFormState = {
  scheduleStepMinutes: 15 | 30 | 60 | 90
  bookingAheadDays: number
  cutoffMinutes: number
  cancelWindowHours: number
  cancelWindowEnabled: boolean
  rescheduleSameDay: boolean
  noShowPenaltyRubles: number // display in rubles; submit ×100
  noShowPenaltyEnabled: boolean
  groupLimit: number
  waitlistLimit: number
  waitlistAutoTransfer: boolean
  clientSelfBook: boolean
  showTrainerWindows: boolean
}

function bookingDataToFormState(d: BookingConfigData): BookingFormState {
  return {
    scheduleStepMinutes: (d.scheduleStepMinutes as 15 | 30 | 60 | 90) ?? 60,
    bookingAheadDays: d.bookingAheadDays,
    cutoffMinutes: d.cutoffMinutes,
    cancelWindowHours: d.cancelWindowHours,
    cancelWindowEnabled: d.cancelWindowEnabled,
    rescheduleSameDay: d.rescheduleSameDay,
    noShowPenaltyRubles: Math.round(d.noShowPenaltyKopecks / 100),
    noShowPenaltyEnabled: d.noShowPenaltyEnabled,
    groupLimit: d.groupLimit,
    waitlistLimit: d.waitlistLimit,
    waitlistAutoTransfer: d.waitlistAutoTransfer,
    clientSelfBook: d.clientSelfBook,
    showTrainerWindows: d.showTrainerWindows,
  }
}

export function BookingSection({
  registerSave,
  registerCancel,
}: {
  registerSave?: (fn: () => Promise<void>) => void
  registerCancel?: (fn: () => void) => void
}) {
  const session = useSession()
  const role = session.data?.role ?? 'reception'
  const { markDirty } = useSettingsDirty()

  const bookingQuery = useBookingConfig(role)
  const updateBookingConfig = useUpdateBookingConfig()

  const [form, setForm] = useState<BookingFormState>({
    scheduleStepMinutes: 60,
    bookingAheadDays: 14,
    cutoffMinutes: 60,
    cancelWindowHours: 6,
    cancelWindowEnabled: true,
    rescheduleSameDay: true,
    noShowPenaltyRubles: 0,
    noShowPenaltyEnabled: false,
    groupLimit: 12,
    waitlistLimit: 5,
    waitlistAutoTransfer: true,
    clientSelfBook: true,
    showTrainerWindows: true,
  })
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const serverDataRef = useRef<BookingFormState | null>(null)

  useEffect(() => {
    if (bookingQuery.data) {
      const fs = bookingDataToFormState(bookingQuery.data)
      serverDataRef.current = fs
      setForm(fs)
    }
  }, [bookingQuery.data])

  function patch(partial: Partial<BookingFormState>) {
    setForm((prev) => ({ ...prev, ...partial }))
    markDirty(ID_BOOKING)
  }

  async function handleSave() {
    const body = {
      scheduleStepMinutes: form.scheduleStepMinutes,
      bookingAheadDays: form.bookingAheadDays,
      cutoffMinutes: form.cutoffMinutes,
      cancelWindowHours: form.cancelWindowHours,
      cancelWindowEnabled: form.cancelWindowEnabled,
      rescheduleSameDay: form.rescheduleSameDay,
      noShowPenaltyKopecks: form.noShowPenaltyRubles * 100, // ÷100 display, ×100 submit
      noShowPenaltyEnabled: form.noShowPenaltyEnabled,
      groupLimit: form.groupLimit,
      waitlistLimit: form.waitlistLimit,
      waitlistAutoTransfer: form.waitlistAutoTransfer,
      clientSelfBook: form.clientSelfBook,
      showTrainerWindows: form.showTrainerWindows,
    }
    const result = BookingConfigUpdateSchema.safeParse(body)
    if (!result.success) {
      const errs: Record<string, string> = {}
      for (const issue of result.error.issues) {
        const key = issue.path[0]
        if (key) errs[String(key)] = issue.message
      }
      setFieldErrors(errs)
      throw new Error(result.error.message)
    }
    setFieldErrors({})
    return new Promise<void>((resolve, reject) => {
      updateBookingConfig.mutate(result.data, {
        onSuccess: () => {
          serverDataRef.current = form
          resolve()
        },
        onError: (err) => {
          if (err instanceof ApiError && err.fields) {
            const errs: Record<string, string> = {}
            for (const [k, v] of Object.entries(err.fields)) {
              errs[k] = String(v)
            }
            setFieldErrors(errs)
          }
          reject(err)
        },
      })
    })
  }

  function handleCancel() {
    if (serverDataRef.current) {
      setForm(serverDataRef.current)
    }
    setFieldErrors({})
  }

  useEffect(() => {
    registerSave?.(handleSave)
    registerCancel?.(handleCancel)
  }, [form]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <SectionCard
      id={ID_BOOKING}
      icon={Calendar}
      title="Запись и слоты"
      desc="Правила онлайн-записи и групповых тренировок. Влияет на приложение клиента и бота в Telegram."
    >
      {!can(role, 'edit', 'settings') ? (
        <EmptyState
          icon={Lock}
          title="Недостаточно прав"
          message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
          className="py-12"
        />
      ) : bookingQuery.isPending ? (
        <div className="flex flex-col gap-3 pt-2">
          <Skeleton className="h-[38px] w-full rounded-[10px] bg-surface-3" />
          <Skeleton className="h-[38px] w-full rounded-[10px] bg-surface-3" />
          <Skeleton className="h-[38px] w-full rounded-[10px] bg-surface-3" />
          <Skeleton className="h-[38px] w-full rounded-[10px] bg-surface-3" />
        </div>
      ) : bookingQuery.isError ? (
        <div className="py-4 text-[12px] text-fg-muted">
          Не удалось загрузить настройки.{' '}
          <button
            type="button"
            onClick={() => void bookingQuery.refetch()}
            className="font-semibold text-fg hover:underline"
          >
            Повторить
          </button>
        </div>
      ) : (
        <>
          <SettingRow
            first
            label="Шаг расписания"
            hint="Минимальная длительность слота тренировки."
          >
            <div className="inline-flex flex-wrap gap-0.5 rounded-full border-[0.5px] border-border bg-surface-2 p-[3px]">
              {STEP_OPTIONS.map((opt) => {
                const active = form.scheduleStepMinutes === opt.value
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => patch({ scheduleStepMinutes: opt.value })}
                    className={cn(
                      'h-[28px] rounded-full px-3 text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      active
                        ? 'bg-fg text-bg dark:bg-primary dark:text-[#06120c]'
                        : 'text-fg-muted hover:text-fg',
                    )}
                  >
                    {opt.label}
                  </button>
                )
              })}
            </div>
          </SettingRow>
          <SettingRow
            label="Окно записи вперёд"
            hint="За сколько клиент может бронировать слоты."
          >
            <InlineStepper
              value={form.bookingAheadDays}
              unit="дней"
              min={1}
              max={365}
              onChange={(v) => patch({ bookingAheadDays: v })}
            />
            {fieldErrors.bookingAheadDays ? (
              <div className="mt-1 text-[11px] text-danger">{fieldErrors.bookingAheadDays}</div>
            ) : null}
          </SettingRow>
          <SettingRow label="Закрытие записи" hint="За сколько до начала запись недоступна.">
            <InlineStepper
              value={form.cutoffMinutes}
              unit="минут"
              min={0}
              max={1440}
              onChange={(v) => patch({ cutoffMinutes: v })}
            />
          </SettingRow>
          <SettingRow label="Отмена и перенос">
            <div className="flex flex-col gap-3.5">
              {/* Cancel window */}
              <div className="flex items-start gap-3">
                <InlineToggle
                  checked={form.cancelWindowEnabled}
                  onToggle={() => patch({ cancelWindowEnabled: !form.cancelWindowEnabled })}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 text-[13px] font-semibold">
                    Бесплатная отмена
                    {form.cancelWindowEnabled ? (
                      <InlineStepper
                        value={form.cancelWindowHours}
                        unit="ч."
                        min={1}
                        onChange={(v) => patch({ cancelWindowHours: v })}
                      />
                    ) : null}
                  </div>
                  <div className="mt-0.5 text-[11.5px] leading-relaxed text-fg-subtle">
                    Позже — списание тренировки или штраф (см. ниже).
                  </div>
                </div>
              </div>
              {/* Reschedule same day */}
              <div className="flex items-start gap-3">
                <InlineToggle
                  checked={form.rescheduleSameDay}
                  onToggle={() => patch({ rescheduleSameDay: !form.rescheduleSameDay })}
                />
                <div className="min-w-0">
                  <div className="text-[13px] font-semibold">Перенос в пределах суток</div>
                  <div className="mt-0.5 text-[11.5px] leading-relaxed text-fg-subtle">
                    Можно перенести на другой слот в этот же день без штрафа.
                  </div>
                </div>
              </div>
              {/* No-show penalty */}
              <div>
                <div className="flex items-start gap-3">
                  <InlineToggle
                    checked={form.noShowPenaltyEnabled}
                    onToggle={() => patch({ noShowPenaltyEnabled: !form.noShowPenaltyEnabled })}
                  />
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold">Штраф за неявку</div>
                    <div className="mt-0.5 text-[11.5px] leading-relaxed text-fg-subtle">
                      Списывается с депозита, либо блокирует запись на 3 дня.
                    </div>
                  </div>
                </div>
                {form.noShowPenaltyEnabled ? (
                  <div className="mt-2 pl-12">
                    <div className="relative inline-block">
                      <input
                        type="text"
                        inputMode="numeric"
                        value={form.noShowPenaltyRubles}
                        onChange={(e) => {
                          const val = parseInt(e.target.value, 10)
                          if (!isNaN(val) && val >= 0) {
                            patch({ noShowPenaltyRubles: val })
                          }
                        }}
                        className={cn(FIELD, 'w-36 pr-9 tabular-nums')}
                      />
                      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[13px] font-medium text-fg-subtle">
                        ₽
                      </span>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </SettingRow>
          <SettingRow label="Групповые тренировки">
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap gap-4">
                <div>
                  <div className="mb-1 text-[11.5px] text-fg-subtle">Лимит участников</div>
                  <InlineStepper
                    value={form.groupLimit}
                    unit="чел."
                    min={1}
                    onChange={(v) => patch({ groupLimit: v })}
                  />
                </div>
                <div>
                  <div className="mb-1 text-[11.5px] text-fg-subtle">Лист ожидания</div>
                  <InlineStepper
                    value={form.waitlistLimit}
                    unit="чел."
                    min={0}
                    onChange={(v) => patch({ waitlistLimit: v })}
                  />
                </div>
              </div>
              <div className="flex items-start gap-3">
                <InlineToggle
                  checked={form.waitlistAutoTransfer}
                  onToggle={() => patch({ waitlistAutoTransfer: !form.waitlistAutoTransfer })}
                />
                <div className="min-w-0">
                  <div className="text-[13px] font-semibold">Авто-перенос из вейтлиста</div>
                  <div className="mt-0.5 text-[11.5px] leading-relaxed text-fg-subtle">
                    При отмене место получает первый из листа ожидания и push приходит сразу.
                  </div>
                </div>
              </div>
            </div>
          </SettingRow>
          <SettingRow label="Персональные тренировки">
            <div className="flex flex-col gap-3.5">
              <div className="flex items-start gap-3">
                <InlineToggle
                  checked={form.clientSelfBook}
                  onToggle={() => patch({ clientSelfBook: !form.clientSelfBook })}
                />
                <div className="min-w-0">
                  <div className="text-[13px] font-semibold">Самозапись клиента к тренеру</div>
                  <div className="mt-0.5 text-[11.5px] leading-relaxed text-fg-subtle">
                    Без подтверждения тренера, если у клиента есть пакет ПТ.
                  </div>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <InlineToggle
                  checked={form.showTrainerWindows}
                  onToggle={() => patch({ showTrainerWindows: !form.showTrainerWindows })}
                />
                <div className="min-w-0">
                  <div className="text-[13px] font-semibold">Показывать пустые окна тренеров</div>
                  <div className="mt-0.5 text-[11.5px] leading-relaxed text-fg-subtle">
                    Клиент видит и может бронировать слоты конкретного тренера.
                  </div>
                </div>
              </div>
            </div>
          </SettingRow>
        </>
      )}
    </SectionCard>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// PaymentsSection — mock (not in scope for Phase 108)
// ─────────────────────────────────────────────────────────────────────────────

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
