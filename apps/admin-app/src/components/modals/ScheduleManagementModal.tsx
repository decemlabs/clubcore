/**
 * ScheduleManagementModal — owner-only modal for publishing slots, creating
 * recurring templates, and creating time-off blocks (Phase 102-01 SCH-01).
 *
 * Single AdaptiveModal with three ChipGroup tabs:
 *   slot      → POST /api/v1/trainer-slots
 *   template  → POST /api/v1/recurring-templates
 *   timeoff   → POST /api/v1/time-off (+ force=true conflict-override flow)
 *
 * OWNER_ONLY — if reception opens this somehow, returns null (can() gate).
 * The FAB in SchedulePage only renders for owner (Plan 102-03 will wire the FAB).
 *
 * T-102-FORCE: force=true only after explicit second user action (danger button).
 */
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { CalendarPlus, Loader2, TriangleAlert } from '@/components/icons';
import { can } from '@/shared/session/can';
import type { Role } from '@/shared/session/types';
import { AdaptiveModal } from './AdaptiveModal';
import {
  Callout,
  ChipGroup,
  Field,
  FieldRow,
  IconChip,
  ModalButton,
  ModalInput,
  ModalSelect,
  ModalTextarea,
  Section,
  StatRow,
} from './fields';
import {
  usePublishSlot,
  useCreateTemplate,
  useCreateTimeOff,
  ApiError,
} from '@/features/schedule/api';
import { useTrainers } from '@/features/trainers/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Tab = 'slot' | 'template' | 'timeoff';

interface ConflictData {
  conflictingSlotIds: string[];
  conflictingBookingIds: string[];
}

// ---------------------------------------------------------------------------
// Error copy maps (UI-SPEC Copywriting Contract)
// ---------------------------------------------------------------------------

const SLOT_ERROR_COPY: Record<string, string> = {
  slot_overlap: 'Слот пересекается с существующим слотом тренера',
  slot_too_close: 'Слот слишком близко к другому слоту (менее минимального интервала)',
  slot_in_past: 'Нельзя публиковать слот в прошлом',
  trainer_inactive: 'Тренер неактивен — сначала активируйте его',
};

// ---------------------------------------------------------------------------
// Day-of-week options (Monday-first per UI-SPEC §1.4)
// ---------------------------------------------------------------------------

const DAY_OPTIONS = [
  { value: '1', label: 'Понедельник' },
  { value: '2', label: 'Вторник' },
  { value: '3', label: 'Среда' },
  { value: '4', label: 'Четверг' },
  { value: '5', label: 'Пятница' },
  { value: '6', label: 'Суббота' },
  { value: '0', label: 'Воскресенье' },
];

// ---------------------------------------------------------------------------
// Helper — Russian plural
// ---------------------------------------------------------------------------

function pluralSlot(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 19) return `${n} слотов`;
  if (mod10 === 1) return `${n} слот`;
  if (mod10 >= 2 && mod10 <= 4) return `${n} слота`;
  return `${n} слотов`;
}

function pluralBooking(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 19) return `${n} бронирований`;
  if (mod10 === 1) return `${n} бронирование`;
  if (mod10 >= 2 && mod10 <= 4) return `${n} бронирования`;
  return `${n} бронирований`;
}

// ---------------------------------------------------------------------------
// Sub-components — SlotTab
// ---------------------------------------------------------------------------

interface SlotTabProps {
  trainers: { id: string; fullName: string }[];
  onSuccess: () => void;
  isPending: boolean;
}

function SlotTab({ trainers, onSuccess, isPending }: SlotTabProps) {
  const publishSlot = usePublishSlot();

  const [trainerId, setTrainerId] = useState('');
  const [date, setDate] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [apiError, setApiError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const isFormValid = trainerId && date && startTime && endTime;

  const handleSubmit = async () => {
    setApiError(null);
    setValidationError(null);

    // Client-side validation
    if (!trainerId) {
      setValidationError('Выберите тренера');
      return;
    }
    if (!date) {
      setValidationError('Дата не может быть в прошлом');
      return;
    }
    if (!startTime || !endTime) {
      setValidationError('Укажите время начала и конца');
      return;
    }
    if (endTime <= startTime) {
      setValidationError('Конец должен быть позже начала');
      return;
    }

    const startISO = `${date}T${startTime}:00`;
    const endISO = `${date}T${endTime}:00`;

    try {
      await publishSlot.mutateAsync({ trainerId, startTime: startISO, endTime: endISO });
      onSuccess();
    } catch (err) {
      if (err instanceof ApiError) {
        const copy = SLOT_ERROR_COPY[err.code] ?? err.message;
        setApiError(copy);
      }
    }
  };

  const pending = isPending || publishSlot.isPending;

  return (
    <>
      <Section>Тренер</Section>
      <Field label="Тренер">
        <ModalSelect value={trainerId} onChange={(e) => setTrainerId(e.target.value)}>
          <option value="">Выберите тренера</option>
          {trainers.map((t) => (
            <option key={t.id} value={t.id}>
              {t.fullName}
            </option>
          ))}
        </ModalSelect>
      </Field>

      <Section>Дата и время</Section>
      <Field label="Дата">
        <ModalInput
          type="date"
          value={date}
          min={new Date().toISOString().split('T')[0]}
          onChange={(e) => setDate(e.target.value)}
        />
      </Field>
      <FieldRow>
        <Field label="Начало">
          <ModalInput
            type="time"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
          />
        </Field>
        <Field label="Конец">
          <ModalInput type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
        </Field>
      </FieldRow>

      {validationError && (
        <Callout tone="danger" icon={TriangleAlert}>
          {validationError}
        </Callout>
      )}
      {apiError && (
        <Callout tone="danger" icon={TriangleAlert}>
          {apiError}
        </Callout>
      )}

      {/* Footer injected via parent — slot tab passes its handlers */}
      <div className="mt-4 flex justify-end gap-2">
        <ModalButton
          variant="primary"
          disabled={!isFormValid || pending}
          onClick={() => void handleSubmit()}
        >
          {pending ? <Loader2 className="size-4 animate-spin" /> : null}
          Опубликовать
        </ModalButton>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Sub-components — TemplateTab
// ---------------------------------------------------------------------------

interface TemplateTabProps {
  trainers: { id: string; fullName: string }[];
  onSuccess: () => void;
  isPending: boolean;
}

function TemplateTab({ trainers, onSuccess, isPending }: TemplateTabProps) {
  const createTemplate = useCreateTemplate();

  const [trainerId, setTrainerId] = useState('');
  const [dayOfWeek, setDayOfWeek] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [validFrom, setValidFrom] = useState('');
  const [validUntil, setValidUntil] = useState('');
  const [apiError, setApiError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const isFormValid = trainerId && dayOfWeek !== '' && startTime && endTime && validFrom;

  const handleSubmit = async () => {
    setApiError(null);
    setValidationError(null);

    if (!trainerId) {
      setValidationError('Выберите тренера');
      return;
    }
    if (dayOfWeek === '') {
      setValidationError('Выберите день недели');
      return;
    }
    if (!startTime || !endTime) {
      setValidationError('Укажите время');
      return;
    }
    if (endTime <= startTime) {
      setValidationError('Конец должен быть позже начала');
      return;
    }
    if (!validFrom) {
      setValidationError('Укажите дату начала действия');
      return;
    }
    if (validUntil && validUntil <= validFrom) {
      setValidationError('Дата окончания должна быть позже даты начала');
      return;
    }

    try {
      await createTemplate.mutateAsync({
        trainerId,
        dayOfWeek: parseInt(dayOfWeek, 10),
        startTime,
        endTime,
        validFrom,
        validUntil: validUntil || undefined,
      });
      onSuccess();
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(err.message);
      }
    }
  };

  const pending = isPending || createTemplate.isPending;

  return (
    <>
      <Section>Тренер</Section>
      <Field label="Тренер">
        <ModalSelect value={trainerId} onChange={(e) => setTrainerId(e.target.value)}>
          <option value="">Выберите тренера</option>
          {trainers.map((t) => (
            <option key={t.id} value={t.id}>
              {t.fullName}
            </option>
          ))}
        </ModalSelect>
      </Field>

      <Section>Расписание</Section>
      <Field label="День недели">
        <ModalSelect value={dayOfWeek} onChange={(e) => setDayOfWeek(e.target.value)}>
          <option value="">Выберите день</option>
          {DAY_OPTIONS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </ModalSelect>
      </Field>
      <FieldRow>
        <Field label="Начало">
          <ModalInput
            type="time"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
          />
        </Field>
        <Field label="Конец">
          <ModalInput type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
        </Field>
      </FieldRow>

      <Section>Период действия</Section>
      <FieldRow>
        <Field label="Действует с">
          <ModalInput
            type="date"
            value={validFrom}
            min={new Date().toISOString().split('T')[0]}
            onChange={(e) => setValidFrom(e.target.value)}
          />
        </Field>
        <Field label="Действует до" optional hint="Оставьте пустым — шаблон бессрочный">
          <ModalInput
            type="date"
            value={validUntil}
            onChange={(e) => setValidUntil(e.target.value)}
          />
        </Field>
      </FieldRow>

      {validationError && (
        <Callout tone="danger" icon={TriangleAlert}>
          {validationError}
        </Callout>
      )}
      {apiError && (
        <Callout tone="danger" icon={TriangleAlert}>
          {apiError}
        </Callout>
      )}

      <div className="mt-4 flex justify-end gap-2">
        <ModalButton
          variant="primary"
          disabled={!isFormValid || pending}
          onClick={() => void handleSubmit()}
        >
          {pending ? <Loader2 className="size-4 animate-spin" /> : null}
          Создать шаблон
        </ModalButton>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Sub-components — TimeOffTab
// ---------------------------------------------------------------------------

interface TimeOffTabProps {
  trainers: { id: string; fullName: string }[];
  onSuccess: () => void;
  isPending: boolean;
}

function TimeOffTab({ trainers, onSuccess, isPending }: TimeOffTabProps) {
  const createTimeOff = useCreateTimeOff();

  const [trainerId, setTrainerId] = useState('');
  const [blockStart, setBlockStart] = useState('');
  const [blockEnd, setBlockEnd] = useState('');
  const [reason, setReason] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const [forceError, setForceError] = useState<string | null>(null);

  // T-102-FORCE: conflict state set on 409 time_off_booked_conflict
  const [conflictData, setConflictData] = useState<ConflictData | null>(null);

  const isFormValid = trainerId && blockStart && blockEnd;

  const buildBody = () => ({
    trainerId,
    blockStart,
    blockEnd,
    reason: reason || undefined,
  });

  const handleSubmit = async () => {
    setValidationError(null);
    setForceError(null);

    if (!trainerId) {
      setValidationError('Выберите тренера');
      return;
    }
    if (!blockStart) {
      setValidationError('Укажите начало блокировки');
      return;
    }
    if (!blockEnd) {
      setValidationError('Укажите конец блокировки');
      return;
    }
    if (blockEnd <= blockStart) {
      setValidationError('Конец должен быть позже начала');
      return;
    }

    try {
      await createTimeOff.mutateAsync({ body: buildBody() });
      // toast owned by useCreateTimeOff.onSuccess (CR-02: avoid double-toast)
      onSuccess();
    } catch (err) {
      if (err instanceof ApiError && err.code === 'time_off_booked_conflict') {
        // T-102-FORCE: switch to conflict state — modal stays open
        const data = (err as unknown as { data: ConflictData }).data;
        setConflictData(data ?? { conflictingSlotIds: [], conflictingBookingIds: [] });
      } else if (err instanceof ApiError) {
        setValidationError(err.message);
      }
    }
  };

  const handleForce = async () => {
    setForceError(null);
    try {
      await createTimeOff.mutateAsync({ body: buildBody(), force: true });
      const m = conflictData?.conflictingBookingIds.length ?? 0;
      toast.success('Период заблокирован', { description: `Отменено бронирований: ${m}` });
      onSuccess();
    } catch (err) {
      if (err instanceof ApiError) {
        setForceError(err.message ?? 'Не удалось применить блокировку. Попробуйте ещё раз.');
      } else {
        setForceError('Не удалось применить блокировку. Попробуйте ещё раз.');
      }
    }
  };

  const pending = isPending || createTimeOff.isPending;

  // Conflict state (Surface 2)
  if (conflictData) {
    const n = conflictData.conflictingSlotIds.length;
    const m = conflictData.conflictingBookingIds.length;

    return (
      <>
        <Callout tone="danger" icon={TriangleAlert}>
          <p>
            Найдены конфликты: {pluralSlot(n)} и {pluralBooking(m)}
          </p>
          <p className="mt-1">Подтверждение заблокирует эти слоты и отменит все связанные брони.</p>
        </Callout>

        {n > 0 && <StatRow label="Блокируемые слоты" value={`${n} шт.`} />}
        {m > 0 && <StatRow label="Отменяемые брони" value={`${m} шт.`} />}

        {forceError && (
          <Callout tone="danger" icon={TriangleAlert}>
            {forceError}
          </Callout>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <ModalButton variant="ghost" disabled={pending} onClick={() => setConflictData(null)}>
            Назад
          </ModalButton>
          <ModalButton variant="danger" disabled={pending} onClick={() => void handleForce()}>
            {pending ? <Loader2 className="size-4 animate-spin" /> : null}
            Заблокировать принудительно
          </ModalButton>
        </div>
      </>
    );
  }

  // Normal form
  return (
    <>
      <Section>Тренер</Section>
      <Field label="Тренер">
        <ModalSelect value={trainerId} onChange={(e) => setTrainerId(e.target.value)}>
          <option value="">Выберите тренера</option>
          {trainers.map((t) => (
            <option key={t.id} value={t.id}>
              {t.fullName}
            </option>
          ))}
        </ModalSelect>
      </Field>

      <Section>Период блокировки</Section>
      <FieldRow>
        <Field label="С">
          <ModalInput
            type="datetime-local"
            value={blockStart}
            onChange={(e) => setBlockStart(e.target.value)}
          />
        </Field>
        <Field label="По">
          <ModalInput
            type="datetime-local"
            value={blockEnd}
            onChange={(e) => setBlockEnd(e.target.value)}
          />
        </Field>
      </FieldRow>

      <Section>Причина</Section>
      <Field label="Причина" optional>
        <ModalTextarea
          placeholder="Болезнь, отпуск…"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </Field>

      {validationError && (
        <Callout tone="danger" icon={TriangleAlert}>
          {validationError}
        </Callout>
      )}

      <div className="mt-4 flex justify-end gap-2">
        <ModalButton
          variant="primary"
          disabled={!isFormValid || pending}
          onClick={() => void handleSubmit()}
        >
          {pending ? <Loader2 className="size-4 animate-spin" /> : null}
          Заблокировать
        </ModalButton>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Main modal
// ---------------------------------------------------------------------------

export interface ScheduleManagementModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Role is passed from parent (via useSession) for can() gate. */
  role: Role;
}

export function ScheduleManagementModal({
  open,
  onOpenChange,
  role,
}: ScheduleManagementModalProps) {
  // All hooks MUST be called unconditionally (React rules of hooks)
  const [tab, setTab] = useState<Tab>('slot');
  const [isPending] = useState(false); // individual tabs manage their own pending

  // Trainer data for all selects.
  // Guard: pre-102-02 useTrainers() returns TrainersPageData (no items field);
  // post-102-02 returns { items: TrainerData[] }. Read defensively. (D-102-01-TRAINERSHAPE)
  const trainersQuery = useTrainers();
  const trainers: { id: string; fullName: string }[] =
    (trainersQuery.data as unknown as { items?: { id: string; fullName: string }[] } | undefined)
      ?.items ?? [];

  // Reset on open (pattern from BookModal.tsx)
  useEffect(() => {
    if (open) {
      setTab('slot');
    }
  }, [open]);

  // OWNER_ONLY gate — defensive early return after hooks (T-102-IDOR)
  if (!can(role, 'create', 'schedule-slots')) return null;

  const handleClose = () => onOpenChange(false);

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip tone="accent" icon={CalendarPlus} />}
      title="Управление расписанием"
      description="Слот · Шаблон · Блокировка"
      footerActions={
        <ModalButton variant="ghost" disabled={isPending} onClick={handleClose}>
          Отмена
        </ModalButton>
      }
    >
      <ChipGroup
        value={tab}
        onChange={(v) => setTab(v as Tab)}
        options={[
          { value: 'slot', label: 'Слот' },
          { value: 'template', label: 'Шаблон' },
          { value: 'timeoff', label: 'Блокировка' },
        ]}
      />

      <div className="mt-4">
        {tab === 'slot' && (
          <SlotTab trainers={trainers} onSuccess={handleClose} isPending={isPending} />
        )}
        {tab === 'template' && (
          <TemplateTab trainers={trainers} onSuccess={handleClose} isPending={isPending} />
        )}
        {tab === 'timeoff' && (
          <TimeOffTab trainers={trainers} onSuccess={handleClose} isPending={isPending} />
        )}
      </div>
    </AdaptiveModal>
  );
}
