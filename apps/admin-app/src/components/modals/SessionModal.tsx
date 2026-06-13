import { useEffect, useState, type ReactNode } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { ROUTES } from '@/app/routes';
import { router } from '@/app/router';
import { Initials } from '@/components/ui/initials';
import { Segmented } from '@/components/ui/Segmented';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Activity,
  Building2,
  Calendar,
  Check,
  CircleX,
  Clock,
  Info,
  MoreHorizontal,
  RefreshCw,
  TriangleAlert,
  UserPlus,
  Users,
} from '@/components/icons';
import type { SessionScreen } from './modals-context';
import { AdaptiveModal } from './AdaptiveModal';
import {
  Callout,
  Field,
  FieldRow,
  IconChip,
  ModalButton,
  ModalInput,
  ModalSelect,
  ToggleRow,
} from './fields';

type Go = (screen: SessionScreen) => void;
type ScreenProps = { open: boolean; onOpenChange: (open: boolean) => void; go: Go };

function Badge({ tone = 'accent', children }: { tone?: 'accent' | 'warn'; children: ReactNode }) {
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.3px]',
        tone === 'accent'
          ? 'bg-primary-soft text-primary-deep dark:text-primary'
          : 'bg-warning-soft text-warning-deep',
      )}
    >
      {children}
    </span>
  );
}

const cancelBtn = (onOpenChange: (o: boolean) => void, label = 'Отмена') => (
  <ModalButton variant="ghost" onClick={() => onOpenChange(false)}>
    {label}
  </ModalButton>
);

/* ───────────────────────── Детали ───────────────────────── */

const ROSTER = [
  { i: 'АП', c: 'linear-gradient(135deg,#6366f1,#818cf8)' },
  { i: 'МС', c: 'linear-gradient(135deg,#10b981,#34d399)' },
  { i: 'КЛ', c: 'linear-gradient(135deg,#f43f5e,#fb7185)' },
  { i: 'ИК', c: 'linear-gradient(135deg,#0ea5e9,#38bdf8)' },
  { i: 'СО', c: 'linear-gradient(135deg,#f59e0b,#fbbf24)' },
];

function DetailScreen({ open, onOpenChange, go }: ScreenProps) {
  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip icon={Activity} />}
      title={
        <span className="flex flex-wrap items-center gap-2">
          Йога · групповая <Badge>Запланирована</Badge>
        </span>
      }
      description="Сегодня, 30 апр · 15:00–16:00 · Зал 1"
      footerInfo={
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label="Ещё"
              className="grid size-9 place-items-center rounded-full border-[0.5px] border-border bg-surface text-fg-muted transition-colors hover:border-border-strong hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <MoreHorizontal className="size-[15px]" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="min-w-[180px]">
            <DropdownMenuItem onSelect={() => toast.success('Тренировка продублирована')}>
              Дублировать
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => toast('Экспорт списка участников')}>
              Экспорт
            </DropdownMenuItem>
            <DropdownMenuItem
              className="text-danger focus:text-danger"
              onSelect={() => go('cancel')}
            >
              Отменить тренировку
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      }
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => go('reschedule')}>
            Перенести
          </ModalButton>
          <ModalButton onClick={() => toast.success('Открыт чек-ин участников')}>
            <Check className="size-3.5" strokeWidth={2.6} />
            Чек-ин участников
          </ModalButton>
        </>
      }
    >
      <div className="flex items-center gap-3 border-b-[0.5px] border-dashed border-border py-3">
        <Initials
          initials="ОВ"
          color="linear-gradient(135deg,#8b5cf6,#ec4899)"
          className="size-9 text-xs"
        />
        <div className="min-w-0 flex-1">
          <div className="text-[11.5px] text-fg-subtle">Тренер</div>
          <div className="text-[13.5px] font-semibold">Ольга Власова</div>
        </div>
        <ModalButton
          variant="ghost"
          className="h-[34px] px-3 text-[12.5px]"
          onClick={() => {
            onOpenChange(false);
            void router.navigate(ROUTES.trainer('t1'));
          }}
        >
          Профиль
        </ModalButton>
      </div>

      <div className="mt-3.5">
        <div className="mb-2 flex items-baseline gap-2">
          <span className="text-sm font-bold">8 из 12</span>
          <span className="text-xs text-fg-muted">записано</span>
          <span className="ml-auto text-xs text-fg-subtle">осталось 4 места</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-surface-3">
          <div
            className="h-full rounded-full bg-[linear-gradient(90deg,var(--primary),#5ee9b8)]"
            style={{ width: '66%' }}
          />
        </div>
        <div className="mt-3.5 flex flex-wrap items-center">
          {ROSTER.map((a) => (
            <span
              key={a.i}
              style={{ background: a.c }}
              className="-mr-2 grid size-8 place-items-center rounded-full border-2 border-surface text-[11px] font-bold text-white"
            >
              {a.i}
            </span>
          ))}
          <span className="-mr-2 grid size-8 place-items-center rounded-full border-2 border-surface bg-surface-3 text-[11px] font-bold text-fg-muted">
            +3
          </span>
        </div>
      </div>

      <div className="mt-3.5">
        <Callout tone="warn" icon={RefreshCw}>
          Перенесена с <b>1 мая, 09:00</b>. Участники уведомлены.
        </Callout>
      </div>
    </AdaptiveModal>
  );
}

/* ───────────────────────── Создание / Редактирование ───────────────────────── */

function FormScreen({
  open,
  onOpenChange,
  mode,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: 'create' | 'edit';
}) {
  const [type, setType] = useState<'group' | 'personal'>('group');

  useEffect(() => {
    if (open) setType('group');
  }, [open]);

  const create = mode === 'create';

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      size="wide"
      icon={<IconChip icon={Calendar} />}
      title={create ? 'Новая тренировка' : 'Редактирование тренировки'}
      description={create ? 'Добавьте занятие в расписание зала' : 'Йога · групповая · #SS-3120'}
      footerInfo={
        create ? undefined : (
          <button
            type="button"
            aria-label="Удалить тренировку"
            onClick={() => toast('Откроется подтверждение удаления')}
            className="grid size-9 place-items-center rounded-full border-[0.5px] border-border bg-surface text-fg-muted transition-colors hover:border-danger hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <CircleX className="size-[15px]" />
          </button>
        )
      }
      footerActions={
        <>
          {cancelBtn(onOpenChange)}
          <ModalButton
            onClick={() => {
              toast.success(create ? 'Тренировка создана' : 'Изменения сохранены');
              onOpenChange(false);
            }}
          >
            {create ? 'Создать тренировку' : 'Сохранить'}
          </ModalButton>
        </>
      }
    >
      <Field label="Тип">
        <Segmented
          options={[
            { value: 'group', label: 'Групповая' },
            { value: 'personal', label: 'Персональная' },
          ]}
          value={type}
          onChange={setType}
          ariaLabel="Тип тренировки"
        />
      </Field>
      <FieldRow>
        <Field label="Направление">
          <ModalSelect defaultValue="Йога">
            <option>Йога</option>
            <option>Стретчинг</option>
            <option>Пилатес</option>
            <option>Функционал</option>
            <option>Бокс</option>
            <option>Кардио</option>
          </ModalSelect>
        </Field>
        <Field label="Тренер">
          <ModalSelect defaultValue="Ольга Власова">
            <option>Ольга Власова</option>
            <option>Артём Поляков</option>
            <option>Вадим Дроздов</option>
          </ModalSelect>
        </Field>
      </FieldRow>
      <FieldRow cols={3}>
        <Field label="Дата">
          <ModalInput defaultValue="30.04.2026" />
        </Field>
        <Field label="Начало">
          <ModalInput defaultValue="15:00" />
        </Field>
        <Field label="Длит.">
          <ModalSelect defaultValue="60 мин">
            <option>60 мин</option>
            <option>45 мин</option>
            <option>90 мин</option>
          </ModalSelect>
        </Field>
      </FieldRow>
      <FieldRow>
        <Field label="Зал">
          <ModalSelect defaultValue="Зал 1">
            <option>Зал 1</option>
            <option>Зал 2</option>
            <option>Кардио-зона</option>
          </ModalSelect>
        </Field>
        {type === 'group' ? (
          <Field label="Вместимость">
            <ModalInput defaultValue="12" inputMode="numeric" />
          </Field>
        ) : (
          <div />
        )}
      </FieldRow>
      <Field label="Повтор">
        <ModalSelect defaultValue="Не повторять">
          <option>Не повторять</option>
          <option>Каждую неделю · Ср</option>
          <option>По будням</option>
          <option>Пн / Ср / Пт</option>
        </ModalSelect>
      </Field>
      <Callout tone="accent" icon={Check}>
        Слот свободен — <b>Зал 1</b> и тренер не заняты в это время.
      </Callout>
    </AdaptiveModal>
  );
}

/* ───────────────────────── Перенос ───────────────────────── */

function RescheduleScreen({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [room, setRoom] = useState('Зал 1');
  const [time, setTime] = useState('15:00');
  const [notify, setNotify] = useState(true);

  useEffect(() => {
    if (open) {
      setRoom('Зал 1');
      setTime('15:00');
      setNotify(true);
    }
  }, [open]);

  const busy = room === 'Зал 1' && time.trim() === '15:00';

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip tone="warn" icon={RefreshCw} />}
      title="Перенести тренировку"
      description="Йога · групповая · сейчас 30 апр, 15:00"
      footerActions={
        <>
          {cancelBtn(onOpenChange)}
          <ModalButton
            disabled={busy}
            onClick={() => {
              toast.success('Тренировка перенесена');
              onOpenChange(false);
            }}
          >
            Перенести
          </ModalButton>
        </>
      }
    >
      <FieldRow cols={3}>
        <Field label="Новая дата">
          <ModalInput defaultValue="02.05.2026" />
        </Field>
        <Field label="Начало">
          <ModalInput value={time} onChange={(e) => setTime(e.target.value)} />
        </Field>
        <Field label="Зал">
          <ModalSelect value={room} onChange={(e) => setRoom(e.target.value)}>
            <option>Зал 1</option>
            <option>Зал 2</option>
            <option>Кардио-зона</option>
          </ModalSelect>
        </Field>
      </FieldRow>
      <div
        className={cn(
          'mt-3 flex items-center gap-2 text-[12.5px] font-semibold',
          busy ? 'text-danger' : 'text-primary-deep dark:text-primary',
        )}
      >
        {busy ? (
          <TriangleAlert className="size-[15px]" />
        ) : (
          <Check className="size-[15px]" strokeWidth={2.6} />
        )}
        {busy
          ? 'Конфликт — Зал 1 занят в 15:00. Выберите другой слот.'
          : 'Слот свободен — можно переносить'}
      </div>
      <ToggleRow
        title="Уведомить участников"
        sub="8 человек получат SMS и push о переносе"
        checked={notify}
        onChange={setNotify}
      />
    </AdaptiveModal>
  );
}

/* ───────────────────────── Конфликты ───────────────────────── */

const CONFLICTS: {
  id: string;
  icon: typeof Building2;
  head: string;
  a: { t: string; s: string };
  b: { t: string; s: string };
  acts: { label: string; go?: SessionScreen; toast?: string }[];
}[] = [
  {
    id: 'c1',
    icon: Building2,
    head: 'Зал 1 занят дважды · Ср, 15:00',
    a: { t: 'Йога · групповая', s: 'Ольга Власова · 15:00–16:00' },
    b: { t: 'Стретчинг · персон.', s: 'Артём Поляков · 15:30–16:30' },
    acts: [
      { label: 'Перенести вторую', go: 'reschedule' },
      { label: 'Открыть', toast: 'Открыта в расписании' },
    ],
  },
  {
    id: 'c2',
    icon: Users,
    head: 'Тренер занят · Вадим Дроздов · Пт, 18:00',
    a: { t: 'Бокс · группа', s: 'Зал 2 · 18:00–19:00' },
    b: { t: 'Функционал · перс.', s: 'Кардио-зона · 18:00–19:00' },
    acts: [
      { label: 'Сменить тренера', toast: 'Назначен другой тренер' },
      { label: 'Перенести', go: 'reschedule' },
    ],
  },
  {
    id: 'c3',
    icon: Clock,
    head: 'Клиент в двух записях · Анна Петрова · Сб, 12:00',
    a: { t: 'Пилатес · персон.', s: '12:00–13:00 · Зал 2' },
    b: { t: 'Йога · группа', s: '12:00–13:00 · Зал 1' },
    acts: [{ label: 'Снять с группы', toast: 'Запись отменена' }],
  },
];

function ConflictScreen({ open, onOpenChange, go }: ScreenProps) {
  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      size="wide"
      icon={<IconChip tone="danger" icon={TriangleAlert} />}
      title={
        <span className="flex flex-wrap items-center gap-2">
          Конфликты в расписании <Badge tone="warn">3</Badge>
        </span>
      }
      description="Найдены пересечения по тренерам и залам на этой неделе"
      footerActions={
        <>
          {cancelBtn(onOpenChange, 'Закрыть')}
          <ModalButton onClick={() => toast.success('Автоперенос предложен для 3 конфликтов')}>
            Решить автоматически
          </ModalButton>
        </>
      }
    >
      {CONFLICTS.map((c) => {
        const Icon = c.icon;
        return (
          <div key={c.id} className="mt-3 rounded-xl border-[0.5px] border-border p-3.5">
            <div className="mb-2.5 flex items-center gap-2 text-[12.5px] font-semibold text-danger">
              <Icon className="size-[15px]" />
              {c.head}
            </div>
            <div className="grid grid-cols-1 items-center gap-2.5 min-[420px]:grid-cols-[1fr_auto_1fr]">
              <div className="rounded-lg bg-surface-2 px-3 py-2.5">
                <div className="text-[12.5px] font-semibold">{c.a.t}</div>
                <div className="mt-0.5 text-[11px] text-fg-subtle">{c.a.s}</div>
              </div>
              <span className="text-[11px] font-bold text-fg-subtle max-[420px]:hidden">⚡</span>
              <div className="rounded-lg bg-surface-2 px-3 py-2.5 opacity-80">
                <div className="text-[12.5px] font-semibold">{c.b.t}</div>
                <div className="mt-0.5 text-[11px] text-fg-subtle">{c.b.s}</div>
              </div>
            </div>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {c.acts.map((a) => (
                <ModalButton
                  key={a.label}
                  variant="ghost"
                  className="h-[34px] px-3 text-[12.5px]"
                  onClick={() => (a.go ? go(a.go) : a.toast ? toast(a.toast) : undefined)}
                >
                  {a.label}
                </ModalButton>
              ))}
            </div>
          </div>
        );
      })}
    </AdaptiveModal>
  );
}

/* ───────────────────────── Лист ожидания ───────────────────────── */

const WAITLIST = [
  {
    id: 'w1',
    i: 'ДВ',
    c: 'linear-gradient(135deg,#6366f1,#818cf8)',
    name: 'Дмитрий Васин',
    sub: 'в очереди с 09:14',
  },
  {
    id: 'w2',
    i: 'ЕС',
    c: 'linear-gradient(135deg,#f59e0b,#fbbf24)',
    name: 'Екатерина Соколова',
    sub: 'в очереди с 09:40',
  },
  {
    id: 'w3',
    i: 'ПС',
    c: 'linear-gradient(135deg,#10b981,#34d399)',
    name: 'Павел Сидоров',
    sub: 'в очереди с 10:05',
  },
  {
    id: 'w4',
    i: 'ЛТ',
    c: 'linear-gradient(135deg,#f43f5e,#fb7185)',
    name: 'Лидия Тарасова',
    sub: 'в очереди с 10:22',
  },
];

function WaitlistScreen({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [list, setList] = useState(WAITLIST);

  useEffect(() => {
    if (open) setList(WAITLIST);
  }, [open]);

  const promote = (id: string, name: string) => {
    setList((l) => l.filter((p) => p.id !== id));
    toast.success('Записан из листа ожидания', { description: name });
  };

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip tone="indigo" icon={UserPlus} />}
      title={
        <span className="flex flex-wrap items-center gap-2">
          Лист ожидания <Badge tone="warn">12/12</Badge>
        </span>
      }
      description="Йога · группа · Ср, 15:00 · мест нет"
      footerInfo={
        <span>
          В очереди: <b className="font-[650] text-fg">{list.length}</b>
        </span>
      }
      footerActions={
        <ModalButton variant="ghost" onClick={() => toast('Всем отправлено уведомление')}>
          Уведомить всех
        </ModalButton>
      }
    >
      <Callout tone="accent" icon={Info}>
        Когда освободится место, <b>первый в списке</b> получит уведомление и автоматически
        запишется.
      </Callout>
      <div className="mt-1.5">
        {list.map((p, idx) => (
          <div
            key={p.id}
            className="flex items-center gap-3 border-b-[0.5px] border-border py-2.5 last:border-b-0"
          >
            <span
              className={cn(
                'grid size-6 shrink-0 place-items-center rounded-full text-[11.5px] font-bold tabular-nums',
                idx === 0 ? 'bg-primary text-[#06120c]' : 'bg-surface-3 text-fg-muted',
              )}
            >
              {idx + 1}
            </span>
            <Initials initials={p.i} color={p.c} className="size-8 text-[11px]" />
            <div className="min-w-0 flex-1">
              <div className="text-[13.5px] font-semibold">{p.name}</div>
              <div className="text-[11px] text-fg-subtle">{p.sub}</div>
            </div>
            <ModalButton
              className="h-[34px] px-3 text-[12.5px]"
              onClick={() => promote(p.id, p.name)}
            >
              Записать
            </ModalButton>
          </div>
        ))}
        {list.length === 0 ? (
          <div className="py-6 text-center text-[12.5px] text-fg-subtle">Очередь пуста</div>
        ) : null}
      </div>
    </AdaptiveModal>
  );
}

/* ───────────────────────── Отмена ───────────────────────── */

function CancelScreen({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [notify, setNotify] = useState(true);

  useEffect(() => {
    if (open) setNotify(true);
  }, [open]);

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip tone="danger" icon={CircleX} />}
      title="Отменить тренировку?"
      description="Йога · групповая · Ср, 15:00 · Зал 1"
      footerActions={
        <>
          {cancelBtn(onOpenChange, 'Не отменять')}
          <ModalButton
            variant="danger"
            onClick={() => {
              toast.success('Тренировка отменена');
              onOpenChange(false);
            }}
          >
            Отменить тренировку
          </ModalButton>
        </>
      }
    >
      <ToggleRow
        title="Уведомить участников"
        sub="8 записанных получат сообщение об отмене"
        checked={notify}
        onChange={setNotify}
      />
      <div className="mt-3.5">
        <Callout tone="danger" icon={TriangleAlert}>
          Запись вернётся на абонементы участников. Лист ожидания <b>(4 человека)</b> будет закрыт.
        </Callout>
      </div>
    </AdaptiveModal>
  );
}

/* ───────────────────────── Диспетчер ───────────────────────── */

export function SessionModal({
  open,
  onOpenChange,
  payload,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payload?: { screen?: SessionScreen };
}) {
  const [screen, setScreen] = useState<SessionScreen>(payload?.screen ?? 'detail');

  useEffect(() => {
    if (open) setScreen(payload?.screen ?? 'detail');
  }, [open, payload?.screen]);

  const props = { open, onOpenChange, go: setScreen };

  switch (screen) {
    case 'create':
      return <FormScreen open={open} onOpenChange={onOpenChange} mode="create" />;
    case 'edit':
      return <FormScreen open={open} onOpenChange={onOpenChange} mode="edit" />;
    case 'reschedule':
      return <RescheduleScreen open={open} onOpenChange={onOpenChange} />;
    case 'conflict':
      return <ConflictScreen {...props} />;
    case 'waitlist':
      return <WaitlistScreen open={open} onOpenChange={onOpenChange} />;
    case 'cancel':
      return <CancelScreen open={open} onOpenChange={onOpenChange} />;
    case 'detail':
    default:
      return <DetailScreen {...props} />;
  }
}
