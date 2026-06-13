import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { Initials } from '@/components/ui/initials';
import { Segmented } from '@/components/ui/Segmented';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Archive, Camera, Check, Plus, TriangleAlert, UserPlus } from '@/components/icons';
import { useModals } from './modals-context';
import { AdaptiveModal } from './AdaptiveModal';
import {
  Field,
  FieldRow,
  ModalButton,
  ModalInput,
  ModalSelect,
  ModalTextarea,
  Section,
} from './fields';

interface FormState {
  firstName: string;
  lastName: string;
  phone: string;
  email: string;
  specs: string[];
  employment: 'staff' | 'self';
  ratePersonal: string;
  rateGroup: string;
  commission: string;
  branch: string;
  status: string;
  note: string;
}

const SPEC_OPTIONS = [
  'Йога',
  'Стретчинг',
  'Пилатес',
  'Силовые',
  'Кардио',
  'Бокс',
  'Детские группы',
];
const BRANCHES = ['Тверская', 'Сокольники', 'Новокосино'];
const STATUSES = ['Активна', 'На рассмотрении', 'В отпуске', 'В архиве'];

const EMPLOYMENT: { value: FormState['employment']; label: string }[] = [
  { value: 'staff', label: 'В штате' },
  { value: 'self', label: 'Самозанятый' },
];

const CREATE_INITIAL: FormState = {
  firstName: '',
  lastName: '',
  phone: '',
  email: '',
  specs: [],
  employment: 'staff',
  ratePersonal: '',
  rateGroup: '',
  commission: '',
  branch: 'Тверская',
  status: 'Активна',
  note: '',
};

const EDIT_INITIAL: FormState = {
  firstName: 'Ольга',
  lastName: 'Власова',
  phone: '+7 916 503-77-12',
  email: 'o.vlasova@moizal.ru',
  specs: ['Йога', 'Стретчинг', 'Пилатес'],
  employment: 'self',
  ratePersonal: '1 800',
  rateGroup: '1 200',
  commission: '30',
  branch: 'Тверская',
  status: 'Активна',
  note: 'Ведёт женские группы по утрам. Сертификат Yoga Alliance RYT-200.',
};

/** Мультивыбор специализаций (чипы с галочкой). */
function SpecChips({ value, onToggle }: { value: string[]; onToggle: (v: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {SPEC_OPTIONS.map((o) => {
        const on = value.includes(o);
        return (
          <button
            key={o}
            type="button"
            aria-pressed={on}
            onClick={() => onToggle(o)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border-[0.5px] px-3.5 py-2 text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              on
                ? 'border-fg bg-fg text-bg dark:border-primary dark:bg-primary dark:text-[#06120c]'
                : 'border-border-strong bg-surface text-fg hover:border-fg-subtle',
            )}
          >
            {on ? <Check className="size-3" strokeWidth={3} /> : null}
            {o}
          </button>
        );
      })}
    </div>
  );
}

export function TrainerFormModal({
  open,
  onOpenChange,
  payload,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payload?: { trainerId?: string };
}) {
  const { open: openModal } = useModals();
  const mode = payload?.trainerId ? 'edit' : 'create';
  const initial = useMemo(() => (mode === 'edit' ? EDIT_INITIAL : CREATE_INITIAL), [mode]);

  const [state, setState] = useState<FormState>(initial);
  const [guard, setGuard] = useState(false);

  useEffect(() => {
    if (open) {
      setState(initial);
      setGuard(false);
    }
  }, [open, initial]);

  const dirty = useMemo(() => JSON.stringify(state) !== JSON.stringify(initial), [state, initial]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setState((s) => ({ ...s, [k]: v }));

  const requestClose = (next: boolean) => {
    if (next) return;
    if (dirty) setGuard(true);
    else onOpenChange(false);
  };

  const save = () => {
    toast.success(mode === 'create' ? 'Тренер добавлен в команду' : 'Изменения сохранены');
    onOpenChange(false);
  };

  const discard = () => {
    setGuard(false);
    onOpenChange(false);
  };

  const archive = () => {
    onOpenChange(false);
    openModal('confirm', {
      confirm: {
        title: 'Архивировать тренера?',
        message: (
          <>
            «{EDIT_INITIAL.firstName} {EDIT_INITIAL.lastName}» переместится в архив и исчезнет из
            активного состава.
          </>
        ),
        tone: 'danger',
        confirmLabel: 'Архивировать',
        onConfirm: () => {
          toast.success('Тренер архивирован');
        },
      },
    });
  };

  const icon =
    mode === 'edit' ? (
      <Initials
        initials="ОВ"
        color="linear-gradient(135deg,#8b5cf6,#ec4899)"
        className="size-11 text-[15px]"
      />
    ) : (
      <span className="grid size-11 place-items-center rounded-[13px] bg-primary-soft text-primary-deep dark:text-primary">
        <UserPlus className="size-5" strokeWidth={2} />
      </span>
    );

  const footerInfo = (
    <div className="flex items-center gap-3">
      {mode === 'edit' ? (
        <button
          type="button"
          onClick={archive}
          aria-label="Архивировать тренера"
          className="grid size-9 shrink-0 place-items-center rounded-full border-[0.5px] border-border bg-surface text-fg-muted transition-colors hover:border-danger hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Archive className="size-[15px]" />
        </button>
      ) : null}
      {dirty ? (
        <span className="flex items-center gap-1.5 font-medium text-warning-deep">
          <span className="size-[7px] rounded-full bg-current" />
          Несохранённые изменения
        </span>
      ) : (
        <span>{mode === 'edit' ? 'Сохранено только что' : 'Все поля можно изменить позже'}</span>
      )}
    </div>
  );

  return (
    <>
      <AdaptiveModal
        open={open}
        onOpenChange={requestClose}
        size="wide"
        icon={icon}
        title={mode === 'create' ? 'Новый тренер' : 'Редактирование тренера'}
        description={
          mode === 'create'
            ? 'Заполните карточку — тренер появится в команде'
            : 'Ольга Власова · #TR-007'
        }
        footerInfo={footerInfo}
        footerActions={
          <>
            <ModalButton variant="ghost" onClick={() => requestClose(false)}>
              Отмена
            </ModalButton>
            <ModalButton disabled={mode === 'edit' && !dirty} onClick={save}>
              {mode === 'create' ? (
                <>
                  <Plus className="size-3.5" strokeWidth={2.6} />
                  Добавить тренера
                </>
              ) : (
                'Сохранить'
              )}
            </ModalButton>
          </>
        }
      >
        <Section>Профиль</Section>
        <div className="flex items-center gap-3.5">
          <span className="relative shrink-0">
            {mode === 'edit' ? (
              <>
                <Initials
                  initials="ОВ"
                  color="linear-gradient(135deg,#8b5cf6,#ec4899)"
                  className="size-[60px] text-xl"
                />
                <span className="absolute -bottom-0.5 -right-0.5 grid size-[22px] place-items-center rounded-full border-[0.5px] border-border bg-surface text-fg-muted">
                  <Camera className="size-3" />
                </span>
              </>
            ) : (
              <span className="grid size-[60px] place-items-center rounded-full border-[1.5px] border-dashed border-border-strong bg-surface-3 text-fg-subtle">
                <Camera className="size-5" strokeWidth={1.8} />
              </span>
            )}
          </span>
          <ModalButton
            variant="ghost"
            className="h-9 px-3.5 text-[12.5px]"
            onClick={() => toast('Загрузка фото — демо')}
          >
            Загрузить фото
          </ModalButton>
        </div>

        <div className="mt-3.5">
          <FieldRow>
            <Field label="Имя">
              <ModalInput
                placeholder="Имя"
                value={state.firstName}
                onChange={(e) => set('firstName', e.target.value)}
                autoComplete="given-name"
              />
            </Field>
            <Field label="Фамилия">
              <ModalInput
                placeholder="Фамилия"
                value={state.lastName}
                onChange={(e) => set('lastName', e.target.value)}
                autoComplete="family-name"
              />
            </Field>
          </FieldRow>
        </div>
        <FieldRow>
          <Field label="Телефон">
            <ModalInput
              type="tel"
              placeholder="+7 ___ ___-__-__"
              value={state.phone}
              onChange={(e) => set('phone', e.target.value)}
              autoComplete="tel"
            />
          </Field>
          <Field label="Эл. почта">
            <ModalInput
              type="email"
              placeholder="trainer@mail.ru"
              value={state.email}
              onChange={(e) => set('email', e.target.value)}
              autoComplete="email"
            />
          </Field>
        </FieldRow>

        <Section>Специализация</Section>
        <SpecChips
          value={state.specs}
          onToggle={(v) =>
            set(
              'specs',
              state.specs.includes(v) ? state.specs.filter((s) => s !== v) : [...state.specs, v],
            )
          }
        />

        <Section>Условия работы</Section>
        <Field label="Тип занятости">
          <Segmented
            options={EMPLOYMENT}
            value={state.employment}
            onChange={(v) => set('employment', v)}
            ariaLabel="Тип занятости"
          />
        </Field>
        <FieldRow>
          <Field label="Персональная, ₽">
            <ModalInput
              inputMode="numeric"
              suffix="₽"
              placeholder="0"
              value={state.ratePersonal}
              onChange={(e) => set('ratePersonal', e.target.value)}
            />
          </Field>
          <Field label="Групповая, ₽">
            <ModalInput
              inputMode="numeric"
              suffix="₽"
              placeholder="0"
              value={state.rateGroup}
              onChange={(e) => set('rateGroup', e.target.value)}
            />
          </Field>
        </FieldRow>
        <FieldRow>
          <Field label="Комиссия зала">
            <ModalInput
              inputMode="numeric"
              suffix="%"
              placeholder="30"
              value={state.commission}
              onChange={(e) => set('commission', e.target.value)}
            />
          </Field>
          <Field label="Филиал">
            <ModalSelect value={state.branch} onChange={(e) => set('branch', e.target.value)}>
              {BRANCHES.map((b) => (
                <option key={b}>{b}</option>
              ))}
            </ModalSelect>
          </Field>
        </FieldRow>

        <Section>Доступ и статус</Section>
        <Field label="Статус">
          <ModalSelect value={state.status} onChange={(e) => set('status', e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </ModalSelect>
        </Field>
        <Field label="Заметка">
          <ModalTextarea
            placeholder="Опыт, сертификаты, особенности…"
            value={state.note}
            onChange={(e) => set('note', e.target.value)}
          />
        </Field>
      </AdaptiveModal>

      <Dialog open={guard} onOpenChange={setGuard}>
        <DialogContent
          showCloseButton={false}
          className="gap-0 overflow-hidden rounded-[18px] border-border bg-surface p-0 sm:max-w-[400px]"
        >
          <div className="flex gap-3.5 p-[22px]">
            <span className="grid size-[42px] shrink-0 place-items-center rounded-xl bg-warning-soft text-warning-deep">
              <TriangleAlert className="size-5" />
            </span>
            <div>
              <DialogTitle className="text-base font-bold tracking-[-0.3px]">
                Закрыть без сохранения?
              </DialogTitle>
              <DialogDescription className="mt-1.5 text-[13px] leading-relaxed text-fg-muted">
                Внесённые данные не сохранятся. Точно закрыть?
              </DialogDescription>
            </div>
          </div>
          <div className="flex items-center justify-between gap-2 border-t-[0.5px] border-border bg-surface-2 px-[22px] py-3.5">
            <ModalButton
              variant="text"
              className="text-danger hover:bg-danger-soft hover:text-danger"
              onClick={discard}
            >
              Не сохранять
            </ModalButton>
            <div className="flex gap-2">
              <ModalButton variant="ghost" onClick={() => setGuard(false)}>
                Остаться
              </ModalButton>
              <ModalButton
                onClick={() => {
                  setGuard(false);
                  save();
                }}
              >
                Сохранить
              </ModalButton>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
