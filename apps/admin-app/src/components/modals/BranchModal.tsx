import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { Building2 } from '@/components/icons';
import { branchesData } from '@/mocks/branches';
import type { BranchStatus } from '@/features/branches/types';
import { AdaptiveModal } from './AdaptiveModal';
import { Field, FieldRow, IconChip, ModalButton, ModalInput, ModalSelect } from './fields';

const MANAGERS = ['Не назначен', 'Ольга Воронина', 'Роман Ким', 'Сергей Белов'];
const STATUS_LABELS = ['Скоро открытие', 'Активен', 'На паузе'];
const STATUS_TO_LABEL: Record<BranchStatus, string> = {
  soon: 'Скоро открытие',
  active: 'Активен',
  paused: 'На паузе',
};

const SWATCHES = [
  'linear-gradient(135deg,#2dd4a4,#0f9b76)',
  'linear-gradient(135deg,#6366f1,#818cf8)',
  'linear-gradient(135deg,#f59e0b,#fbbf24)',
  'linear-gradient(135deg,#f43f5e,#fb7185)',
  'linear-gradient(135deg,#0ea5e9,#38bdf8)',
];

interface FormState {
  name: string;
  city: string;
  metro: string;
  addr: string;
  phone: string;
  manager: string;
  status: string;
  swatch: number;
}

const CREATE_STATE: FormState = {
  name: '',
  city: 'Москва',
  metro: '',
  addr: '',
  phone: '',
  manager: 'Не назначен',
  status: 'Скоро открытие',
  swatch: 0,
};

export function BranchModal({
  open,
  onOpenChange,
  payload,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payload?: { branchId?: string };
}) {
  const branch = payload?.branchId
    ? branchesData.branches.find((b) => b.id === payload.branchId)
    : undefined;
  const isEdit = !!branch;
  const [state, setState] = useState<FormState>(CREATE_STATE);

  useEffect(() => {
    if (!open) return;
    if (branch) {
      const swatch = SWATCHES.indexOf(branch.gradient);
      setState({
        name: branch.name,
        city: branch.city,
        metro: branch.metro,
        addr: branch.addr,
        phone: branch.phone,
        manager: branch.manager?.name ?? 'Не назначен',
        status: STATUS_TO_LABEL[branch.status],
        swatch: swatch >= 0 ? swatch : 0,
      });
    } else {
      setState(CREATE_STATE);
    }
  }, [open, branch]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setState((s) => ({ ...s, [k]: v }));

  const submit = () => {
    toast.success(isEdit ? 'Изменения сохранены' : 'Филиал создан');
    onOpenChange(false);
  };

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip tone="accent" icon={Building2} />}
      title={isEdit ? 'Редактировать филиал' : 'Новый филиал'}
      description={isEdit && branch ? `${branch.name} · #${branch.code}` : 'Заполните данные зала'}
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton onClick={submit}>{isEdit ? 'Сохранить' : 'Создать филиал'}</ModalButton>
        </>
      }
    >
      <Field label="Название">
        <ModalInput
          value={state.name}
          placeholder="Например, Арбат"
          onChange={(e) => set('name', e.target.value)}
        />
      </Field>
      <FieldRow>
        <Field label="Город">
          <ModalInput value={state.city} onChange={(e) => set('city', e.target.value)} />
        </Field>
        <Field label="Метро">
          <ModalInput
            value={state.metro}
            placeholder="Станция"
            onChange={(e) => set('metro', e.target.value)}
          />
        </Field>
      </FieldRow>
      <Field label="Адрес">
        <ModalInput
          value={state.addr}
          placeholder="Улица, дом"
          onChange={(e) => set('addr', e.target.value)}
        />
      </Field>
      <FieldRow>
        <Field label="Телефон">
          <ModalInput
            type="tel"
            value={state.phone}
            placeholder="+7 ___ ___-__-__"
            onChange={(e) => set('phone', e.target.value)}
          />
        </Field>
        <Field label="Управляющий">
          <ModalSelect value={state.manager} onChange={(e) => set('manager', e.target.value)}>
            {MANAGERS.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </ModalSelect>
        </Field>
      </FieldRow>
      <FieldRow>
        <Field label="Статус">
          <ModalSelect value={state.status} onChange={(e) => set('status', e.target.value)}>
            {STATUS_LABELS.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </ModalSelect>
        </Field>
        <Field label="Цвет на карте">
          <div className="flex flex-wrap gap-2 pt-0.5">
            {SWATCHES.map((g, i) => {
              const active = state.swatch === i;
              return (
                <button
                  key={g}
                  type="button"
                  aria-label={`Цвет ${i + 1}`}
                  aria-pressed={active}
                  onClick={() => set('swatch', i)}
                  style={{ background: g }}
                  className={cn(
                    'size-[30px] rounded-[9px] transition-transform focus-visible:outline-none active:scale-95',
                    active && 'ring-2 ring-fg ring-offset-2 ring-offset-surface',
                  )}
                />
              );
            })}
          </div>
        </Field>
      </FieldRow>
    </AdaptiveModal>
  );
}
