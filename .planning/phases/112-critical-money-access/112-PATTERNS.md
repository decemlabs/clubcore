# Phase 112: Critical Money & Access — Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/modules/payments/router.py` | route | request-response | `apps/backend/app/modules/users/router.py` (PATCH endpoints) | exact |
| `apps/backend/app/modules/payments/service.py` | service | CRUD (append-only) | self — extend `issue_refund` | exact |
| `apps/backend/app/modules/payments/schemas.py` | model/schema | request-response | `apps/backend/app/modules/users/schemas.py` | exact |
| `apps/backend/app/core/exceptions.py` | utility | — | self — follow `CannotDeactivateLastOwnerError` pattern | exact |
| `apps/backend/app/modules/users/router.py` | route | request-response | self (deactivate/reactivate endpoints) | exact |
| `apps/backend/app/modules/users/service.py` | service | CRUD | self — mirror `deactivate_user` guard chain | exact |
| `apps/admin-app/src/features/payments/api.ts` | hook | request-response | `apps/admin-app/src/features/users/api.ts` (useDeactivateUser) | exact |
| `apps/admin-app/src/features/users/api.ts` | hook | request-response | self — add `useChangeUserRole` beside existing mutations | exact |
| `apps/admin-app/src/pages/cashbox/components/TransactionsCard.tsx` | component | CRUD | `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` (InviteModal + UserRowActions) | role-match |
| `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` | component | request-response | self (InviteModal, UserRowActions, DropdownMenuItem pattern) | exact |

---

## Pattern Assignments

### `apps/backend/app/modules/payments/router.py` (new PATCH endpoint)

**Analog:** `apps/backend/app/modules/users/router.py` lines 118–131 (deactivate_user_endpoint)

**Decorator + signature order** (RBAC-04 rule — require_permission before verify_csrf):
```python
@router.post(
    "/{payment_id}/refund",
    status_code=status.HTTP_201_CREATED,
    response_model=ResponseEnvelope[PaymentResponse],
    summary="Issue a manual ledger refund for any recorded payment (owner-only; REF-01)",
)
async def refund_payment_endpoint(
    payment_id: UUID,
    payload: PaymentRefundRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.REFUND, Resource.FINANCE))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaymentResponse]:
```

Key points:
- `require_permission` before `verify_csrf` in the signature (RBAC-04 / users/router.py:22-25)
- `(Action.REFUND, Resource.FINANCE)` is already in `OWNER_ONLY` (permissions.py:75)
- No try/except in router — service raises `AppError` subclasses that the global handler maps (users/router.py:31-36)
- Returns `ResponseEnvelope[PaymentResponse]` with `status.HTTP_201_CREATED` (new ledger row appended)

**Imports to add to payments/router.py:**
```python
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.permissions import Action, Resource
from app.modules.payments import service as payments_service
from app.modules.payments.schemas import PaymentRefundRequest, PaymentResponse
```

---

### `apps/backend/app/modules/payments/service.py` — new `refund_arbitrary_payment` function

**Analog:** existing `issue_refund` in same file (lines 166–241)

**Core pattern** — new top-level function alongside `issue_refund`, `record_payment`:
```python
async def refund_arbitrary_payment(  # noqa: SVC001 caller-owns-txn — router owns UoW
    session: AsyncSession,
    *,
    payment_id: UUID,
    amount_kopecks: int,
    reason: str,
    audit_actor: CurrentUser,
) -> Payment:
    """REF-01 Phase 112 — refund any non-refund payment row by direct payment_id.

    Unlike issue_refund (which takes subject_kind/subject_id), this function
    fetches the original by ID, validates it is not itself a refund row, validates
    amount_kopecks <= original.amount_kopecks, inserts a negative-amount row,
    and emits refund_issued audit. Caller (router) owns commit.
    """
```

Guard logic to implement (model on `deactivate_user` service guards, users/service.py:262-280):
1. Fetch original by `payment_id` → 404 `OriginalPaymentNotFoundError` if missing
2. Reject if `original.subject_kind == SUBJECT_KIND_REFUND` → 409 `CannotRefundRefundError`
3. Reject if `amount_kopecks > original.amount_kopecks` → 409 `OverRefundError` (or use `AlreadyRefundedError` with new message)
4. `insert_payment(..., amount_kopecks=-amount_kopecks, refund_of=original.id)`
5. `await session.flush()` → catch `IntegrityError`, discriminate `uq_payments_refund_of_alive` → `AlreadyRefundedError`
6. `audit.emit(session, "refund_issued", ...)` — same field set as existing `issue_refund` lines 223–239

**Audit emit pattern** (payments/service.py lines 223–240):
```python
await audit.emit(
    session,
    "refund_issued",
    actor_user_id=audit_actor.id,
    resource_type="payment",
    resource_id=refund_payment.id,
    payment_id=str(refund_payment.id),
    refund_of_payment_id=str(original.id),
    amount_kopecks=refund_payment.amount_kopecks,
    subject_kind=original.subject_kind,
    subject_id=str(original.subject_id),
    received_by_user_id=str(audit_actor.id),
    reason=reason,
    payment_row_hash=original_hash,
)
```

---

### `apps/backend/app/modules/payments/schemas.py` — new `PaymentRefundRequest`

**Analog:** `MembershipRefundRequest` in same file (lines 61–76) + `InvitationRevokeRequest` from users/schemas.py (lines 83–87)

**Pattern:**
```python
class PaymentRefundRequest(BackendSchemaBase):
    """POST /api/v1/payments/{payment_id}/refund body (Phase 112 REF-01).

    ``reason`` is required, min 3 chars (per D-112 decision).
    ``amount_kopecks`` is required; must be > 0 and <= original (validated in service).
    BackendSchemaBase sets extra='forbid' automatically.
    """
    amount_kopecks: int = Field(gt=0, description="Refund amount in kopecks; must not exceed original payment amount.")
    reason: str = Field(min_length=3, max_length=500)
```

---

### `apps/backend/app/core/exceptions.py` — new error classes

**Analog:** `CannotDeactivateLastOwnerError` / `CannotDeactivateSelfError` (lines 394–419)

**Pattern** (add at the end of the users-guard block or in a payments block):
```python
class CannotRefundRefundError(ConflictError):
    """Raised when the actor tries to refund a refund row itself (Phase 112 REF-01)."""
    code = "cannot_refund_refund"
    status_code = 409

class OverRefundError(ConflictError):
    """Raised when requested amount_kopecks > original payment amount (Phase 112 REF-01)."""
    code = "over_refund"
    status_code = 409

class CannotChangeOwnRoleError(ConflictError):
    """Raised when actor tries to change their own role (Phase 112 TEAM-01)."""
    code = "cannot_change_own_role"
    status_code = 409

class CannotChangeLastOwnerRoleError(ConflictError):
    """Raised when demoting the last remaining owner (Phase 112 TEAM-01)."""
    code = "cannot_change_last_owner_role"
    status_code = 409
```

---

### `apps/backend/app/modules/users/router.py` — new PATCH /{user_id}/role endpoint

**Analog:** `deactivate_user_endpoint` (lines 118–131) — exact same decorator + signature shape

**Pattern:**
```python
@router.patch(
    "/{user_id}/role",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change a staff user's role (owner↔reception); 409 on self / last-owner demotion",
)
async def change_user_role_endpoint(
    user_id: UUID,
    payload: UserRoleChangeRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.UPDATE, Resource.USERS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """TEAM-01 / Phase 112 — self + last-owner guards; UPDATE permission + CSRF required."""
    await service.change_user_role(session, actor, user_id, payload.role)
    return None
```

Wire format: `204 No Content` (mirrors deactivate/reactivate) — no response body.

---

### `apps/backend/app/modules/users/service.py` — new `change_user_role` function

**Analog:** `deactivate_user` (lines 251–302) — same guard chain structure

**Pattern:**
```python
async def change_user_role(
    session: AsyncSession,
    actor: CurrentUser,
    target_user_id: UUID,
    new_role: Role,
) -> None:
    """TEAM-01 / Phase 112 — self + last-owner demotion guards, then UPDATE + audit.

    Effect timing: role persists immediately; reflected on target's NEXT login.
    No session invalidation (existing sessions keep old role until re-auth).
    """
    target = await repository.get_alive(session, target_user_id)
    if target is None:
        raise UserNotFoundError("user_not_found")
    if target.id == actor.id:
        raise CannotChangeOwnRoleError("cannot_change_own_role")
    if target.role == Role.OWNER and new_role != Role.OWNER:
        # Demoting an owner — guard against last-owner demotion
        active_owner_count = await repository.count_active_owners_excluding(
            session, excluded_user_id=target_user_id
        )
        if active_owner_count < 1:
            raise CannotChangeLastOwnerRoleError("cannot_change_last_owner_role")

    await repository.update_user_role(session, target_user_id=target_user_id, new_role=new_role)

    await audit.emit(
        session,
        "user_role_changed",
        actor_user_id=actor.id,
        resource_type="user",
        resource_id=target_user_id,
        audit_correlation_id=None,
        changed_user_id=str(target_user_id),
        old_role=target.role.value,
        new_role=new_role.value,
    )
    await session.flush()
    await session.commit()
```

Note: `count_active_owners_excluding` already exists in `users/repository.py` (used by deactivate_user) — reuse without modification.

---

### `apps/backend/app/modules/users/schemas.py` — new `UserRoleChangeRequest`

**Analog:** `UserCreateRequest` (lines 27–32) + `InvitationRevokeRequest` (lines 83–87)

```python
class UserRoleChangeRequest(BackendSchemaBase):
    """PATCH /api/v1/users/{user_id}/role body (Phase 112 TEAM-01)."""
    role: Role
```

---

### `apps/admin-app/src/features/users/api.ts` — add `useChangeUserRole`

**Analog:** `useDeactivateUser` (lines 96–105) in same file — exact same useMutation shape

**Pattern:**
```typescript
/**
 * Change a staff user's role (owner-only).
 * PATCH /api/v1/users/{user_id}/role
 * May throw ApiError with code: cannot_change_own_role | cannot_change_last_owner_role
 */
export function useChangeUserRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, role }: { id: string; role: 'owner' | 'reception' }) =>
      staffRequest('patch', '/api/v1/users/{user_id}/role', {
        params: { user_id: id },
        body: { role },
      }),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: usersKeys.lists() });
    },
  });
}
```

Add to exports. `staffRequest` auto-attaches `X-CSRF-Token` for PATCH.

---

### `apps/admin-app/src/features/payments/api.ts` — add `useRefundPayment`

**Analog:** `useDeactivateUser` in `features/users/api.ts` (lines 96–105); `paymentsKeys` factory already in this file

**Pattern:**
```typescript
/**
 * Refund a payment by payment id (owner-only, REFUND + FINANCE permission).
 * POST /api/v1/payments/{payment_id}/refund
 * Returns new refund Payment row.
 * Invalidates paymentsKeys.lists() (cashbox + finance ledger re-render).
 */
export function useRefundPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ paymentId, amountKopecks, reason }: {
      paymentId: string;
      amountKopecks: number;
      reason: string;
    }) => {
      const raw = await staffRequest('post', '/api/v1/payments/{payment_id}/refund', {
        params: { payment_id: paymentId },
        body: { amountKopecks, reason },
      });
      return PaymentsListResponseSchema.parse ...  // or a single PaymentResponseSchema
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: paymentsKeys.lists() });
    },
  });
}
```

`paymentsKeys.lists()` invalidation covers both cashbox (uses `usePaymentsLedger`) and finance table — broad but correct (matches existing cashbox convention).

---

### `apps/admin-app/src/pages/cashbox/components/TransactionsCard.tsx` — add refund action

**Analog:** `InviteModal` + `UserRowActions` DropdownMenu in `SectionsBottom.tsx` (lines 570–959)

**Key patterns to copy:**

Refund modal — AdaptiveModal with amount field + reason textarea (analog: `InviteModal` lines 682–753):
```typescript
// Modal structure (copy AdaptiveModal wrapper from InviteModal):
<AdaptiveModal
  open={open}
  onOpenChange={handleOpenChange}
  title="Оформить возврат"
  icon={<IconChip tone="warn" icon={Undo2} />}
  description={`${payment.id.slice(-6)} · ${formatRub(payment.amountKopecks / 100)}`}
  footerActions={
    <>
      <ModalButton variant="ghost" disabled={submitting} onClick={() => handleOpenChange(false)}>
        Отмена
      </ModalButton>
      <ModalButton variant="danger" disabled={!isValid || submitting} onClick={handleSubmit}>
        Вернуть {formatRub(amountKopecks / 100)}
      </ModalButton>
    </>
  }
>
```

Amount field: pre-filled with `payment.amountKopecks / 100`, editable input (numeric), validated ≤ original.

Reason field: `<textarea>` with `minLength={3}` (free-text per D-112 decision, not a select).

Owner gate on refund action — hide the button entirely for reception (not disabled):
```typescript
// In PaymentRow, only render the action button when can(role, 'refund', 'finance')
// and payment.refundOf == null (not already a refund row)
{canRefund && !isRefund && (
  <button type="button" onClick={() => openRefundModal(payment)}>
    Возврат
  </button>
)}
```

`role` prop flows down from `CashboxPage` → `TransactionsCard` → `PaymentRow` (same pattern as `useUsers(filter, role)` in users feature).

Error handling toast (copy `handle409` from SectionsBottom.tsx lines 760–774):
```typescript
function handleRefundError(err: unknown) {
  if (err instanceof ApiError) {
    if (err.code === 'already_refunded') {
      toast.error('Возврат уже оформлен');
    } else if (err.code === 'over_refund') {
      toast.error('Сумма возврата превышает сумму платежа');
    } else if (err.code === 'cannot_refund_refund') {
      toast.error('Нельзя оформить возврат на возврат');
    } else {
      toast.error('Не удалось оформить возврат. Попробуйте ещё раз.');
    }
  } else {
    toast.error('Не удалось оформить возврат. Попробуйте ещё раз.');
  }
}
```

---

### `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` — add change-role modal

**Analog:** `InviteModal` in same file (lines 570–754), `UserRowActions` DropdownMenu (lines 776–959)

**Role picker pattern** (copy from InviteModal form lines 728–751):
```typescript
// Pill-style role toggle — same markup as InviteModal role picker
<div className="inline-flex flex-wrap gap-0.5 rounded-full border-[0.5px] border-border bg-surface-2 p-[3px]">
  {(['reception', 'owner'] as const).map((r) => {
    const active = selectedRole === r;
    return (
      <button key={r} type="button" disabled={submitting}
        onClick={() => setSelectedRole(r)}
        className={cn(
          'h-[28px] rounded-full px-3 text-[12.5px] font-semibold ...',
          active ? 'bg-fg text-bg dark:bg-primary dark:text-[#06120c]' : 'text-fg-muted hover:text-fg',
        )}>
        {ROLE_LABEL[r]}
      </button>
    );
  })}
</div>
```

Add "Изменить роль" `DropdownMenuItem` in `UserRowActions` for `status === 'active' && !isSelf` branch (lines 791–853). Opens `ChangeRoleModal` via local `useState(false)` (same approach as `inviteOpen` at line 969).

Error code mapping for `handle409`-style function:
- `cannot_change_own_role` → `'Нельзя изменить собственную роль'`
- `cannot_change_last_owner_role` → `'Нельзя снять роль у единственного владельца'`

---

## Shared Patterns

### RBAC-04 Dependency Ordering (all backend mutation endpoints)
**Source:** `apps/backend/app/modules/users/router.py` lines 22-25 (docstring) and lines 123-126, 140-143
**Apply to:** `POST /payments/{payment_id}/refund` and `PATCH /users/{user_id}/role`
```python
# CORRECT order in function signature — require_permission BEFORE verify_csrf
actor: Annotated[CurrentUser, Depends(require_permission(Action.X, Resource.Y))],
_csrf: Annotated[None, Depends(verify_csrf)],
```

### Append-only + SVC001 pattern (payments service)
**Source:** `apps/backend/app/modules/payments/service.py` lines 1-24, lines 94, 166
**Apply to:** new `refund_arbitrary_payment` function
- Mark with `# noqa: SVC001 caller-owns-txn` when the router owns commit
- Actually for the new refund endpoint the router IS the orchestrator — the service should call `session.commit()` itself (unlike membership/PT refund where memberships.service is the orchestrator)
- Guidance: match the pattern of `deactivate_user` in users/service.py (line 302) — service owns commit for standalone endpoints

### Audit emit — flat kwargs
**Source:** `apps/backend/app/modules/users/service.py` lines 291-300, 319-327
**Apply to:** both new service functions
```python
await audit.emit(
    session,
    "event_name",
    actor_user_id=actor.id,
    resource_type="...",
    resource_id=resource_id,
    audit_correlation_id=None,  # IN-01 — terminal event, no downstream chain
    # ... flat domain fields, UUIDs as str(uuid), datetimes as .isoformat()
)
await session.flush()
await session.commit()
```

### staffRequest + onSettled invalidation (frontend hooks)
**Source:** `apps/admin-app/src/features/users/api.ts` lines 96-105
**Apply to:** `useChangeUserRole`, `useRefundPayment`
```typescript
return useMutation({
  mutationFn: (...) => staffRequest('patch', '/api/v1/...', { params: ..., body: ... }),
  onSettled: () => {
    void qc.invalidateQueries({ queryKey: xKeys.lists() });
  },
});
```
`staffRequest` auto-attaches `X-CSRF-Token` for all non-GET verbs.

### ApiError instanceof guard + toast mapping
**Source:** `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` lines 760-774
**Apply to:** refund modal `onError`, role-change modal `onError`
```typescript
if (err instanceof ApiError) {
  // switch on err.code for domain-typed toasts
} else {
  toast.error('Не удалось выполнить действие. Попробуйте ещё раз.');
}
```

### AdaptiveModal form structure
**Source:** `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` lines 682-753 (InviteModal form phase)
**Apply to:** `ChangeRoleModal`, refund modal in `TransactionsCard` and Finance table
- `IconChip` in `icon` prop, `description` prop for sub-caption
- `footerActions` with ghost Cancel + primary/danger Confirm
- Local `useState` for form fields + `submitting: boolean`
- Reset state on close via `setTimeout(..., 300)` after dialog animation

---

## No Analog Found

All files have close analogs. No new domain patterns without precedent.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/users/`, `apps/backend/app/modules/payments/`, `apps/backend/app/core/`, `apps/admin-app/src/features/users/`, `apps/admin-app/src/features/payments/`, `apps/admin-app/src/pages/settings/`, `apps/admin-app/src/pages/cashbox/`, `apps/admin-app/src/pages/finance/`
**Files scanned:** 18
**Pattern extraction date:** 2026-06-15
