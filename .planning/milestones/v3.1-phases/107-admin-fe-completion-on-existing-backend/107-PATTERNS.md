# Phase 107: Admin FE Completion on Existing Backend — Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 7 (4 new, 3 modified)
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `components/modals/PlanFormModal.tsx` | component / form-modal | request-response (create + update) | `components/modals/SubscriptionModal.tsx` (CreateScreen) + `components/modals/ExtendModal.tsx` (FieldRow/ModalInput layout) | exact |
| `components/modals/PtPackageSellModal.tsx` | component / form-modal | request-response (sell) | `components/modals/SubscriptionModal.tsx` CreateScreen (plan select → StatRow → notes) | exact |
| `components/modals/PtPackageCancelDialog.tsx` | component / confirm-modal | request-response (cancel) | `components/modals/SubscriptionModal.tsx` CancelScreen | exact |
| `components/modals/PtPackageRefundDialog.tsx` | component / confirm-modal | request-response (refund) | `components/modals/SubscriptionModal.tsx` RefundScreen | exact |
| `pages/plans/PlansPage.tsx` | page | CRUD (create + update wiring) | self (add local modal state + replace stub handlers) | self-modification |
| `pages/client/components/TrainingsTab.tsx` | component | CRUD (sell/cancel/refund actions) | `pages/client/components/ProfileHeroReal.tsx` (DropdownMenu) + `SubscriptionModal.tsx` (lifecycle patterns) | role-match |
| `pages/client/components/ProfileHeroReal.tsx` | component | request-response (delete) | self + `features/clients/api.ts:114` | self-modification |

---

## Pattern Assignments

### `components/modals/PlanFormModal.tsx` (component, request-response)

**Primary analog:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx`
**Secondary analog (FieldRow layout):** `apps/admin-app/src/components/modals/ExtendModal.tsx`

**File-level structure pattern** (from SubscriptionModal lines 1–48):
- Top-level JSDoc block documenting the screens and wire update rationale
- All imports at top: `useEffect`, `useState`, `cn`, `formatKopecks`, hooks from features, icons from `@/components/icons`, then local modal imports
- Internal component per concern (no default export; named export for the dispatcher)

**Imports pattern** (mirror SubscriptionModal lines 17–45 + plans/schemas):
```typescript
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { cn } from '@/lib/cn'
import { formatKopecks } from '@/lib/format'
import { useSession } from '@/features/auth/api'
import { can } from '@/shared/session/can'
import { useCreatePlan, useUpdatePlan, ApiError } from '@/features/plans/api'
import { useCreatePtPackagePlan, useUpdatePtPackagePlan } from '@/features/pt-packages/api'
import {
  MembershipPlanCreateSchema,
  MembershipPlanUpdateSchema,
  type MembershipPlanData,
  type MembershipPlanCreateInput,
} from '@/features/plans/schemas'
import {
  PtPackagePlanCreateSchema,
  PtPackagePlanUpdateSchema,
  type PtPackagePlanData,
  type PtPackagePlanCreateInput,
} from '@/features/pt-packages/schemas'
import { Loader2, Plus, Dumbbell, SquarePen, TriangleAlert } from '@/components/icons'
import { AdaptiveModal } from './AdaptiveModal'
import {
  Callout, Field, FieldRow, IconChip, ModalButton, ModalInput, StatRow
} from './fields'
```

**ErrorCallout helper** (from SubscriptionModal lines 81–94 — copy verbatim):
```typescript
function ErrorCallout({ error }: { error: Error | null }) {
  if (!error) return null
  const msg =
    error instanceof ApiError
      ? error.message
      : 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.'
  return (
    <div className="mt-3.5">
      <Callout tone="danger" icon={TriangleAlert}>
        {msg}
      </Callout>
    </div>
  )
}
```

**useEffect reset on open** (from SubscriptionModal lines 106–112):
```typescript
useEffect(() => {
  if (open) {
    // reset all local state + mutation.reset()
    createMutation.reset()
    updateMutation.reset()
  }
}, [open]) // eslint-disable-line react-hooks/exhaustive-deps
```

**FieldRow + ModalInput layout** (from ExtendModal lines 122–143):
```typescript
// Numeric pairs go in FieldRow cols={2}; name field is full-width above
<Field label="Название" required>
  <ModalInput type="text" ... />
</Field>
<FieldRow>
  <Field label="Длительность" hint="Нельзя изменить после создания">
    <ModalInput type="number" min={1} suffix="дн." disabled={mode === 'edit'} ... />
  </Field>
  <Field label="Стоимость">
    <ModalInput type="number" min={0} suffix="₽" disabled={mode === 'edit'} ... />
  </Field>
</FieldRow>
```

**Skeleton loading state for inputs** (from SubscriptionModal lines 161–163):
```typescript
{plansQuery.isPending ? (
  <div className="h-[42px] animate-pulse rounded-xl bg-surface-3" />
) : (
  <ModalInput ... />
)}
```

**Footer with isPending guard** (from SubscriptionModal lines 143–157):
```typescript
footerActions={
  <>
    <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
      Не создавать
    </ModalButton>
    <ModalButton disabled={isPending || !isValid} onClick={handleSubmit}>
      {isPending ? (
        <>
          <Loader2 className="size-[18px] animate-spin" />
          Обработка…
        </>
      ) : (
        'Создать тариф'
      )}
    </ModalButton>
  </>
}
```

**onOpenChange isPending block** (from SubscriptionModal line 133):
```typescript
onOpenChange={isPending ? () => {} : onOpenChange}
```

**Manual Schema.safeParse validation** (D-101-01-NOHOOKFORM — no @hookform/resolvers):
```typescript
// Validate on submit; map .error.flatten().fieldErrors to per-field state
function handleSubmit() {
  const result = MembershipPlanCreateSchema.safeParse(formData)
  if (!result.success) {
    setErrors(result.error.flatten().fieldErrors)
    setSubmitAttempted(true)
    return
  }
  // ...
}
// Inline error display (text-[12px] text-danger below the ModalInput):
{submitAttempted && errors.name?.[0] && (
  <span className="mt-1 block text-[12px] text-danger">{errors.name[0]}</span>
)}
```

**422 field-error mapping** (based on ApiError + CONTEXT.md decisions):
```typescript
onError: (err) => {
  if (err instanceof ApiError && err.fields) {
    // Map fields[] to per-field inline errors
    setServerErrors(mapFieldErrors(err.fields))
  }
  // Non-field errors → ErrorCallout (rendered below all fields)
}
```

**Success with toast** (from PlansPage lines 243–244 — same pattern):
```typescript
onSuccess: (data) => {
  onOpenChange(false)
  toast.success('Тариф создан', { description: data.name })
}
```

**AdaptiveModal shell** — use `size="wide"` (up to 720px); icon/title/description vary by `kind` and `mode` per UI-SPEC Surface 1 copywriting table.

---

### `components/modals/PtPackageSellModal.tsx` (component, request-response)

**Analog:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx` CreateScreen (lines 100–194)

**Imports** (adapt from SubscriptionModal):
```typescript
import { useEffect, useState } from 'react'
import { cn } from '@/lib/cn'
import { formatKopecks } from '@/lib/format'
import { useSession } from '@/features/auth/api'
import { usePtPackagePlans, useSellPtPackage, ApiError } from '@/features/pt-packages/api'
import { CreditCard, Loader2, TriangleAlert } from '@/components/icons'
import { AdaptiveModal } from './AdaptiveModal'
import { Callout, Field, IconChip, ModalButton, ModalTextarea, StatRow } from './fields'
```

**Plan select + skeleton** (copy CreateScreen lines 160–178 — change usePlans → usePtPackagePlans):
```typescript
<Field label="Пакет">
  {plansQuery.isPending ? (
    <div className="h-[42px] animate-pulse rounded-xl bg-surface-3" />
  ) : (
    <select
      value={selectedPlanId}
      onChange={(e) => setSelectedPlanId(e.target.value)}
      disabled={isPending}
      className="w-full h-[42px] cursor-pointer appearance-none rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 pr-9 text-sm text-fg outline-none transition-colors focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]"
    >
      <option value="">Выберите пакет…</option>
      {plans.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name} · {formatKopecks(p.priceKopecks)}
        </option>
      ))}
    </select>
  )}
</Field>
```

**К оплате StatRow** (from CreateScreen line 180):
```typescript
{selectedPlan ? (
  <StatRow label="К оплате" value={formatKopecks(selectedPlan.priceKopecks)} accent />
) : null}
```

**amount_mismatch defensive callout** (from CONTEXT.md + UI-SPEC Surface 2):
```typescript
// After mutation error, check if code === 'amount_mismatch'
{isAmountMismatch && (
  <div className="mt-3.5">
    <Callout tone="warn" icon={TriangleAlert}>
      Стоимость пакета изменилась. Обновите страницу и попробуйте снова.
    </Callout>
  </div>
)}
```

**handleSubmit with amountKopecks locked to plan price** (from API + CONTEXT decisions):
```typescript
function handleSubmit() {
  if (!clientId || !selectedPlanId || !selectedPlan) return
  sellMutation.mutate(
    {
      clientId,
      planId: selectedPlanId,
      amountKopecks: selectedPlan.priceKopecks, // locked, never typed by operator
    },
    { onSuccess: () => onOpenChange(false) },
  )
}
```

**Note:** `useSellPtPackage` already fires `toast.success` in `onSuccess` (api.ts lines 173–175) — do NOT add a duplicate toast in the modal's `onSuccess`.

---

### `components/modals/PtPackageCancelDialog.tsx` (component, request-response)

**Analog:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx` CancelScreen (lines 443–525)

**Key differences from membership CancelScreen:**
- Reason is **REQUIRED** (not optional) — validate on submit + onBlur, disable button when empty
- Add char counter (`{reason.length}/200`) right-aligned at `text-[11.5px] tabular-nums text-fg-subtle`
- Warn callout is always shown (not just on submit error)
- Button variant is `"danger"` (same as membership but with different copy)

**Imports:**
```typescript
import { useEffect, useState } from 'react'
import { useCancelPtPackage, ApiError } from '@/features/pt-packages/api'
import { CircleX, Loader2, TriangleAlert } from '@/components/icons'
import { AdaptiveModal } from './AdaptiveModal'
import { Callout, Field, IconChip, ModalButton, ModalTextarea } from './fields'
```

**Required-reason textarea with counter** (from SubscriptionModal RefundScreen lines 606–629):
```typescript
<Field label="Причина отмены" required>
  <textarea
    className={cn(
      'min-h-[80px] w-full resize-none rounded-[10px] border-[0.5px] border-border bg-surface-2',
      'px-3 py-2.5 text-[13.5px] outline-none placeholder:text-fg-subtle',
      'focus:border-primary focus:ring-2 focus:ring-primary/20',
    )}
    maxLength={200}
    placeholder="Укажите причину отмены"
    value={reason}
    disabled={isPending}
    onChange={(e) => setReason(e.target.value)}
    onBlur={() => setTouched(true)}
  />
  <div className="mt-1 flex justify-between">
    {touched && reasonTrimmed.length === 0 ? (
      <span className="text-[12px] text-danger">Причина обязательна</span>
    ) : (
      <span />
    )}
    <span className="ml-auto text-[11.5px] tabular-nums text-fg-subtle">
      {reason.length}/200
    </span>
  </div>
</Field>
```

**Always-shown warning callout** (from SubscriptionModal CancelScreen lines 518–521):
```typescript
<Callout tone="danger" icon={TriangleAlert}>
  Пакет станет неактивным. Оставшиеся занятия будут аннулированы. Действие необратимо.
</Callout>
```

**Danger footer with required-reason disable** (from SubscriptionModal RefundScreen lines 571–589, adapted):
```typescript
<ModalButton variant="danger" disabled={isPending || reasonTrimmed.length === 0} onClick={handleSubmit}>
  {isPending ? (
    <><Loader2 className="size-[18px] animate-spin" /> Обработка…</>
  ) : (
    'Отменить пакет'
  )}
</ModalButton>
```

**handleSubmit** (from SubscriptionModal RefundScreen lines 547–557, adapted):
```typescript
function handleSubmit() {
  setTouched(true)
  if (!reasonTrimmed || !packageId) return
  cancelMutation.mutate(
    { packageId, body: { reason: reasonTrimmed } },
    { onSuccess: () => { onOpenChange(false) } }, // useCancelPtPackage owns its success toast (api.ts ~205-208) — do NOT duplicate here
  )
}
```

**Note:** `useCancelPtPackage` fires its own toast on success (api.ts lines 205–208) — caller's `onSuccess` should only close the modal. Cross-check hook behavior before adding a surface-level toast.

---

### `components/modals/PtPackageRefundDialog.tsx` (component, request-response)

**Analog:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx` RefundScreen (lines 531–634)

**Verbatim copy points:**
- `useState` for `reason`, `touched` (lines 532–533)
- `useEffect` reset on open (lines 536–541)
- `reasonTrimmed = reason.trim()` (line 545)
- Textarea inline classes (lines 608–612) — copy **verbatim** per UI-SPEC Surface 4
- Counter + touched error layout (lines 619–628) — copy verbatim

**Differences from membership RefundScreen:**
- Use `useRefundPtPackage` instead of `useRefundMembership`
- Pass `packageId` not `membershipId`
- StatRow label «К возврату» (not «Оплачено»); add second StatRow «Дата покупки»
- Footer CTA: `Вернуть {formatKopecks(item.amountKopecks)}`
- Ghost cancel: «Не возвращать» (not «Отмена»)

**Imports:**
```typescript
import { useEffect, useState } from 'react'
import { formatKopecks, formatDateRu } from '@/lib/format'
import { useRefundPtPackage, ApiError } from '@/features/pt-packages/api'
import { Loader2, ReceiptText, TriangleAlert } from '@/components/icons'
import { AdaptiveModal } from './AdaptiveModal'
import { Callout, Field, IconChip, ModalButton, StatRow } from './fields'
```

**Info rows before textarea** (from RefundScreen lines 593–604, adapted):
```typescript
<Callout tone="warn" icon={TriangleAlert}>
  Возврат полный и необратимый. Средства вернутся тем же способом, которым была принята оплата.
</Callout>
<StatRow label="К возврату" value={formatKopecks(item.amountKopecks)} accent />
<StatRow label="Дата покупки" value={formatDateRu(item.createdAt, 'd MMMM yyyy')} />
```

**Note:** `useRefundPtPackage` fires its own toast on success (api.ts lines 244–246) — caller's `onSuccess` should only close the modal.

---

### `pages/plans/PlansPage.tsx` (page, CRUD — stub handlers only)

**Pattern:** Self-modification. No new patterns — replace stub `toast(...)` calls with local modal state.

**Local modal state pattern** (common React pattern in this codebase):
```typescript
// Add at top of PlansPage() alongside existing useState calls
const [planFormModal, setPlanFormModal] = useState<{
  open: boolean
  kind: 'membership' | 'pt-package'
  mode: 'create' | 'edit'
  plan?: MembershipPlanData | PtPackagePlanData
}>({ open: false, kind: 'membership', mode: 'create' })
```

**Replace stub handlers** (PlansPage.tsx lines 232–262):
```typescript
// BEFORE:
const handleCreatePlan = () => { toast('Создание тарифа') }
const handleEditPlan = (plan: MembershipPlanData) => { toast(`Редактирование тарифа «${plan.name}»`) }

// AFTER:
const handleCreatePlan = () =>
  setPlanFormModal({ open: true, kind: 'membership', mode: 'create' })
const handleEditPlan = (plan: MembershipPlanData) =>
  setPlanFormModal({ open: true, kind: 'membership', mode: 'edit', plan })
const handleCreatePtPlan = () =>
  setPlanFormModal({ open: true, kind: 'pt-package', mode: 'create' })
const handleEditPtPlan = (plan: PtPackagePlanData) =>
  setPlanFormModal({ open: true, kind: 'pt-package', mode: 'edit', plan })
```

**Modal placement** (D-101 decision — page-scoped, NOT ModalsProvider):
```typescript
// At bottom of PlansPage JSX, before closing </div>:
<PlanFormModal
  open={planFormModal.open}
  onOpenChange={(open) => setPlanFormModal((s) => ({ ...s, open }))}
  kind={planFormModal.kind}
  mode={planFormModal.mode}
  plan={planFormModal.plan}
/>
```

**Permission gating pattern** (existing in PlansPage lines 204–208 — follow exactly):
```typescript
const canEditMembershipPlans = can(role, 'edit', 'membership-plans')
// ... existing gates unchanged
```

---

### `pages/client/components/TrainingsTab.tsx` (component, CRUD — add kebab actions)

**Primary analog for kebab:** `apps/admin-app/src/pages/client/components/ProfileHeroReal.tsx` (lines 126–170)

**DropdownMenu imports** (from ProfileHeroReal lines 14–20 — exact same import path):
```typescript
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
```

**Kebab button pattern** (icon-only, from ProfileHeroReal lines 127–135):
```typescript
<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <button
      type="button"
      aria-label="Действия с пакетом"
      className="h-8 w-8 rounded-lg inline-flex items-center justify-center text-fg-subtle hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <MoreHorizontal className="size-[15px]" />
    </button>
  </DropdownMenuTrigger>
  <DropdownMenuContent align="end" className="min-w-[160px]">
    {/* Refund — visible to both owner and reception */}
    <DropdownMenuItem onSelect={() => setRefundTarget(item)}>
      Вернуть оплату
    </DropdownMenuItem>
    {/* Cancel — OWNER_ONLY via can() */}
    {can(role, 'cancel', 'pt-packages') && (
      <>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-danger focus:text-danger"
          onSelect={() => setCancelTarget(item)}
        >
          Отменить пакет
        </DropdownMenuItem>
      </>
    )}
  </DropdownMenuContent>
</DropdownMenu>
```

**Danger menu item style** (from ProfileHeroReal line 152 — exact class):
```typescript
className="text-danger focus:text-danger"
```

**Local dialog state for TrainingsTab** (same pattern as PlansPage modal state):
```typescript
const [cancelTarget, setCancelTarget] = useState<PtPackageData | null>(null)
const [refundTarget, setRefundTarget] = useState<PtPackageData | null>(null)
const [sellOpen, setSellOpen] = useState(false)
```

**«Продать пакет» button in CardHead** (use ADD_BTN class from PlansPage lines 37–38):
```typescript
// Entry button style — copy ADD_BTN from PlansPage (h-9, rounded-full, border-[0.5px])
className="inline-flex h-9 items-center gap-1.5 rounded-full border-[0.5px] border-border bg-surface px-3.5 text-[13px] font-semibold text-fg transition-colors hover:border-border-strong"
```

**RBAC gating** (follow can() pattern from SubscriptionModal dispatcher lines 698–706):
```typescript
// Entry button visible to both owner and reception:
{can(role, 'create', 'pt-packages') && (
  <button ... onClick={() => setSellOpen(true)}>Продать пакет</button>
)}
```

**PtPackageRow update** — extend existing grid from `grid-cols-[1fr_auto]` (TrainingsTab line 52) to accommodate the kebab column: `grid-cols-[1fr_auto_auto]` for active packages, or render kebab conditionally outside the grid.

---

### `pages/client/components/ProfileHeroReal.tsx` (component, request-response — onConfirm only)

**Analog:** self + `features/clients/api.ts` `useDeleteClient` (lines 114–124)

**useDeleteClient hook signature** (features/clients/api.ts lines 114–124):
```typescript
export function useDeleteClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      staffRequest('delete', '/api/v1/clients/{client_id}', { params: { client_id: id } }),
    onSettled: (_data, _err, id) => {
      void qc.invalidateQueries({ queryKey: clientsKeys.lists() })
      void qc.invalidateQueries({ queryKey: clientsKeys.detail(id) })
    },
  })
}
```

**Add at component top** (ProfileHeroReal — add `useNavigate` already present on line 9):
```typescript
import { useDeleteClient } from '@/features/clients/api'
// navigate already imported; ROUTES already imported
const deleteClient = useDeleteClient()
```

**Replace stub onConfirm** (ProfileHeroReal lines 160–162):
```typescript
// BEFORE:
onConfirm: () => {
  toast.info('Удаление доступно из карточки редактирования')
},

// AFTER:
onConfirm: () => {
  deleteClient.mutate(client.id, {
    onSuccess: () => {
      navigate(ROUTES.clients)
      toast.success('Клиент удалён')
    },
    onError: () => {
      toast.error('Не удалось удалить клиента')
    },
  })
},
```

**No modal changes** — the existing `ConfirmPayload` shell (title, message, tone, confirmLabel) is already correct per UI-SPEC Surface 5. Only `onConfirm` body changes.

**Post-delete navigation** (ROUTES.clients — already imported in ProfileHeroReal line 11):
```typescript
navigate(ROUTES.clients) // navigates to /clients list
```

---

## Shared Patterns

### ErrorCallout (cross-cutting — all new modals)
**Source:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx` lines 81–94
**Apply to:** PlanFormModal, PtPackageSellModal, PtPackageCancelDialog, PtPackageRefundDialog
```typescript
function ErrorCallout({ error }: { error: Error | null }) {
  if (!error) return null
  const msg =
    error instanceof ApiError
      ? error.message
      : 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.'
  return (
    <div className="mt-3.5">
      <Callout tone="danger" icon={TriangleAlert}>
        {msg}
      </Callout>
    </div>
  )
}
```

### useEffect reset on open (cross-cutting — all new modals)
**Source:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx` lines 106–112
**Apply to:** All 4 new modal components
```typescript
useEffect(() => {
  if (open) {
    setState(initialValue)
    mutation.reset()
  }
}, [open]) // eslint-disable-line react-hooks/exhaustive-deps
```

### isPending block pattern (cross-cutting — all new modals)
**Source:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx` line 133
**Apply to:** All new AdaptiveModal wrappers
```typescript
onOpenChange={isPending ? () => {} : onOpenChange}
```

### Spinner in submit button (cross-cutting — all new modals)
**Source:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx` lines 149–154
**Apply to:** All new modals — primary/danger footer button
```typescript
{isPending ? (
  <>
    <Loader2 className="size-[18px] animate-spin" />
    Обработка…
  </>
) : (
  'Button label'
)}
```

### RBAC can() gating (cross-cutting)
**Source:** `apps/admin-app/src/shared/session/can.ts` + `features/auth/api.ts`
**Pattern from SubscriptionModal dispatcher lines 677–679:**
```typescript
const session = useSession()
const role = session.data?.role ?? 'reception'
// Then: can(role, 'cancel', 'pt-packages') for OWNER_ONLY gates
```

### ApiError re-export (all feature modules)
**Source:** all `features/*/api.ts` bottom section (plans/api.ts line 118, pt-packages/api.ts line 263, clients/api.ts line 130)
**Apply to:** Import `ApiError` from the domain-specific feature api module, not from `@/api/client` directly (ESLint import-boundary D-100-03-APIERROR-REEXPORT).

### Money formatting
**Source:** `apps/admin-app/src/lib/format.ts`
```typescript
import { formatKopecks } from '@/lib/format'
// Price input fields: accept rubles from user, multiply × 100 before sending
// StatRow/display: formatKopecks(kopecks) — Intl.NumberFormat ru-RU RUB
// suffix="₽" on ModalInput for price fields
```

### ADD_BTN class constant (TrainingsTab entry button)
**Source:** `apps/admin-app/src/pages/plans/PlansPage.tsx` lines 37–38
```typescript
// Copy verbatim for the «Продать пакет» button in TrainingsTab card header:
'inline-flex h-9 items-center gap-1.5 rounded-full border-[0.5px] border-border bg-surface px-3.5 text-[13px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
```

---

## No Analog Found

None — all 7 files have direct analogs in the codebase.

---

## Key Observations for Planner

1. **PlanFormModal is the most complex file.** It must handle `kind × mode` = 4 permutations, manual Schema.safeParse validation (no @hookform/resolvers per D-101-01-NOHOOKFORM), disabled fields with «Нельзя изменить после создания» hint, and 422 field-error mapping. The SubscriptionModal + ExtendModal together provide the complete JSX template.

2. **PT-package hooks already own their toasts — all three modals close ONLY, no surface-level toast.** `useSellPtPackage`, `useCancelPtPackage`, and `useRefundPtPackage` each fire their own Sonner success/error toasts (api.ts lines 173–183, 205–224, 244–256; cancel fires `toast.success('Пакет тренировок отменён')`). Every PT-package modal `onSuccess` callback must therefore be ONLY `onOpenChange(false)` — adding any `toast.success(...)` in the modal would double-fire. (PlanFormModal is the lone exception: the plan CRUD hooks do NOT toast, so PlanFormModal owns its own surface-level success toast.)

3. **TrainingsTab needs `useSession` + `can()`** added (not currently imported) to gate the kebab items and «Продать пакет» button visibility.

4. **ProfileHeroReal change is NOT purely surgical — it ADDS an owner-only gate.** The `onConfirm` body changes (lines 160–162) AND a `can(role, 'delete', 'clients')` gate must be ADDED around the «Удалить клиента» dropdown item (+ its preceding separator), which currently renders UNCONDITIONALLY. The file does NOT yet import `useSession` — that import + a derived `role` are new. The existing ConfirmPayload title/message stay unchanged; only the `onConfirm` body and the gating wrapper change.

5. **`usePtPackagePlans` uses `includeArchived` not `active`** (pt-packages/api.ts line 66 comment). For the sell modal, call `usePtPackagePlans()` without the flag to get active-only plans (backend default).

---

## Metadata

**Analog search scope:** `apps/admin-app/src/components/modals/`, `apps/admin-app/src/pages/plans/`, `apps/admin-app/src/pages/client/components/`, `apps/admin-app/src/features/plans/`, `apps/admin-app/src/features/pt-packages/`, `apps/admin-app/src/features/clients/`
**Files scanned:** 12
**Pattern extraction date:** 2026-06-14
