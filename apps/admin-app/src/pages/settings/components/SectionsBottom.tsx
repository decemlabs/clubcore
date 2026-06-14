import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/feedback/EmptyState';
import { useModals } from '@/components/modals/modals-context';
import { AdaptiveModal } from '@/components/modals/AdaptiveModal';
import { IconChip, ModalButton } from '@/components/modals/fields';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Bell,
  Check,
  CheckCircle2,
  Code,
  Download,
  Gift,
  Lock,
  Mail,
  MessageSquare,
  MoreHorizontal,
  Send,
  Smartphone,
  TriangleAlert,
  UserPlus,
  Users,
} from '@/components/icons';
import type { SettingsData } from '@/features/settings/types';
import { useSession } from '@/features/auth/api';
import {
  useUsers,
  useInviteUser,
  useDeactivateUser,
  useReactivateUser,
  useDeleteUser,
  useRevokeInvitation,
  ApiError,
} from '@/features/users/api';
import {
  useNotificationPrefs,
  useUpdateNotificationPrefs,
} from '@/features/settings/api';
import type { UserData } from '@/features/users/schemas';
import { can } from '@/shared/session/can';
import { formatDateRu, getInitials } from '@/lib/format';
import {
  NotificationPrefsUpdateSchema,
} from '@/features/settings/schemas';
import { useSettingsDirty } from '@/components/settings/context';
import {
  Chip,
  GhostBtn,
  PrimaryBtn,
  RadioGroup,
  SectionCard,
  SettingRow,
  Toggle,
} from '@/components/settings/controls';

const ID_NOTIF = 'notifications';
const ID_APP = 'app';
const ID_TEAM = 'team';

// Real user roles from /api/v1/users
const ROLE_TONE: Record<'owner' | 'reception', string> = {
  owner: 'bg-primary-soft text-primary-deep dark:text-primary',
  reception: 'bg-surface-3 text-fg-muted',
};
const ROLE_LABEL: Record<'owner' | 'reception', string> = {
  owner: 'Владелец',
  reception: 'Ресепшн',
};

const MATRIX_COLS = 'grid grid-cols-[minmax(0,1fr)_56px_56px_56px_56px] items-center gap-2';

type TriggerDef = {
  kind: string;
  label: string;
  sub: string;
  alwaysOn?: boolean;
};

// Notification triggers always displayed (fallback when backend matrix is empty).
// _ALWAYS_ON_KINDS per Phase 108-03: payment_succeeded, autopay_charge_failed.
const DEFAULT_TRIGGERS: TriggerDef[] = [
  { kind: 'booking_confirmed', label: 'Подтверждение записи', sub: 'В течение минуты после брони слота.' },
  { kind: 'booking_reminder', label: 'Напоминание за 2 часа', sub: 'Перед началом ПТ или групповой.' },
  { kind: 'waitlist_promoted', label: 'Слот занят — лист ожидания', sub: 'Клиенту в вейтлисте дали место.' },
  { kind: 'membership_expiring', label: 'Абонемент истекает', sub: 'За 7, 3 и 1 день до конца.' },
  { kind: 'payment_succeeded', label: 'Чек об оплате', sub: '54-ФЗ. Отключить нельзя.', alwaysOn: true },
  { kind: 'autopay_charge_failed', label: 'Ошибка автооплаты', sub: 'Клиент должен знать об отклонении платежа.', alwaysOn: true },
  { kind: 'booking_survey', label: 'Опрос «Как тренировка?»', sub: 'Через 30 мин после посещения.' },
  { kind: 'marketing', label: 'Маркетинг и акции', sub: 'Не чаще 1 раза в неделю; «тихие часы» применяются.' },
];

type Channel = 'push' | 'email' | 'sms' | 'tg';
type TriggerRow = { kind: string; push: boolean; email: boolean; sms: boolean; tg: boolean };

function buildMatrixState(matrix: Record<string, unknown>): TriggerRow[] {
  return DEFAULT_TRIGGERS.map(({ kind }) => {
    const entry = (matrix[kind] ?? {}) as Record<string, boolean>;
    return {
      kind,
      push: entry.push ?? true,
      email: entry.email ?? false,
      sms: entry.sms ?? false,
      tg: entry.tg ?? false,
    };
  });
}

function matrixStateToRecord(rows: TriggerRow[]): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const row of rows) {
    result[row.kind] = { push: row.push, email: row.email, sms: row.sms, tg: row.tg };
  }
  return result;
}

// ---------------------------------------------------------------------------
// NotificationsSection — CFG-04 (wired Phase 108-05)
// ---------------------------------------------------------------------------

export function NotificationsSection({
  registerSave,
  registerCancel,
}: {
  registerSave?: (fn: () => Promise<void>) => void;
  registerCancel?: (fn: () => void) => void;
}) {
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  const { markDirty } = useSettingsDirty();

  const notifsQuery = useNotificationPrefs(role);
  const updateNotifs = useUpdateNotificationPrefs();

  const [matrixRows, setMatrixRows] = useState<TriggerRow[]>(() =>
    DEFAULT_TRIGGERS.map(({ kind }) => ({ kind, push: true, email: false, sms: false, tg: false })),
  );
  const [senderSignature, setSenderSignature] = useState('');
  const [signatureError, setSignatureError] = useState('');
  const [quietStart, setQuietStart] = useState('22:00');
  const [quietEnd, setQuietEnd] = useState('10:00');

  const serverStateRef = useRef<{
    matrixRows: TriggerRow[];
    senderSignature: string;
    quietStart: string;
    quietEnd: string;
  } | null>(null);

  useEffect(() => {
    if (notifsQuery.data) {
      const rows = buildMatrixState(notifsQuery.data.matrix as Record<string, unknown>);
      const sig = notifsQuery.data.senderSignature ?? '';
      const qs = notifsQuery.data.quietHoursStart ?? '22:00';
      const qe = notifsQuery.data.quietHoursEnd ?? '10:00';
      serverStateRef.current = { matrixRows: rows, senderSignature: sig, quietStart: qs, quietEnd: qe };
      setMatrixRows(rows);
      setSenderSignature(sig);
      setQuietStart(qs);
      setQuietEnd(qe);
    }
  }, [notifsQuery.data]);

  function dirty() {
    markDirty(ID_NOTIF);
  }

  function toggleCell(kind: string, channel: Channel) {
    setMatrixRows((prev) =>
      prev.map((row) =>
        row.kind === kind ? { ...row, [channel]: !row[channel] } : row,
      ),
    );
    dirty();
  }

  async function handleSave() {
    const body = {
      matrix: matrixStateToRecord(matrixRows),
      senderSignature: senderSignature || null,
      quietHoursStart: quietStart || null,
      quietHoursEnd: quietEnd || null,
    };
    const result = NotificationPrefsUpdateSchema.safeParse(body);
    if (!result.success) {
      const firstIssue = result.error.issues[0];
      const field = firstIssue?.path[0];
      if (field === 'senderSignature') {
        setSignatureError(firstIssue?.message ?? 'Ошибка')
      }
      throw new Error(result.error.message);
    }
    setSignatureError('');
    return new Promise<void>((resolve, reject) => {
      updateNotifs.mutate(result.data, {
        onSuccess: () => {
          if (serverStateRef.current) {
            serverStateRef.current = { matrixRows, senderSignature, quietStart, quietEnd };
          }
          resolve();
        },
        onError: (err) => reject(err),
      });
    });
  }

  function handleCancel() {
    if (serverStateRef.current) {
      setMatrixRows(serverStateRef.current.matrixRows);
      setSenderSignature(serverStateRef.current.senderSignature);
      setQuietStart(serverStateRef.current.quietStart);
      setQuietEnd(serverStateRef.current.quietEnd);
    }
    setSignatureError('');
  }

  useEffect(() => {
    registerSave?.(handleSave);
    registerCancel?.(handleCancel);
  }, [matrixRows, senderSignature, quietStart, quietEnd]); // eslint-disable-line react-hooks/exhaustive-deps

  const headers = [
    { label: 'Push', Icon: Bell },
    { label: 'Email', Icon: Mail },
    { label: 'SMS', Icon: MessageSquare },
    { label: 'TG-бот', Icon: Send },
  ] as const;

  const enabledCount = matrixRows.reduce(
    (n, row) =>
      n +
      (row.push ? 1 : 0) +
      (row.email ? 1 : 0) +
      (row.sms ? 1 : 0) +
      (row.tg ? 1 : 0),
    0,
  );

  const FIELD_TIME =
    'h-8 w-[72px] rounded-lg border-[0.5px] border-border-strong bg-surface-2 px-2 text-center text-[12.5px] tabular-nums outline-none focus:border-fg-subtle';

  return (
    <SectionCard
      id={ID_NOTIF}
      icon={Bell}
      title="Уведомления клиенту"
      desc="Какие триггеры по каким каналам уходят. По умолчанию — push; SMS зарезервированы для важного."
      action={
        <span className="inline-flex h-[30px] items-center gap-1.5 rounded-full border-[0.5px] border-border bg-surface-2 px-3 text-[12px] font-semibold text-fg">
          <Check className="size-3.5" />
          {enabledCount} включены
        </span>
      }
    >
      {!can(role, 'edit', 'settings') ? (
        <EmptyState
          icon={Lock}
          title="Недостаточно прав"
          message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
          className="py-12"
        />
      ) : notifsQuery.isPending ? (
        <div className="flex flex-col gap-2 pt-2">
          <Skeleton className="h-[38px] w-full rounded-lg bg-surface-3" />
          <Skeleton className="h-[38px] w-full rounded-lg bg-surface-3" />
          <Skeleton className="h-[38px] w-full rounded-lg bg-surface-3" />
          <Skeleton className="h-[38px] w-full rounded-lg bg-surface-3" />
        </div>
      ) : notifsQuery.isError ? (
        <div className="py-4 text-[12px] text-fg-muted">
          Не удалось загрузить настройки.{' '}
          <button
            type="button"
            onClick={() => void notifsQuery.refetch()}
            className="font-semibold text-fg hover:underline"
          >
            Повторить
          </button>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto pt-2 [scrollbar-width:thin]">
            <div className="min-w-[540px]">
              <div className={cn(MATRIX_COLS, 'border-b-[0.5px] border-border pb-2')}>
                <span />
                {headers.map(({ label, Icon }) => (
                  <span
                    key={label}
                    className="flex flex-col items-center gap-0.5 text-[10.5px] font-semibold text-fg-muted"
                  >
                    <Icon className="size-3.5" />
                    {label}
                  </span>
                ))}
              </div>
              {DEFAULT_TRIGGERS.map((trigger, i) => {
                const row = matrixRows.find((r) => r.kind === trigger.kind) ?? {
                  kind: trigger.kind,
                  push: true,
                  email: false,
                  sms: false,
                  tg: false,
                };
                const isAlwaysOn = trigger.alwaysOn === true;
                const channels: Channel[] = ['push', 'email', 'sms', 'tg'];
                return (
                  <div
                    key={trigger.kind}
                    className={cn(
                      MATRIX_COLS,
                      i > 0 && 'border-t-[0.5px] border-border',
                      'py-2.5',
                    )}
                  >
                    <div className="min-w-0">
                      <div className="text-[13px] font-semibold">{trigger.label}</div>
                      <div className="text-[11px] text-fg-subtle">{trigger.sub}</div>
                      {isAlwaysOn ? (
                        <div className="text-[10.5px] text-fg-subtle">
                          Нельзя отключить (всегда включено)
                        </div>
                      ) : null}
                    </div>
                    {channels.map((ch) => (
                      <div key={ch} className="flex justify-center">
                        <button
                          type="button"
                          role="switch"
                          aria-checked={row[ch]}
                          disabled={isAlwaysOn}
                          onClick={() => {
                            if (!isAlwaysOn) toggleCell(trigger.kind, ch);
                          }}
                          className={cn(
                            'relative h-5 w-9 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                            row[ch] ? 'bg-primary' : 'bg-surface-3',
                            isAlwaysOn ? 'cursor-not-allowed opacity-65' : 'cursor-pointer',
                          )}
                          title={
                            isAlwaysOn
                              ? 'Нельзя отключить — системное уведомление'
                              : row[ch]
                                ? 'Выключить'
                                : 'Включить'
                          }
                        >
                          <span
                            className={cn(
                              'absolute top-0.5 size-4 rounded-full bg-white shadow-sm transition-[left]',
                              row[ch] ? 'left-[18px]' : 'left-0.5',
                            )}
                          />
                        </button>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>
          <SettingRow label="Подпись отправителя" hint="Виден в SMS и push.">
            <div>
              <input
                type="text"
                value={senderSignature}
                onChange={(e) => {
                  const val = e.target.value.toUpperCase().slice(0, 11);
                  setSenderSignature(val);
                  setSignatureError('');
                  dirty();
                }}
                placeholder="MOY ZAL"
                maxLength={11}
                className="h-[38px] w-full rounded-[10px] border-[0.5px] border-border-strong bg-surface-2 px-3 text-[13.5px] font-mono uppercase text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-fg-subtle focus:bg-surface sm:w-48"
              />
              {signatureError ? (
                <div className="mt-1 text-[11px] text-danger">{signatureError}</div>
              ) : (
                <div className="mt-1 text-[11px] text-fg-subtle">
                  до 11 латинских заглавных символов · зарегистрирован у операторов
                </div>
              )}
            </div>
          </SettingRow>
          <SettingRow
            label="Тихие часы"
            hint="В это время push не отправляются, кроме срочных. Часовой пояс — Europe/Moscow."
          >
            <div className="flex flex-wrap items-center gap-2 text-[12px] text-fg-muted">
              <input
                type="time"
                value={quietStart}
                onChange={(e) => {
                  setQuietStart(e.target.value);
                  dirty();
                }}
                className={FIELD_TIME}
              />
              —
              <input
                type="time"
                value={quietEnd}
                onChange={(e) => {
                  setQuietEnd(e.target.value);
                  dirty();
                }}
                className={FIELD_TIME}
              />
              по часовому поясу Europe/Moscow
            </div>
          </SettingRow>
        </>
      )}
    </SectionCard>
  );
}

export function AppSection({ data }: { data: SettingsData }) {
  return (
    <SectionCard
      id={ID_APP}
      icon={Smartphone}
      title="Приложение клиента"
      desc="Бренд, тема и фичи мобильного приложения «Мой зал». Изменения видны клиентам в течение 5 минут."
      action={
        <span className="inline-flex h-[30px] items-center rounded-full border-[0.5px] border-border bg-surface-2 px-3 text-[12px] font-semibold text-fg">
          v 4.12.3 · обновлено вчера
        </span>
      }
    >
      <SettingRow first label="Превью" hint="Так выглядит главный экран приложения сейчас.">
        <div className="flex flex-wrap items-start gap-5">
          <div className="w-[150px] shrink-0 rounded-[22px] border-[6px] border-fg/90 bg-bg p-3 dark:border-surface-3">
            <span className="mx-auto mb-2 block h-1 w-8 rounded-full bg-fg/20" />
            <span className="grid size-7 place-items-center rounded-lg bg-primary text-[13px] font-bold text-[#06120c]">
              М
            </span>
            <div className="mt-2 text-[13px] font-bold">Привет, Алёна 👋</div>
            <div className="text-[10px] text-fg-subtle">Тверская · до зала 12 мин</div>
            <div className="mt-2 rounded-xl bg-fg p-2.5 text-bg">
              <div className="text-[10px] font-semibold">QR · вход в зал</div>
              <div className="mt-1 text-[9px] opacity-70">A-31 · до 18.09</div>
              <div className="text-[9px] opacity-70">31 визит · 7 ПТ осталось</div>
            </div>
            <div className="mt-2 rounded-lg bg-primary py-1.5 text-center text-[10px] font-bold text-[#06120c]">
              Записаться
            </div>
          </div>
          <div className="min-w-0 flex-1 text-[12px] text-fg-muted">
            <div className="font-semibold text-fg">Что меняется при правках:</div>
            <ul className="mt-1.5 flex flex-col gap-1">
              {[
                'Логотип и заглавный значок (192×192, 512×512)',
                'Акцентный цвет — кнопки, плашки, активные элементы',
                'Шрифт и обращение к клиенту («Вы» / «ты»)',
                'Сплеш-экран и push-иконка',
              ].map((t) => (
                <li key={t} className="flex gap-2">
                  <span className="mt-1.5 size-1 shrink-0 rounded-full bg-fg-subtle" />
                  {t}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </SettingRow>
      <SettingRow label="Акцентный цвет">
        <div className="flex flex-wrap items-center gap-2">
          {data.swatches.map((s) => (
            <button
              key={s.color}
              type="button"
              title={s.title}
              className={cn(
                'size-8 rounded-full ring-offset-2 ring-offset-surface transition-transform hover:scale-110',
                s.active && 'ring-2 ring-fg',
              )}
              style={{ background: s.color }}
            />
          ))}
          <button
            type="button"
            className="grid size-8 place-items-center rounded-full border-[1.5px] border-dashed border-border-strong text-fg-subtle"
          >
            +
          </button>
        </div>
        <div className="mt-2 text-[11px] text-fg-subtle">
          текущий: <span className="font-mono">#2DD4A4</span> · контраст AAA на белом фоне
        </div>
      </SettingRow>
      <SettingRow label="Обращение к клиенту" hint="В пушах, чате и письмах.">
        <RadioGroup
          options={['На «ты», по имени', 'На «вы», по имени', 'По имени-отчеству']}
          defaultValue="На «ты», по имени"
          sectionId={ID_APP}
        />
        <div className="mt-2 text-[11px] text-fg-subtle">
          пример: «Алёна, через час йога — не забудь воду 💧»
        </div>
      </SettingRow>
      <SettingRow label="Включённые модули" hint="Если выключить — раздел не виден клиентам.">
        <div className="grid gap-3.5 sm:grid-cols-2">
          <Toggle
            defaultChecked
            sectionId={ID_APP}
            label="QR-вход"
            sub="по карточке клиента на турникет"
          />
          <Toggle
            defaultChecked
            sectionId={ID_APP}
            label="Запись на групповые"
            sub="с листом ожидания"
          />
          <Toggle
            defaultChecked
            sectionId={ID_APP}
            label="Чат с залом"
            sub="админ + дежурный тренер"
          />
          <Toggle
            defaultChecked
            sectionId={ID_APP}
            label="История тренировок"
            sub="прогресс, веса, серии"
          />
          <Toggle sectionId={ID_APP} label="Дневник питания" sub="бета · только для VIP" />
          <Toggle
            defaultChecked
            sectionId={ID_APP}
            label="Реферальная программа"
            sub="−2 000 ₽ другу и тебе"
          />
        </div>
      </SettingRow>
      <SettingRow label="Контент и партнёры" hint="Дополнительные блоки на главном экране.">
        <div className="flex flex-wrap items-center gap-1.5">
          <Chip tone="accent">Smoothie Bar · −20% после ПТ</Chip>
          <Chip tone="accent">Decathlon · промокод</Chip>
          <Chip>Доставка спортпита</Chip>
          <GhostBtn>+ Блок</GhostBtn>
        </div>
      </SettingRow>
    </SectionCard>
  );
}

const TEAM_COLS =
  'grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 md:grid-cols-[minmax(0,1.6fr)_88px_auto_36px]';

// ---------------------------------------------------------------------------
// Invite modal
// ---------------------------------------------------------------------------

type InviteRole = 'owner' | 'reception';

type InviteState =
  | { phase: 'form'; fullName: string; email: string; role: InviteRole; submitting: boolean }
  | { phase: 'success'; email: string; inviteLinkUrl?: string; invitationExpiresAt?: string };

function InviteModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [state, setState] = useState<InviteState>({
    phase: 'form',
    fullName: '',
    email: '',
    role: 'reception',
    submitting: false,
  });
  const inviteUser = useInviteUser();

  // Reset when re-opening
  function handleOpenChange(value: boolean) {
    if (!value) {
      onClose();
      setTimeout(() => {
        setState({ phase: 'form', fullName: '', email: '', role: 'reception', submitting: false });
      }, 300);
    }
  }

  const isFormValid =
    state.phase === 'form' &&
    state.fullName.trim().length >= 2 &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(state.email.trim());

  function handleSubmit() {
    if (state.phase !== 'form' || !isFormValid) return;
    const { fullName, email, role } = state;
    setState({ ...state, submitting: true });
    inviteUser.mutate(
      { fullName: fullName.trim(), email: email.trim(), role },
      {
        onSuccess: (data) => {
          setState({
            phase: 'success',
            email: data.email,
            inviteLinkUrl: data.inviteLinkUrl ?? undefined,
            invitationExpiresAt: data.invitationExpiresAt ?? undefined,
          });
        },
        onError: (err) => {
          setState({ ...state, submitting: false });
          if (err instanceof ApiError && err.code === 'email_already_active') {
            toast.error('Сотрудник с таким email уже существует');
          } else {
            toast.error('Не удалось отправить приглашение. Попробуйте ещё раз.');
          }
        },
      },
    );
  }

  const FIELD =
    'h-[38px] w-full rounded-[10px] border-[0.5px] border-border-strong bg-surface-2 px-3 text-[13.5px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-fg-subtle focus:bg-surface';

  if (state.phase === 'success') {
    return (
      <AdaptiveModal
        open={open}
        onOpenChange={handleOpenChange}
        title="Приглашение отправлено"
        icon={<IconChip tone="accent" icon={UserPlus} />}
        description="Сотрудник получит письмо с ссылкой для входа"
        footerActions={
          <ModalButton variant="ghost" onClick={() => handleOpenChange(false)}>
            Закрыть
          </ModalButton>
        }
      >
        <div className="flex flex-col items-center gap-3 py-2 text-center">
          <span className="grid size-12 place-items-center rounded-full bg-primary-soft text-primary-deep dark:text-primary">
            <CheckCircle2 className="size-6" />
          </span>
          <div>
            <div className="text-[15px] font-semibold">Приглашение отправлено</div>
            <div className="mt-1 text-[13px] text-fg-muted">
              {state.email} получит письмо в течение нескольких минут.
            </div>
          </div>
        </div>
        {state.inviteLinkUrl ? (
          <div className="mt-4">
            <div className="mb-2 text-[12.5px] text-fg-muted">
              Если письмо не дошло, скопируйте ссылку:
            </div>
            <input
              readOnly
              value={state.inviteLinkUrl}
              onClick={(e) => (e.target as HTMLInputElement).select()}
              className="h-9 w-full rounded-[10px] border-[0.5px] border-border bg-surface-2 px-3 font-mono text-[12px] text-fg-muted outline-none"
            />
            <div className="mt-2 flex items-center justify-between gap-2">
              <GhostBtn
                onClick={() => {
                  void navigator.clipboard.writeText(state.inviteLinkUrl ?? '');
                  toast.success('Ссылка скопирована');
                }}
              >
                Копировать ссылку
              </GhostBtn>
              {state.invitationExpiresAt ? (
                <span className="text-[11.5px] text-fg-subtle">
                  Ссылка действует до {formatDateRu(state.invitationExpiresAt)}
                </span>
              ) : null}
            </div>
          </div>
        ) : null}
      </AdaptiveModal>
    );
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={handleOpenChange}
      title="Пригласить сотрудника"
      icon={<IconChip tone="accent" icon={UserPlus} />}
      description="Сотрудник получит письмо с ссылкой для входа"
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={state.submitting} onClick={() => handleOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton
            variant="primary"
            disabled={!isFormValid || state.submitting}
            onClick={handleSubmit}
          >
            Пригласить
          </ModalButton>
        </>
      }
    >
      <div className="mb-3.5">
        <label className="mb-1.5 block text-[12px] font-semibold text-fg-muted">
          Имя и фамилия
        </label>
        <input
          type="text"
          placeholder="Иван Иванов"
          value={state.fullName}
          onChange={(e) => setState({ ...state, fullName: e.target.value })}
          disabled={state.submitting}
          className={FIELD}
        />
      </div>
      <div className="mb-3.5">
        <label className="mb-1.5 block text-[12px] font-semibold text-fg-muted">Email</label>
        <input
          type="email"
          placeholder="ivan@example.com"
          value={state.email}
          onChange={(e) => setState({ ...state, email: e.target.value })}
          disabled={state.submitting}
          className={FIELD}
        />
      </div>
      <div className="mb-1">
        <div className="mb-1.5 text-[12px] font-semibold text-fg-muted">Роль</div>
        <div className="inline-flex flex-wrap gap-0.5 rounded-full border-[0.5px] border-border bg-surface-2 p-[3px]">
          {(['reception', 'owner'] as const).map((r) => {
            const active = state.role === r;
            return (
              <button
                key={r}
                type="button"
                disabled={state.submitting}
                onClick={() => setState({ ...state, role: r })}
                className={cn(
                  'h-[28px] rounded-full px-3 text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  active
                    ? 'bg-fg text-bg dark:bg-primary dark:text-[#06120c]'
                    : 'text-fg-muted hover:text-fg',
                )}
              >
                {ROLE_LABEL[r]}
              </button>
            );
          })}
        </div>
      </div>
    </AdaptiveModal>
  );
}

// ---------------------------------------------------------------------------
// User row actions
// ---------------------------------------------------------------------------

function handle409(err: unknown) {
  if (err instanceof ApiError) {
    if (err.code === 'cannot_deactivate_self') {
      toast.error('Нельзя деактивировать себя');
    } else if (err.code === 'cannot_deactivate_last_owner') {
      toast.error('Нельзя деактивировать единственного владельца');
    } else if (err.code === 'already_inactive') {
      toast.error('Пользователь уже неактивен');
    } else {
      toast.error('Не удалось выполнить действие. Попробуйте ещё раз.');
    }
  } else {
    toast.error('Не удалось выполнить действие. Попробуйте ещё раз.');
  }
}

function UserRowActions({
  user,
  currentUserId,
}: {
  user: UserData;
  currentUserId: string | undefined;
}) {
  const { open } = useModals();
  const deactivate = useDeactivateUser();
  const reactivate = useReactivateUser();
  const deleteUser = useDeleteUser();
  const revokeInv = useRevokeInvitation();

  const isSelf = user.id === currentUserId;

  if (user.status === 'active') {
    if (isSelf) {
      return (
        <span className="justify-self-end text-[11px] text-fg-subtle">Это вы</span>
      );
    }
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label="Действия с сотрудником"
            className="grid size-7 place-items-center justify-self-end rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg"
          >
            <MoreHorizontal className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            variant="destructive"
            onClick={() =>
              open('confirm', {
                confirm: {
                  title: `Деактивировать ${user.fullName}?`,
                  message: 'Сотрудник потеряет доступ к системе. Его данные сохранятся.',
                  confirmLabel: 'Деактивировать',
                  cancelLabel: 'Отмена',
                  tone: 'danger',
                  onConfirm: () => {
                    deactivate.mutate(user.id, {
                      onError: (err) => handle409(err),
                    });
                  },
                },
              })
            }
          >
            Деактивировать
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            onClick={() =>
              open('confirm', {
                confirm: {
                  title: `Удалить ${user.fullName}?`,
                  message: 'Аккаунт будет помечен как удалённый. Данные сохраняются.',
                  confirmLabel: 'Удалить',
                  cancelLabel: 'Отмена',
                  tone: 'danger',
                  onConfirm: () => {
                    deleteUser.mutate(user.id, {
                      onError: () => toast.error('Не удалось выполнить действие. Попробуйте ещё раз.'),
                    });
                  },
                },
              })
            }
          >
            Удалить
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  if (user.status === 'pending_invitation') {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label="Действия с сотрудником"
            className="grid size-7 place-items-center justify-self-end rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg"
          >
            <MoreHorizontal className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            variant="destructive"
            onClick={() =>
              open('confirm', {
                confirm: {
                  title: `Отозвать приглашение для ${user.email}?`,
                  message: 'Ссылка для входа перестанет работать.',
                  confirmLabel: 'Отозвать',
                  cancelLabel: 'Отмена',
                  tone: 'danger',
                  onConfirm: () => {
                    if (!user.invitationTokenId) {
                      toast.error('Не удалось определить приглашение. Обновите страницу.');
                      return;
                    }
                    revokeInv.mutate(
                      { tokenId: user.invitationTokenId, reason: 'Отозвано владельцем' },
                      {
                        onError: () =>
                          toast.error('Не удалось выполнить действие. Попробуйте ещё раз.'),
                      },
                    );
                  },
                },
              })
            }
          >
            Отозвать приглашение
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  // deactivated
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Действия с сотрудником"
          className="grid size-7 place-items-center justify-self-end rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg"
        >
          <MoreHorizontal className="size-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          onClick={() =>
            open('confirm', {
              confirm: {
                title: `Восстановить ${user.fullName}?`,
                message: 'Сотрудник снова получит доступ к системе.',
                confirmLabel: 'Восстановить',
                cancelLabel: 'Отмена',
                onConfirm: () => {
                  reactivate.mutate(user.id, {
                    onError: (err) => handle409(err),
                  });
                },
              },
            })
          }
        >
          Восстановить
        </DropdownMenuItem>
        <DropdownMenuItem
          variant="destructive"
          onClick={() =>
            open('confirm', {
              confirm: {
                title: `Удалить ${user.fullName}?`,
                message: 'Аккаунт будет помечен как удалённый. Данные сохраняются.',
                confirmLabel: 'Удалить',
                cancelLabel: 'Отмена',
                tone: 'danger',
                onConfirm: () => {
                  deleteUser.mutate(user.id, {
                    onError: () => toast.error('Не удалось выполнить действие. Попробуйте ещё раз.'),
                  });
                },
              },
            })
          }
        >
          Удалить
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// ---------------------------------------------------------------------------
// TeamSection — wired (Phase 104-05 SET-02)
// ---------------------------------------------------------------------------

export function TeamSection() {
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  const currentUserId = session.data?.id;
  const [inviteOpen, setInviteOpen] = useState(false);

  // Owner gate (T-104-12): reception fires ZERO users API calls
  const usersQuery = useUsers({}, role);

  return (
    <SectionCard
      id={ID_TEAM}
      icon={Users}
      title="Доступы команды"
      desc="Кто и как может работать в админке."
      action={
        can(role, 'list', 'users') ? (
          <PrimaryBtn onClick={() => setInviteOpen(true)}>+ Пригласить</PrimaryBtn>
        ) : undefined
      }
    >
      {/* Reception: Lock-EmptyState INSIDE body — zero users API calls (T-104-12) */}
      {!can(role, 'list', 'users') ? (
        <EmptyState
          icon={Lock}
          title="Недостаточно прав"
          message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
          className="py-12"
        />
      ) : usersQuery.isPending ? (
        <div className="flex flex-col gap-2 pt-2">
          <Skeleton className="h-[46px] w-full rounded-xl bg-surface-3" />
          <Skeleton className="h-[46px] w-full rounded-xl bg-surface-3" />
          <Skeleton className="h-[46px] w-full rounded-xl bg-surface-3" />
        </div>
      ) : usersQuery.isError ? (
        <div className="py-4 text-[12px] text-fg-muted">
          Не удалось загрузить список сотрудников.{' '}
          <button
            type="button"
            onClick={() => void usersQuery.refetch()}
            className="font-semibold text-fg hover:underline"
          >
            Повторить
          </button>
        </div>
      ) : !usersQuery.data || usersQuery.data.items.length === 0 ? (
        <EmptyState
          icon={Users}
          title="Сотрудники не найдены"
          message={'Пригласите первого сотрудника, нажав «+ Пригласить».'}
          className="py-12"
        />
      ) : (
        <div className="pt-2">
          <div
            className={cn(
              TEAM_COLS,
              'border-b-[0.5px] border-border pb-2 text-[10.5px] font-semibold uppercase tracking-[0.3px] text-fg-subtle max-md:hidden',
            )}
          >
            <span>Сотрудник</span>
            <span>Роль</span>
            <span>Статус</span>
            <span />
          </div>
          {usersQuery.data.items.map((user) => {
            const initials = getInitials(user.fullName);
            return (
              <div
                key={user.id}
                className={cn(
                  TEAM_COLS,
                  'border-t-[0.5px] border-border py-2.5 first:border-t-0 md:first:border-t-[0.5px]',
                )}
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <Initials
                    initials={initials}
                    color="linear-gradient(135deg,#94a3b8,#64748b)"
                    className="size-[30px] text-[11px]"
                  />
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-semibold">{user.fullName}</div>
                    <div className="truncate text-[11px] text-fg-subtle">{user.email}</div>
                  </div>
                </div>
                {/* Role badge */}
                <span
                  className={cn(
                    'justify-self-start rounded-full px-2 py-0.5 text-[10.5px] font-bold uppercase',
                    ROLE_TONE[user.role],
                  )}
                >
                  {ROLE_LABEL[user.role]}
                </span>
                {/* Status badge */}
                <span className="max-md:hidden">
                  {user.status === 'pending_invitation' ? (
                    <span className="rounded-full bg-warning-soft px-2 py-0.5 text-[10.5px] font-bold uppercase text-warning-deep">
                      Ожидает
                    </span>
                  ) : user.status === 'deactivated' ? (
                    <span className="rounded-full bg-surface-3 px-2 py-0.5 text-[10.5px] font-bold uppercase text-fg-muted">
                      Неактивен
                    </span>
                  ) : null}
                </span>
                <UserRowActions user={user} currentUserId={currentUserId} />
              </div>
            );
          })}
        </div>
      )}

      <InviteModal open={inviteOpen} onClose={() => setInviteOpen(false)} />
    </SectionCard>
  );
}

export function IntegrationsSection({ data }: { data: SettingsData }) {
  return (
    <SectionCard
      id="integrations"
      icon={Code}
      title="Интеграции и API"
      desc="Внешние системы, подключённые к «Моему залу». Для каждой — статус и последняя синхронизация."
      action={<span className="text-[12px] font-semibold text-fg-muted">Все 24 →</span>}
    >
      <div className="flex flex-col gap-2 pt-2">
        {data.integrations.map((it) => (
          <div
            key={it.name}
            className="flex flex-wrap items-center gap-3 rounded-xl border-[0.5px] border-border bg-surface-2 p-3"
          >
            <span
              className="grid size-12 shrink-0 place-items-center rounded-xl text-[12px] font-bold text-white"
              style={{ background: it.color }}
            >
              {it.logo}
            </span>
            <div className="min-w-0 flex-1">
              <div className={cn('text-[13px] font-semibold', it.muted && 'text-fg-muted')}>
                {it.name}
              </div>
              <div className="text-[11.5px] text-fg-subtle">{it.desc}</div>
              {it.meta ? (
                <div
                  className={cn(
                    'mt-0.5 text-[11px]',
                    it.status === 'warn' ? 'text-warning-deep' : 'text-fg-subtle',
                  )}
                >
                  {it.meta}
                </div>
              ) : null}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {it.chip ? <Chip tone={it.chipTone}>{it.chip}</Chip> : null}
              <GhostBtn>{it.action}</GhostBtn>
            </div>
          </div>
        ))}
      </div>
      <SettingRow label="API-доступ" hint="Для разработчиков и собственных интеграций.">
        <div className="flex flex-wrap items-center gap-2">
          <input
            readOnly
            value="mz_live_••••••••••••••••••••a1B7"
            className="h-[38px] min-w-[220px] flex-1 rounded-[10px] border-[0.5px] border-border-strong bg-surface-2 px-3 font-mono text-[12.5px] text-fg-muted outline-none"
          />
          <GhostBtn>Показать</GhostBtn>
          <GhostBtn>Ротация</GhostBtn>
        </div>
        <div className="mt-1.5 text-[11px] text-fg-subtle">
          создан 12 фев · использован 142 раза за сутки · последний запрос —{' '}
          <b className="font-semibold text-fg-muted">POST /v1/bookings</b> · 14 сек назад
        </div>
      </SettingRow>
    </SectionCard>
  );
}

export function BillingSection({ data }: { data: SettingsData }) {
  return (
    <SectionCard
      id="billing"
      icon={Gift}
      title="Тариф «Мой зал»"
      desc="Подписка на сервис, лимиты по клиентам, SMS и хранилищу. Платёжный реквизит для счёта."
    >
      <div className="grid gap-3 pt-3 lg:grid-cols-[1.25fr_1fr]">
        <div
          className="relative overflow-hidden rounded-xl p-5 text-white"
          style={{ background: 'linear-gradient(160deg,#1c1917,#2a2826)' }}
        >
          <span
            aria-hidden
            className="pointer-events-none absolute -right-10 -top-10 size-40 rounded-full"
            style={{
              background: 'radial-gradient(circle, rgba(45,212,164,0.22), transparent 70%)',
            }}
          />
          <div className="relative text-[10.5px] font-bold uppercase tracking-[0.5px] text-primary">
            Текущий тариф
          </div>
          <div className="relative mt-1 text-[26px] font-bold">Pro · 3 филиала</div>
          <div className="relative mt-1 text-[12px] text-white/60">
            19 800 ₽ / мес · <b className="font-semibold text-white">237 600 ₽</b> в год — экономия
            39 600 ₽
          </div>
          <div className="relative mt-4 grid grid-cols-2 gap-2 text-[12px]">
            {data.planFeatures.map((f) => (
              <div key={f} className="flex items-center gap-1.5 text-white/80">
                <Check className="size-3.5 shrink-0 text-primary" strokeWidth={2.6} />
                {f}
              </div>
            ))}
          </div>
          <div className="relative mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-3 text-[11.5px] text-white/55">
            Следующее списание: <b className="font-semibold text-white">1 июня 2026</b> · Visa 4287
            <button
              type="button"
              className="rounded-full bg-white/10 px-3 py-1 text-[12px] font-semibold text-white hover:bg-white/20"
            >
              Сравнить тарифы →
            </button>
          </div>
        </div>

        <div className="rounded-xl border-[0.5px] border-border bg-surface-2 p-4">
          <div className="text-[13px] font-bold">Использование за май</div>
          <div className="mt-3 flex flex-col gap-3">
            {data.usage.map((u) => (
              <div key={u.label}>
                <div className="flex items-center justify-between text-[11.5px]">
                  <span className="text-fg-muted">{u.label}</span>
                  <span className="tabular-nums">
                    {u.used} / <b className="font-semibold text-fg">{u.limit}</b>
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-3">
                  <div
                    className={cn(
                      'h-full rounded-full',
                      u.tone === 'warn' ? 'bg-warning' : 'bg-primary',
                    )}
                    style={{ width: `${u.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 text-[11px] text-fg-subtle">
            SMS заканчиваются за 4 дня до конца месяца — рекомендуем докупить пакет 1 000 SMS за 1
            200 ₽.
          </div>
        </div>
      </div>

      <SettingRow label="Платёжный метод">
        <div className="flex flex-wrap items-center gap-3 rounded-xl border-[0.5px] border-border bg-surface-2 p-3">
          <span className="grid h-8 w-12 place-items-center rounded-md bg-gradient-to-br from-[#1a4ba8] to-[#2563eb] text-[11px] font-bold text-white">
            Visa
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-semibold">Visa **** 4287 · Сбер</div>
            <div className="text-[11.5px] text-fg-subtle">
              истекает 09/27 · оплата автоматически 1-го числа
            </div>
          </div>
          <GhostBtn>Заменить</GhostBtn>
        </div>
        <div className="mt-2">
          <GhostBtn>+ Платить по счёту (ООО)</GhostBtn>
        </div>
      </SettingRow>

      <SettingRow label="Платёжные документы" hint="Скачать чек или счёт-фактуру можно за 5 лет.">
        <div className="flex flex-col">
          {data.invoices.map((inv, i) => (
            <div
              key={inv.num}
              className={cn(
                'grid grid-cols-[110px_minmax(0,1fr)_auto_72px_32px] items-center gap-3 py-2.5 text-[12.5px] max-sm:grid-cols-[minmax(0,1fr)_auto]',
                i > 0 && 'border-t-[0.5px] border-border',
              )}
            >
              <span className="font-mono text-[11.5px] text-fg-muted max-sm:hidden">{inv.num}</span>
              <div className="min-w-0">
                <div className="truncate font-semibold">{inv.desc}</div>
                <div className="truncate text-[11px] text-fg-subtle">{inv.descSub}</div>
              </div>
              <span className="text-right font-semibold tabular-nums">{inv.amount}</span>
              <span className="rounded-full bg-primary-soft px-2 py-0.5 text-center text-[10px] font-bold uppercase text-primary-deep dark:text-primary max-sm:hidden">
                оплачен
              </span>
              <button
                type="button"
                aria-label="Скачать"
                onClick={() => toast.success('Документ скачан', { description: inv.num })}
                className="grid size-7 place-items-center justify-self-end rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg max-sm:hidden"
              >
                <Download className="size-3.5" />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => toast('Все документы')}
            className="mt-2 self-start text-[12px] font-semibold text-fg-muted hover:text-fg"
          >
            Все документы · 18 →
          </button>
        </div>
      </SettingRow>
    </SectionCard>
  );
}

const DANGER_ROWS: {
  label: string;
  sub: string;
  btn: string;
  danger?: boolean;
  disabled?: boolean;
  red?: boolean;
}[] = [
  {
    label: 'Перенести филиал в другую сеть',
    sub: 'Клиенты, абонементы и тренеры мигрируют. Расписание остановится на 1 час.',
    btn: 'Перенести…',
  },
  {
    label: 'Сбросить настройки филиала',
    sub: 'Часы, уведомления и тема вернутся к умолчаниям сети. Клиенты и абонементы — без изменений.',
    btn: 'Сбросить «Тверская»',
    danger: true,
  },
  {
    label: 'Закрыть филиал',
    sub: 'Запись остановится сразу. Клиенты получат push с предложением другого зала и возвратом за неиспользованные дни.',
    btn: 'Закрыть «Тверская»…',
    danger: true,
  },
  {
    label: 'Удалить аккаунт сети',
    sub: 'Только владелец. 30 дней «корзина», потом данные удаляются необратимо.',
    btn: 'Только Виктор Львов',
    danger: true,
    disabled: true,
    red: true,
  },
];

export function DangerSection() {
  const { open } = useModals();
  return (
    <SectionCard
      id="danger"
      icon={TriangleAlert}
      title="Опасная зона"
      desc="Эти действия необратимы или требуют подтверждения владельца сети."
      danger
    >
      {DANGER_ROWS.map((r, i) => (
        <div
          key={r.label}
          className={cn(
            'flex flex-wrap items-center justify-between gap-3 py-3.5',
            i > 0 && 'border-t-[0.5px] border-danger/20',
          )}
        >
          <div className="min-w-0">
            <div className={cn('text-[13px] font-semibold', r.red && 'text-danger')}>{r.label}</div>
            <div className="mt-0.5 text-[11.5px] text-fg-muted">{r.sub}</div>
          </div>
          <GhostBtn
            danger={r.danger}
            disabled={r.disabled}
            onClick={
              r.danger
                ? () =>
                    open('confirm', {
                      confirm: {
                        title: `${r.label}?`,
                        message: r.sub,
                        tone: 'danger',
                        confirmLabel: r.btn,
                        requireText: 'ТВЕРСКАЯ',
                        onConfirm: () => {
                          toast.success('Действие выполнено');
                        },
                      },
                    })
                : () => toast(r.label)
            }
          >
            {r.btn}
          </GhostBtn>
        </div>
      ))}
    </SectionCard>
  );
}
