import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Initials } from '@/components/ui/initials';
import { Segmented } from '@/components/ui/Segmented';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Camera, Mail, Phone, Trash2, TriangleAlert } from '@/components/icons';
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
  birthday: string;
  gender: 'f' | 'm';
  phone: string;
  email: string;
  plan: string;
  trainer: string;
  branch: string;
  status: string;
  note: string;
}

const INITIAL: FormState = {
  firstName: 'Карина',
  lastName: 'Левчук',
  birthday: '14.03.1994',
  gender: 'f',
  phone: '+7 916 408-22-71',
  email: 'karina.l@mail.ru',
  plan: '«12 месяцев» · безлимит',
  trainer: 'Ольга Власова',
  branch: 'Тверская',
  status: 'Активен',
  note: 'Предпочитает утренние тренировки. Восстанавливается после травмы колена — без приседаний с весом.',
};

const GENDER = [
  { value: 'f', label: 'Женский' },
  { value: 'm', label: 'Мужской' },
] satisfies { value: FormState['gender']; label: string }[];

const PLANS = [
  '«12 месяцев» · безлимит',
  '«6 месяцев» · безлимит',
  '«3 месяца» · 12 визитов',
  'Разовые посещения',
];
const TRAINERS = ['Ольга Власова', 'Артём Поляков', 'Вадим Дроздов', 'Без тренера'];
const BRANCHES = ['Тверская', 'Сокольники', 'Новокосино'];
const STATUSES = ['Активен', 'Заморожен', 'Гость'];

export function EditClientModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { open: openModal } = useModals();
  const [state, setState] = useState<FormState>(INITIAL);
  const [guard, setGuard] = useState(false);

  useEffect(() => {
    if (open) {
      setState(INITIAL);
      setGuard(false);
    }
  }, [open]);

  const dirty = useMemo(() => JSON.stringify(state) !== JSON.stringify(INITIAL), [state]);
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setState((s) => ({ ...s, [k]: v }));

  const requestClose = (next: boolean) => {
    if (next) return;
    if (dirty) setGuard(true);
    else onOpenChange(false);
  };

  const save = () => {
    toast.success('Изменения сохранены');
    onOpenChange(false);
  };

  const remove = () => {
    onOpenChange(false);
    openModal('confirm', {
      confirm: {
        title: 'Удалить клиента?',
        message: (
          <>
            «{INITIAL.firstName} {INITIAL.lastName}» и вся история посещений будут удалены без
            возможности восстановления.
          </>
        ),
        tone: 'danger',
        confirmLabel: 'Удалить',
        requireText: 'УДАЛИТЬ',
        onConfirm: () => {
          toast.success('Клиент удалён');
        },
      },
    });
  };

  return (
    <>
      <AdaptiveModal
        open={open}
        onOpenChange={requestClose}
        size="wide"
        icon={
          <Initials
            initials="КЛ"
            color="linear-gradient(135deg,#6366f1,#818cf8)"
            className="size-11 text-[15px]"
          />
        }
        title="Редактирование клиента"
        description="Карина Левчук · #CL-00871"
        footerInfo={
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="Удалить клиента"
              onClick={remove}
              className="grid size-9 place-items-center rounded-full border-[0.5px] border-border bg-surface text-fg-muted transition-colors hover:border-danger hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Trash2 className="size-[15px]" />
            </button>
            {dirty ? (
              <span className="flex items-center gap-1.5 font-medium text-warning-deep">
                <span className="size-[7px] rounded-full bg-current" />
                Несохранённые изменения
              </span>
            ) : (
              <span>Сохранено только что</span>
            )}
          </div>
        }
        footerActions={
          <>
            <ModalButton variant="ghost" onClick={() => requestClose(false)}>
              Отмена
            </ModalButton>
            <ModalButton disabled={!dirty} onClick={save}>
              Сохранить
            </ModalButton>
          </>
        }
      >
        <Section>Профиль</Section>
        <div className="flex items-center gap-3.5">
          <span className="relative shrink-0">
            <Initials
              initials="КЛ"
              color="linear-gradient(135deg,#6366f1,#818cf8)"
              className="size-[60px] text-xl"
            />
            <span className="absolute -bottom-0.5 -right-0.5 grid size-[22px] place-items-center rounded-full border-[0.5px] border-border bg-surface text-fg-muted">
              <Camera className="size-3" />
            </span>
          </span>
          <div className="flex gap-2">
            <ModalButton
              variant="ghost"
              className="h-9 px-3.5 text-[12.5px]"
              onClick={() => toast('Загрузка фото — демо')}
            >
              Загрузить фото
            </ModalButton>
            <ModalButton
              variant="ghost"
              className="h-9 px-3.5 text-[12.5px]"
              onClick={() => toast('Фото удалено')}
            >
              Удалить
            </ModalButton>
          </div>
        </div>

        <div className="mt-3.5">
          <FieldRow>
            <Field label="Имя">
              <ModalInput
                value={state.firstName}
                onChange={(e) => set('firstName', e.target.value)}
              />
            </Field>
            <Field label="Фамилия">
              <ModalInput
                value={state.lastName}
                onChange={(e) => set('lastName', e.target.value)}
              />
            </Field>
          </FieldRow>
        </div>
        <FieldRow>
          <Field label="Дата рождения">
            <ModalInput value={state.birthday} onChange={(e) => set('birthday', e.target.value)} />
          </Field>
          <Field label="Пол">
            <Segmented
              options={GENDER}
              value={state.gender}
              onChange={(v) => set('gender', v)}
              ariaLabel="Пол"
            />
          </Field>
        </FieldRow>

        <Section>Контакты</Section>
        <Field label="Телефон">
          <ModalInput
            icon={Phone}
            type="tel"
            value={state.phone}
            onChange={(e) => set('phone', e.target.value)}
          />
        </Field>
        <Field label="Эл. почта">
          <ModalInput
            icon={Mail}
            type="email"
            value={state.email}
            onChange={(e) => set('email', e.target.value)}
          />
        </Field>

        <Section>Абонемент и тренер</Section>
        <FieldRow>
          <Field label="Тариф">
            <ModalSelect value={state.plan} onChange={(e) => set('plan', e.target.value)}>
              {PLANS.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </ModalSelect>
          </Field>
          <Field label="Персональный тренер">
            <ModalSelect value={state.trainer} onChange={(e) => set('trainer', e.target.value)}>
              {TRAINERS.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </ModalSelect>
          </Field>
        </FieldRow>
        <FieldRow>
          <Field label="Филиал">
            <ModalSelect value={state.branch} onChange={(e) => set('branch', e.target.value)}>
              {BRANCHES.map((b) => (
                <option key={b}>{b}</option>
              ))}
            </ModalSelect>
          </Field>
          <Field label="Статус">
            <ModalSelect value={state.status} onChange={(e) => set('status', e.target.value)}>
              {STATUSES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </ModalSelect>
          </Field>
        </FieldRow>

        <Section>Заметка для администраторов</Section>
        <Field>
          <ModalTextarea
            placeholder="Аллергии, пожелания, особенности…"
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
                В карточке есть несохранённые изменения. Если закрыть сейчас — они будут потеряны.
              </DialogDescription>
            </div>
          </div>
          <div className="flex items-center justify-between gap-2 border-t-[0.5px] border-border bg-surface-2 px-[22px] py-3.5">
            <ModalButton
              variant="text"
              className="text-danger hover:bg-danger-soft hover:text-danger"
              onClick={() => {
                setGuard(false);
                onOpenChange(false);
              }}
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
