# Phase 102: Schedule + Trainers — Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 12 new/modified files
**Analogs found:** 12 / 12

---

## Booking "Complete" Mechanism — Confirmed

`POST /api/v1/pt-sessions` body `{ptPackageId, trainerId, performedAt, bookingId?}` +
`Idempotency-Key`. When `bookingId` is supplied the service atomically marks the booking
`completed` (Phase 38 PKG-04/05). There is **no** `/bookings/{id}/complete` endpoint.

Planner action: wire "complete" to `POST /api/v1/pt-sessions { ptPackageId, trainerId,
performedAt: now, bookingId }`. Deferred to Phase 103 per CONTEXT.md — place a
`// TODO Phase 103: wire complete to POST /pt-sessions` comment in `BookingDetailModal`.

---

## can() Resource Strings — Verified

From `apps/admin-app/src/shared/session/can.ts` (authoritative):

| Action | Resource | Who |
|--------|----------|-----|
| `create`/`edit`/`delete`/`cancel` | `'schedule-slots'` | owner-only |
| `view`/`list` | `'schedule-slots'` | reception+owner (not in OWNER_ONLY) |
| `create`/`cancel`/`view`/`list` | `'bookings'` | reception+owner (not in OWNER_ONLY) |
| `create`/`edit`/`delete` | `'trainers'` | owner-only |
| `view` | `'trainers'` | reception+owner |
| `view`/`list`/`create`/`edit`/`refund` | `'payroll'` | owner-only |
| `view`/`create` | `'compensation'` | owner-only |

Use these exact strings in all `can(role, action, resource)` calls for Phase 102.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `features/schedule/api.ts` (replace) | service | request-response CRUD | `features/memberships/api.ts` | exact |
| `features/schedule/schemas.ts` (new) | model/schema | transform | `features/memberships/schemas.ts` | exact |
| `features/schedule/keys.ts` (new) | utility | — | `features/memberships/keys.ts` | exact |
| `features/bookings/api.ts` (new) | service | request-response CRUD | `features/memberships/api.ts` | exact |
| `features/bookings/schemas.ts` (new) | model/schema | transform | `features/memberships/schemas.ts` | exact |
| `features/bookings/keys.ts` (new) | utility | — | `features/memberships/keys.ts` | exact |
| `features/trainers/api.ts` (replace) | service | request-response CRUD | `features/clients/api.ts` | exact |
| `features/trainers/schemas.ts` (new) | model/schema | transform | `features/memberships/schemas.ts` | exact |
| `features/payroll/api.ts` (new) | service | request-response CRUD | `features/memberships/api.ts` | exact |
| `features/payroll/schemas.ts` (new) | model/schema | transform | `features/memberships/schemas.ts` | exact |
| `components/modals/ScheduleManagementModal.tsx` (new) | component | request-response | `components/modals/TrainerFormModal.tsx` + `BookModal.tsx` | role-match |
| `components/modals/BookingModal.tsx` (new) | component | request-response | `components/modals/BookModal.tsx` | exact |

---

## Pattern Assignments

### `features/schedule/api.ts` (service, request-response CRUD)

**Analog:** `apps/admin-app/src/features/memberships/api.ts`

**Imports pattern** (memberships/api.ts lines 23–36):
```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { staffRequest, ApiError } from '@/api/client';
import { scheduleKeys } from './keys';
import {
  TrainerSlotSchema,
  TrainerSlotListResponseSchema,
  RecurringTemplateSchema,
  TimeOffSchema,
  type TrainerSlotData,
  type PublishSlotInput,
  type CancelSlotInput,
  type CreateTemplateInput,
  type CreateTimeOffInput,
} from './schemas';
```

**Query pattern — week slots** (model after memberships/api.ts lines 43–54):
```typescript
export function useTrainerSlots(params: { trainerId?: string; fromTime: string; toTime: string }) {
  return useQuery({
    queryKey: scheduleKeys.week(params),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/trainer-slots', { query: params });
      return TrainerSlotListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}
```

**Mutation with Idempotency-Key** (model after memberships/api.ts lines 79–103):
```typescript
export function usePublishSlot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PublishSlotInput) => {
      // crypto.randomUUID() called at submit time — fresh key per attempt
      const raw = await staffRequest('post', '/api/v1/trainer-slots', {
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      });
      return TrainerSlotSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: () => {
      toast.success('Слот опубликован');
      void qc.invalidateQueries({ queryKey: scheduleKeys.all });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
    },
  });
}
```

**Cancel slot mutation** (model after memberships/api.ts lines 303–339):
```typescript
export function useCancelSlot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ slotId, body }: { slotId: string; body: CancelSlotInput }) => {
      await staffRequest('patch', '/api/v1/trainer-slots/{slot_id}/cancel', {
        params: { slot_id: slotId },
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      });
    },
    onSuccess: () => {
      toast.success('Слот отменён');
      void qc.invalidateQueries({ queryKey: scheduleKeys.all });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
    },
  });
}
// Re-export for page/modal layers (ESLint import-boundary)
export { ApiError };
```

---

### `features/schedule/schemas.ts` (model/schema, transform)

**Analog:** `apps/admin-app/src/features/memberships/schemas.ts`

**Pattern** (memberships/schemas.ts lines 13–62):
```typescript
import { z } from 'zod';

// Wire shapes mirror camelCase Pydantic aliases

export const TrainerSlotSchema = z.object({
  id: z.string(),
  trainerId: z.string(),
  startTime: z.string(),
  endTime: z.string(),
  status: z.enum(['active', 'cancelled', 'booked']),
  createdAt: z.string(),
});
export type TrainerSlotData = z.infer<typeof TrainerSlotSchema>;

export const TrainerSlotListResponseSchema = z.object({
  data: z.object({
    items: z.array(TrainerSlotSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

export const RecurringTemplateSchema = z.object({
  id: z.string(),
  trainerId: z.string(),
  dayOfWeek: z.number().int().min(0).max(6),
  startTime: z.string(),
  endTime: z.string(),
  validFrom: z.string(),
  validUntil: z.string().nullable().optional(),
  isActive: z.boolean(),
});
export type RecurringTemplateData = z.infer<typeof RecurringTemplateSchema>;

export const TimeOffSchema = z.object({
  id: z.string(),
  trainerId: z.string(),
  blockStart: z.string(),
  blockEnd: z.string(),
  reason: z.string().nullable().optional(),
  createdAt: z.string(),
});
export type TimeOffData = z.infer<typeof TimeOffSchema>;

// Mutation input schemas
export const PublishSlotSchema = z.object({
  trainerId: z.string().min(1, 'Выберите тренера'),
  startTime: z.string().min(1),
  endTime: z.string().min(1),
});
export type PublishSlotInput = z.infer<typeof PublishSlotSchema>;

export const CancelSlotSchema = z.object({
  cancelReason: z.string().min(1).max(200),
});
export type CancelSlotInput = z.infer<typeof CancelSlotSchema>;

export const CreateTemplateSchema = z.object({
  trainerId: z.string().min(1, 'Выберите тренера'),
  dayOfWeek: z.number().int().min(0).max(6),
  startTime: z.string().min(1),
  endTime: z.string().min(1),
  validFrom: z.string().min(1),
  validUntil: z.string().optional(),
});
export type CreateTemplateInput = z.infer<typeof CreateTemplateSchema>;

export const CreateTimeOffSchema = z.object({
  trainerId: z.string().min(1, 'Выберите тренера'),
  blockStart: z.string().min(1),
  blockEnd: z.string().min(1),
  reason: z.string().optional(),
});
export type CreateTimeOffInput = z.infer<typeof CreateTimeOffSchema>;
```

---

### `features/schedule/keys.ts` (utility)

**Analog:** `apps/admin-app/src/features/memberships/keys.ts`

**Pattern** (memberships/keys.ts lines 22–29):
```typescript
export const scheduleKeys = {
  all: ['schedule'] as const,
  slots: () => [...scheduleKeys.all, 'slots'] as const,
  week: (params: { trainerId?: string; fromTime: string; toTime: string }) =>
    [...scheduleKeys.slots(), params] as const,
  templates: () => [...scheduleKeys.all, 'templates'] as const,
  timeOff: () => [...scheduleKeys.all, 'time-off'] as const,
} as const;
```

---

### `features/bookings/api.ts` (service, request-response CRUD)

**Analog:** `apps/admin-app/src/features/memberships/api.ts`

**Key factory** (model after clients/api.ts lines 37–43):
```typescript
export const bookingsKeys = {
  all: ['bookings'] as const,
  lists: () => [...bookingsKeys.all, 'list'] as const,
  list: (filter: BookingsListQuery) => [...bookingsKeys.lists(), filter] as const,
  detail: (id: string) => [...bookingsKeys.all, 'detail', id] as const,
  byTrainer: (trainerId: string, date: string) =>
    [...bookingsKeys.all, 'byTrainer', trainerId, date] as const,
};
```

**Create booking mutation** (model after memberships/api.ts lines 79–103):
```typescript
export function useCreateBooking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: BookingCreateInput) => {
      const raw = await staffRequest('post', '/api/v1/bookings', {
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      });
      return BookingSchema.parse((raw as { data: unknown }).data);
    },
    // NOTE: onError is handled inline in BookingModal (caller inspects ApiError.code)
    // for race-conflict 409 display — do NOT toast here for slot_already_booked
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({ queryKey: scheduleKeys.all });
      void qc.invalidateQueries({ queryKey: bookingsKeys.lists() });
    },
  });
}
```

**Cancel booking mutation** (model after memberships/api.ts lines 303–339):
```typescript
export function useCancelBooking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ bookingId, body }: { bookingId: string; body: CancelBookingInput }) => {
      await staffRequest('post', '/api/v1/bookings/{booking_id}/cancel', {
        params: { booking_id: bookingId },
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      });
    },
    onSuccess: () => {
      toast.success('Бронирование отменено');
      void qc.invalidateQueries({ queryKey: scheduleKeys.all });
      void qc.invalidateQueries({ queryKey: bookingsKeys.lists() });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'cancel_window_expired') {
        toast.error('Окно отмены закрыто', {
          description: 'До занятия менее 24 часов. Отмена доступна только владельцу.',
        });
      } else {
        const msg = err instanceof ApiError ? err.message : undefined;
        toast.error(msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
      }
    },
  });
}
export { ApiError };
```

---

### `features/bookings/schemas.ts` (model/schema)

**Analog:** `apps/admin-app/src/features/memberships/schemas.ts`

```typescript
import { z } from 'zod';

export const BookingSchema = z.object({
  id: z.string(),
  slotId: z.string(),
  clientId: z.string(),
  ptPackageId: z.string(),
  status: z.enum(['confirmed', 'cancelled', 'no_show', 'completed']),
  // BookingDetailResponse adds slot + ptPackage snapshots
  slot: z.object({
    trainerId: z.string(),
    startTime: z.string(),
    endTime: z.string(),
    trainerFullName: z.string().optional(),
  }).optional(),
  ptPackage: z.object({
    id: z.string(),
    planName: z.string(),
    sessionsRemaining: z.number(),
    sessionsTotal: z.number(),
  }).optional(),
  clientFullName: z.string().optional(),
  createdAt: z.string(),
});
export type BookingData = z.infer<typeof BookingSchema>;

export const BookingsListResponseSchema = z.object({
  data: z.object({
    items: z.array(BookingSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

export const BookingCreateSchema = z.object({
  slotId: z.string().min(1),
  clientId: z.string().min(1, 'Клиент обязателен'),
  ptPackageId: z.string().min(1, 'Выберите PT-пакет'),
});
export type BookingCreateInput = z.infer<typeof BookingCreateSchema>;

export const CancelBookingSchema = z.object({
  reason: z.string().min(1).max(200),
});
export type CancelBookingInput = z.infer<typeof CancelBookingSchema>;
```

---

### `features/trainers/api.ts` (replace mock → http)

**Analog:** `apps/admin-app/src/features/clients/api.ts`

**Key factory + queries** (clients/api.ts lines 37–72):
```typescript
export const trainersKeys = {
  all: ['trainers'] as const,
  lists: () => [...trainersKeys.all, 'list'] as const,
  list: (filter: TrainersListQuery) => [...trainersKeys.lists(), filter] as const,
  details: () => [...trainersKeys.all, 'detail'] as const,
  detail: (id: string) => [...trainersKeys.details(), id] as const,
};

export function useTrainers(filter: TrainersListQuery = {}) {
  return useQuery({
    queryKey: trainersKeys.list(filter),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/trainers', { query: filter });
      return TrainersListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}

export function useTrainer(id: string) {
  return useQuery({
    queryKey: trainersKeys.detail(id),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/trainers/{trainer_id}', {
        params: { trainer_id: id },
      });
      return TrainerSchema.parse((raw as { data: unknown }).data);
    },
    enabled: !!id,
    staleTime: 30_000,
  });
}
```

**PATCH trainer mutation** (model after clients/api.ts lines 90–111):
```typescript
export function useUpdateTrainer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: TrainerUpdateInput }) => {
      const raw = await staffRequest('patch', '/api/v1/trainers/{trainer_id}', {
        params: { trainer_id: id },
        body,
      });
      return TrainerSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: (data) => {
      toast.success('Изменения сохранены');
      void qc.invalidateQueries({ queryKey: trainersKeys.lists() });
      void qc.invalidateQueries({ queryKey: trainersKeys.detail(data.id) });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'phone_exists') {
        // Caller handles inline Callout — do NOT toast here
        return;
      }
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
    },
  });
}
export { ApiError };
```

---

### `features/trainers/schemas.ts` (new)

**Analog:** `apps/admin-app/src/features/memberships/schemas.ts`

```typescript
import { z } from 'zod';

// Wire shape — camelCase aliases from backend
export const TrainerSchema = z.object({
  id: z.string(),
  fullName: z.string(),
  phone: z.string().nullable().optional(),
  isActive: z.boolean(),
  bio: z.string().nullable().optional(),
  specialization: z.string().nullable().optional(),
  photoUrl: z.string().nullable().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
});
export type TrainerData = z.infer<typeof TrainerSchema>;

export const TrainersListResponseSchema = z.object({
  data: z.object({
    items: z.array(TrainerSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

export const TrainerUpdateSchema = z.object({
  fullName: z.string().optional(),
  phone: z.string().nullable().optional(),
  isActive: z.boolean().optional(),
  bio: z.string().nullable().optional(),
  specialization: z.string().nullable().optional(),
  photoUrl: z.string().nullable().optional(),
});
export type TrainerUpdateInput = z.infer<typeof TrainerUpdateSchema>;
```

---

### `features/payroll/api.ts` (new, owner-only)

**Analog:** `apps/admin-app/src/features/memberships/api.ts`

**403 guard pattern** (model after PlansPage.tsx lines 282–290):
```typescript
// Payroll permission gate — inline in tab component (not in api.ts):
// if (!can(role, 'view', 'payroll')) return <EmptyState icon={Lock} title="Недостаточно прав" … />;
// All payroll hooks are still called conditionally via `enabled: can(role,'view','payroll')`
```

**Comp-config query** (model after memberships/api.ts lines 43–54):
```typescript
export function usePayrollConfig(trainerId: string) {
  const { role } = useSession();
  return useQuery({
    queryKey: payrollKeys.config(trainerId),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/payroll/trainer-configs/{trainer_id}', {
        params: { trainer_id: trainerId },
      });
      return PayrollConfigSchema.parse((raw as { data: unknown }).data);
    },
    enabled: !!trainerId && can(role, 'view', 'payroll'),
    staleTime: 30_000,
  });
}
```

**PUT comp-config mutation** (INSERT-only versioned — model after useSellMembership):
```typescript
export function useSetPayrollConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ trainerId, body }: { trainerId: string; body: PayrollConfigInput }) => {
      const raw = await staffRequest('put', '/api/v1/payroll/trainer-configs/{trainer_id}', {
        params: { trainer_id: trainerId },
        body,
      });
      return PayrollConfigSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: (_data, vars) => {
      toast.success('Конфигурация сохранена');
      void qc.invalidateQueries({ queryKey: payrollKeys.config(vars.trainerId) });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
    },
  });
}
```

**Accrual run mutation** with 409 handling (model after useCancelMembership):
```typescript
export function useRunAccrual() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: RunAccrualInput) => {
      const raw = await staffRequest('post', '/api/v1/payroll/accruals', { body });
      return AccrualSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: (_data, vars) => {
      toast.success('Начисление выполнено');
      void qc.invalidateQueries({ queryKey: payrollKeys.accruals(vars.trainerId) });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'payroll_period_already_run') {
        toast.error('Период уже обработан', {
          description: 'Начисление за этот период уже выполнено.',
        });
      } else {
        const msg = err instanceof ApiError ? err.message : undefined;
        toast.error(msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
      }
    },
  });
}
```

**Mark-paid mutation** (model after useCancelMembership):
```typescript
export function useMarkAccrualPaid() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ accrualId, trainerId }: { accrualId: string; trainerId: string }) => {
      await staffRequest('post', '/api/v1/payroll/accruals/{accrual_id}/mark-paid', {
        params: { accrual_id: accrualId },
      });
    },
    onSuccess: (_data, vars) => {
      toast.success('Выплата зафиксирована');
      void qc.invalidateQueries({ queryKey: payrollKeys.accruals(vars.trainerId) });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'already_paid') {
        toast.error('Уже выплачено', {
          description: 'Это начисление уже отмечено как выплаченное.',
        });
        // Caller should refetch accruals list on this path too
      } else {
        const msg = err instanceof ApiError ? err.message : undefined;
        toast.error(msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
      }
    },
  });
}
export { ApiError };
```

---

### `features/payroll/schemas.ts` (new)

**Analog:** `apps/admin-app/src/features/memberships/schemas.ts`

```typescript
import { z } from 'zod';

export const PayrollConfigSchema = z.object({
  id: z.string(),
  trainerId: z.string(),
  commissionPctBps: z.number().int().min(0).max(10000),
  sessionFeeKopecks: z.number().int().min(0),
  effectiveFrom: z.string(),
  createdAt: z.string(),
});
export type PayrollConfigData = z.infer<typeof PayrollConfigSchema>;

export const PayrollConfigInputSchema = z.object({
  commissionPctBps: z.number().int().min(0, 'Комиссия: от 0 до 100%').max(10000, 'Комиссия: от 0 до 100%'),
  sessionFeeKopecks: z.number().int().min(0, 'Ставка не может быть отрицательной'),
  effectiveFrom: z.string().min(1, 'Укажите дату начала действия'),
});
export type PayrollConfigInput = z.infer<typeof PayrollConfigInputSchema>;

export const AccrualPreviewSchema = z.object({
  sessionCount: z.number(),
  fixedKopecks: z.number(),
  commissionKopecks: z.number(),
  totalKopecks: z.number(),
});
export type AccrualPreviewData = z.infer<typeof AccrualPreviewSchema>;

export const AccrualSchema = z.object({
  id: z.string(),
  trainerId: z.string(),
  periodStart: z.string(),
  periodEnd: z.string(),
  sessionCount: z.number(),
  fixedKopecks: z.number(),
  commissionKopecks: z.number(),
  totalKopecks: z.number(),
  status: z.enum(['pending', 'paid', 'clawback']),
  accruedAt: z.string(),
});
export type AccrualData = z.infer<typeof AccrualSchema>;

export const AccrualsListResponseSchema = z.object({
  data: z.object({
    items: z.array(AccrualSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

export const RunAccrualSchema = z.object({
  trainerId: z.string().min(1),
  periodStart: z.string().min(1),
  periodEnd: z.string().min(1),
});
export type RunAccrualInput = z.infer<typeof RunAccrualSchema>;
```

---

### `components/modals/ScheduleManagementModal.tsx` (new, owner-only)

**Analog:** `apps/admin-app/src/components/modals/TrainerFormModal.tsx` (ChipGroup tab switcher pattern) + `AdaptiveModal.tsx` (shell)

**Shell pattern** (TrainerFormModal.tsx lines 1–18, AdaptiveModal.tsx lines 43–57):
```typescript
import { useState } from 'react';
import { toast } from 'sonner';
import { CalendarPlus, Loader2, TriangleAlert } from '@/components/icons';
import { AdaptiveModal } from './AdaptiveModal';
import {
  ChipGroup, Callout, Field, FieldRow, IconChip,
  ModalButton, ModalInput, ModalSelect, ModalTextarea, Section, StatRow,
} from './fields';
import { usePublishSlot, useCreateTemplate, useCreateTimeOff } from '@/features/schedule/api';
import { useTrainers } from '@/features/trainers/api';
import type { ApiError } from '@/features/schedule/api';

type Tab = 'slot' | 'template' | 'timeoff';

export function ScheduleManagementModal({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [tab, setTab] = useState<Tab>('slot');
  // reset on open (pattern from BookModal.tsx lines 53–61):
  // useEffect(() => { if (open) { setTab('slot'); /* reset field state */ } }, [open]);

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip tone="accent" icon={CalendarPlus} />}
      title="Управление расписанием"
      description="Слот · Шаблон · Блокировка"
      footerActions={/* cancel + submit buttons per active tab */}
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
      {tab === 'slot' && <SlotTab onSuccess={() => onOpenChange(false)} />}
      {tab === 'template' && <TemplateTab onSuccess={() => onOpenChange(false)} />}
      {tab === 'timeoff' && <TimeOffTab onSuccess={() => onOpenChange(false)} />}
    </AdaptiveModal>
  );
}
```

**409 inline Callout pattern** (fields.tsx line 312 — `Callout` re-exported from `@/components/ui/callout`):
```typescript
// Inside SlotTab after fields, before footer:
{apiError && (
  <Callout tone="danger" icon={TriangleAlert}>
    {ERROR_COPY[apiError.code] ?? apiError.message}
  </Callout>
)}
```

**Time-off conflict / force-override state:**
```typescript
// TimeOffTab local state:
const [conflictData, setConflictData] = useState<{ conflictingSlotIds: string[]; conflictingBookingIds: string[] } | null>(null);

// On 409 time_off_booked_conflict:
onError: (err) => {
  if (err instanceof ApiError && err.code === 'time_off_booked_conflict') {
    setConflictData(err.data); // conflict ids from error body
  } else { /* generic error */ }
},
// Render: conflictData ? <ConflictState data={conflictData} /> : <TimeOffForm />
```

---

### `components/modals/BookingModal.tsx` (new)

**Analog:** `apps/admin-app/src/components/modals/BookModal.tsx`

**Shell** (BookModal.tsx lines 40–80):
```typescript
export function BookingModal({
  slotId, trainerFullName, slotStartTime, slotEndTime,
  open, onOpenChange,
}: BookingModalProps) {
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [selectedPtPackageId, setSelectedPtPackageId] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    if (open) { setSelectedClientId(null); setSelectedPtPackageId(null); setApiError(null); }
  }, [open]);

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={open && isPending ? () => {} : onOpenChange}  // suppress close while pending
      icon={<IconChip tone="accent" icon={CalendarCheck} />}
      title="Записать клиента"
      description={`${trainerFullName} · ${formatSlotTime(slotStartTime, slotEndTime)}`}
      footerInfo={selectedClientId ? <FooterInfo /> : null}
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton
            variant="primary"
            disabled={!selectedClientId || !selectedPtPackageId || isPending}
            onClick={handleBook}
          >
            {isPending ? <Loader2 className="size-4 animate-spin" /> : null}
            Записать
          </ModalButton>
        </>
      }
    >
      {/* Client search section */}
      {/* PT-package section (shown only when client selected) */}
      {/* 409 race-conflict Callout */}
      {apiError && <Callout tone="danger" icon={TriangleAlert}>{apiError}</Callout>}
    </AdaptiveModal>
  );
}
```

**409 race-safe handling + calendar invalidate** (model after memberships cancel 409 at lines 327–338):
```typescript
const createBooking = useCreateBooking();
const qc = useQueryClient();

const handleBook = async () => {
  setApiError(null);
  try {
    await createBooking.mutateAsync({ slotId, clientId: selectedClientId!, ptPackageId: selectedPtPackageId! });
    toast.success('Запись создана', { description: `${clientName} · ${trainerFullName} · ${formatSlotTime(...)}` });
    onOpenChange(false);
  } catch (err) {
    if (err instanceof ApiError && (err.code === 'slot_already_booked' || err.code === 'slot_not_available')) {
      setApiError('Слот уже занят — кто-то успел записаться раньше. Закройте это окно — расписание обновится.');
      void qc.invalidateQueries({ queryKey: scheduleKeys.all }); // calendar refetches
    } else if (err instanceof ApiError) {
      setApiError(PT_PACKAGE_ERRORS[err.code] ?? err.message);
    }
    // Modal stays open — user manually closes
  }
};
```

---

## Modified Pages — Pattern Notes

### `pages/schedule/SchedulePage.tsx`

**FAB role-gate** (model after PlansPage.tsx lines 305–310):
```typescript
// Reception: no FAB rendered
{can(role, 'create', 'schedule-slots') && (
  <button className="fixed bottom-6 right-6 z-30 …" onClick={() => setManagementOpen(true)}>
    <Plus … />
    Управление расписанием
  </button>
)}
```

**PageLoading / PageError / EmptyState** (PlansPage.tsx lines 315–323):
```typescript
{(slotsQuery.isPending || bookingsQuery.isPending) && <PageLoading />}
{(slotsQuery.isError || bookingsQuery.isError) && <PageError onRetry={() => { slotsQuery.refetch(); bookingsQuery.refetch(); }} />}
{!slotsQuery.isPending && slots.length === 0 && (
  <EmptyState
    icon={can(role, 'create', 'schedule-slots') ? CalendarPlus : CalendarX}
    title={can(role, 'create', 'schedule-slots') ? 'Расписание пусто' : 'Нет слотов на эту неделю'}
    …
  />
)}
```

### `pages/trainers/TrainersPage.tsx`

**Section removal** (model after P101 clients filter reduction — hide, not conditionally render):
- Remove `<section ref={loadRef}>` (`<LoadHeatmap>`) entirely — no backend
- Remove `<RequestsCard>` entirely — no backend
- Remove `<EarningsCard>` entirely — Phase 104
- If only one tab remains in `TrainerFilterTabs` → hide the tab bar entirely

**Owner-only edit button** (model after PlansPage.tsx lines 306–309):
```typescript
{can(role, 'edit', 'trainers') && (
  <button aria-label="Редактировать тренера" onClick={() => openEdit(trainer)}>
    <Pencil className="size-[15px]" />
  </button>
)}
```

### `pages/trainer/components/PayoutsTab.tsx` (wired)

**Reception 403 gate** (model after PlansPage.tsx lines 317–323):
```typescript
if (!can(role, 'view', 'payroll')) {
  return (
    <EmptyState
      icon={Lock}
      title="Недостаточно прав"
      message="Раздел выплат доступен только владельцу."
    />
  );
}
// All payroll useQuery hooks beneath this guard — no API calls for reception
```

**Money display** — always `formatRub(kopecks)` from `@/lib/format` (integer kopecks → rubles string with NBSPs). For comp-config editor: display = `kopecks / 100`; send back = `Math.round(rubles * 100)`. For commissionPctBps: display = `bps / 100`; send back = `Math.round(pct * 100)`.

---

## Shared Patterns

### Authentication / staffRequest Transport
**Source:** `apps/admin-app/src/api/client.ts` (import via `staffRequest, ApiError`)
**Apply to:** All new `features/*/api.ts` files
```typescript
import { staffRequest, ApiError } from '@/api/client';
// Re-export ApiError for page/modal ESLint boundary compliance:
export { ApiError };
```

### Idempotency-Key
**Source:** `apps/admin-app/src/features/memberships/api.ts` lines 84–87
**Apply to:** ALL schedule mutations (publish slot, cancel slot, create template, deactivate template, create time-off, delete time-off) + booking create + booking cancel
```typescript
headers: { 'Idempotency-Key': crypto.randomUUID() }
// Called INSIDE mutationFn — fresh UUID per attempt, never at hook init
```

### Schema Parse Pattern
**Source:** `apps/admin-app/src/features/memberships/api.ts` lines 46–49, 88–89
**Apply to:** All queryFn and mutationFn returning typed objects
```typescript
// List: Schema.parse(raw).data
// Single: Schema.parse((raw as { data: unknown }).data)
```

### Query staleTime
**Source:** `apps/admin-app/src/features/clients/api.ts` line 57
**Apply to:** All new useQuery hooks
```typescript
staleTime: 30_000,
```

### Error Toast Fallback
**Source:** `apps/admin-app/src/features/memberships/api.ts` lines 97–100
**Apply to:** All onError handlers
```typescript
const msg = err instanceof ApiError ? err.message : undefined;
toast.error(msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
```

### 403 EmptyState Gate
**Source:** `apps/admin-app/src/pages/plans/PlansPage.tsx` lines 282–323
**Apply to:** PayoutsTab (payroll), any section that is owner-only
```typescript
// Pre-query check via can():
if (!can(role, 'view', 'payroll')) {
  return <EmptyState icon={Lock} title="Недостаточно прав" message="…" />;
}
// Post-query 403 check for unexpected forbidden:
const isForbidden = query.isError && query.error instanceof ApiError && query.error.code === 'forbidden';
```

### Modal Reset on Open
**Source:** `apps/admin-app/src/components/modals/BookModal.tsx` lines 53–61
**Apply to:** ScheduleManagementModal, BookingModal, BookingDetailModal
```typescript
useEffect(() => {
  if (open) {
    // reset all local state to initial values
  }
}, [open]);
```

### AdaptiveModal Shell
**Source:** `apps/admin-app/src/components/modals/AdaptiveModal.tsx` — size=`'default'` (max-w-540px desktop, drawer mobile), body `px-5 py-[18px] sm:px-[22px]`
**Apply to:** ScheduleManagementModal, BookingModal, BookingDetailModal

### ConfirmModal for Destructive Confirms
**Source:** `apps/admin-app/src/components/modals/ConfirmModal.tsx` lines 12–60
**Apply to:** Booking cancel confirm, Mark-paid confirm
```typescript
<ConfirmModal
  open={confirmOpen}
  onOpenChange={setConfirmOpen}
  payload={{
    title: 'Отменить бронирование?',
    message: '…',
    tone: 'danger',
    confirmLabel: 'Отменить запись',
    cancelLabel: 'Назад',
    onConfirm: async () => { await cancelBooking.mutateAsync(…); },
  }}
/>
```

### fields.tsx Primitives Available
**Source:** `apps/admin-app/src/components/modals/fields.tsx`
All these are available for direct import:
- `Section`, `Field`, `FieldRow` — layout
- `ModalInput`, `ModalSelect`, `ModalTextarea` — inputs (all use `CONTROL` class with `h-[42px] rounded-xl border-[0.5px] border-border bg-surface-2`)
- `ChipGroup` — tab switcher in ScheduleManagementModal
- `PlanCards` — PT-package picker in BookingModal
- `ResultList`, `ResultItem` — client search results in BookingModal
- `ModalButton` (variants: `primary`, `ghost`, `danger`, `text`) — footer actions
- `IconChip` (tones: `accent`, `warn`, `danger`, `indigo`) — modal header icon
- `StatRow` — read-only data display rows
- `Callout` (re-exported from `@/components/ui/callout`) — 409/error display

---

## No Analog Found

None. All files have close analogs in the existing codebase.

---

## Metadata

**Analog search scope:** `apps/admin-app/src/features/`, `apps/admin-app/src/components/modals/`, `apps/admin-app/src/pages/plans/`, `apps/backend/app/modules/pt_sessions/`
**Files scanned:** ~20
**Pattern extraction date:** 2026-06-13
