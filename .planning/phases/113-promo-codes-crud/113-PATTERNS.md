# Phase 113: Promo Codes CRUD — Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 15 new/modified files
**Analogs found:** 15 / 15

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/promo_codes/router.py` | controller | request-response | `apps/backend/app/modules/users/router.py` | exact |
| `apps/backend/app/modules/promo_codes/schemas.py` | model/DTO | CRUD | `apps/backend/app/modules/users/schemas.py` | exact |
| `apps/backend/app/modules/promo_codes/service.py` (extend) | service | CRUD | `apps/backend/app/modules/users/repository.py` (service pattern) | role-match |
| `apps/backend/app/modules/promo_codes/repository.py` | repository | CRUD + aggregate | `apps/backend/app/modules/users/repository.py` | exact |
| `apps/backend/app/modules/promo_codes/models.py` (extend) | model | — | existing `PromoCode` model | exact |
| `apps/backend/app/core/permissions.py` (extend) | config | — | `apps/backend/app/core/permissions.py` | exact |
| `apps/backend/alembic/versions/0072_*.py` | migration | — | `alembic/versions/0050_clients_notif_prefs.py` | exact |
| `apps/backend/app/api/v1/router.py` (extend) | config | — | `apps/backend/app/api/v1/router.py` | exact |
| `apps/backend/tests/integration/test_rbac_parity.py` (extend) | test | — | existing parity test | exact |
| `apps/backend/tests/integration/promo_codes/` (NEW) | test | request-response | `apps/backend/tests/integration/` adjacent module tests | role-match |
| `apps/admin-app/src/features/promoCodes/api.ts` | hook | request-response | `apps/admin-app/src/features/users/api.ts` | exact |
| `apps/admin-app/src/features/promoCodes/schemas.ts` | model/DTO | — | `apps/admin-app/src/features/plans/schemas.ts` | exact |
| `apps/admin-app/src/pages/plans/PlansPage.tsx` (extend) | component | CRUD | existing PlansPage + pt-packages section pattern | exact |
| `apps/admin-app/src/pages/plans/components/PromoCard.tsx` (extend) | component | — | existing PromoCard + PromoCard action buttons | exact |
| `apps/admin-app/src/components/modals/PromoCodeModal.tsx` | component | CRUD | `apps/admin-app/src/components/modals/PlanFormModal.tsx` | exact |
| `apps/admin-app/src/shared/session/can.ts` (extend) | config | — | existing `can.ts` | exact |

---

## Pattern Assignments

### `apps/backend/app/modules/promo_codes/router.py` (controller, request-response)

**Analog:** `apps/backend/app/modules/users/router.py`

**Imports pattern** (users/router.py lines 42–74):
```python
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.promo_codes import service
from app.modules.promo_codes.schemas import (
    PromoCodeCreateRequest,
    PromoCodeUpdateRequest,
    PromoCodeListQuery,
    PromoCodeListItemResponse,
)

router = APIRouter(tags=["Promo Codes"])
```

**RBAC-04 ordering invariant** — `require_permission` BEFORE `verify_csrf` in every mutation signature (users/router.py lines 99–104, 124–129):
```python
# READ — no CSRF, just require_permission
async def list_promo_codes_endpoint(
    query: Annotated[PromoCodeListQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.LIST, Resource.PROMO_CODES))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[PromoCodeListItemResponse]]:

# WRITE — require_permission BEFORE verify_csrf (RBAC-04)
async def create_promo_code_endpoint(
    payload: PromoCodeCreateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.PROMO_CODES))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PromoCodeResponse]:
```

**204 No Content deactivate pattern** (users/router.py lines 119–132):
```python
@router.patch(
    "/{promo_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate promo code (soft — sets is_active=False)",
)
async def deactivate_promo_code_endpoint(
    promo_id: UUID,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.DELETE, Resource.PROMO_CODES))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.deactivate_promo_code(session, actor, promo_id)
    return None
```

**Error handling:** no per-endpoint try/except. All service-layer `AppError` subclasses bubble to the global exception handler registered in `app.core.exceptions`. See docstring pattern from users/router.py lines 28–39.

---

### `apps/backend/app/modules/promo_codes/schemas.py` (DTO, CRUD)

**Analog:** `apps/backend/app/modules/users/schemas.py`

**Base classes** (users/schemas.py lines 24–25):
```python
from app.core.pagination import PageQuery
from app.core.permissions import Role
from app.core.schemas import BackendSchemaBase, ResponseData

# Request DTOs inherit BackendSchemaBase (camelCase wire, extra='forbid')
class PromoCodeCreateRequest(BackendSchemaBase):
    code: str  # normalized to UPPER in service layer
    discount_type: Literal['percentage', 'fixed']
    discount_value: int  # kopecks for fixed; percent*100 for percentage
    max_uses: int | None = None
    per_client_limit: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    applicable_to: str | None = None
    description: str | None = None

# Response DTOs inherit ResponseData (adds from_attributes=True for ORM→DTO)
class PromoCodeListItemResponse(ResponseData):
    id: UUID
    code: str
    discount_type: str
    discount_value: int
    max_uses: int | None
    per_client_limit: int | None
    valid_from: datetime | None
    valid_until: datetime | None
    is_active: bool
    applicable_to: str | None
    description: str | None
    used_count: int  # aggregate from promo_redemptions
    created_at: datetime
```

**List query** — inherit `PageQuery` (users/schemas.py lines 35–43):
```python
class PromoCodeListQuery(PageQuery):
    active: bool | None = None  # None = all (active + inactive)
```

**Paginated list envelope** (pagination.py):
```python
# response_model=ResponseEnvelope[PaginatedData[PromoCodeListItemResponse]]
# Wire: { "data": { "items": [...], "total": N, "page": 1, "pageSize": 20 } }
```

---

### `apps/backend/app/modules/promo_codes/repository.py` (repository, CRUD + aggregate)

**Analog:** `apps/backend/app/modules/users/repository.py`

**No commit/flush discipline** — caller (service) owns the transactional moment (users/repository.py line 8).

**Paginated list with aggregate** (users/repository.py lines 101–165 adapted):
```python
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
from app.modules.promo_codes.models import PromoCode, PromoRedemption
from app.modules.promo_codes.schemas import PromoCodeListItemResponse, PromoCodeListQuery


async def list_promo_codes(
    session: AsyncSession, query: PromoCodeListQuery
) -> PaginatedData[PromoCodeListItemResponse]:
    predicates = [PromoCode.deleted_at.is_(None)]
    if query.active is not None:
        predicates.append(PromoCode.is_active.is_(query.active))

    # COUNT with predicate
    total = await session.scalar(
        select(func.count()).select_from(PromoCode).where(and_(*predicates))
    ) or 0

    # used_count aggregate via correlated subquery (mirrors cross-module raw SQL discipline)
    used_count_subq = (
        select(func.count())
        .select_from(PromoRedemption)
        .where(PromoRedemption.promo_code_id == PromoCode.id)
        .correlate(PromoCode)
        .scalar_subquery()
    )

    stmt = (
        select(PromoCode, used_count_subq.label("used_count"))
        .where(and_(*predicates))
        .order_by(PromoCode.created_at.desc(), PromoCode.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )

    rows = (await session.execute(stmt)).all()
    items = [
        PromoCodeListItemResponse(
            id=row.PromoCode.id,
            code=row.PromoCode.code,
            # ... all fields ...
            used_count=row.used_count,
        )
        for row in rows
    ]

    return PaginatedData.model_construct(
        items=items, total=total, page=query.page, page_size=query.page_size
    )
```

**Soft-deactivate** — mirrors `deactivate_user` in users/repository.py lines 248–275:
```python
async def deactivate_promo_code(session: AsyncSession, *, promo_id: UUID) -> None:
    await session.execute(
        update(PromoCode)
        .where(PromoCode.id == promo_id, PromoCode.deleted_at.is_(None))
        .values(is_active=False)
    )
```

---

### `apps/backend/app/modules/promo_codes/models.py` (extend — add description)

**Analog:** existing `PromoCode` model at `apps/backend/app/modules/promo_codes/models.py` lines 52–88.

Add one nullable `String` column after `applicable_to` (models.py line 67):
```python
# Add after the applicable_to column:
description: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

No new constraints needed — additive nullable column, no backfill.

---

### `apps/backend/alembic/versions/0072_*.py` (migration, additive column)

**Analog:** `apps/backend/alembic/versions/0050_clients_notif_prefs.py` (entire file — 39 lines, simplest add_column pattern)

**Full structure to copy:**
```python
"""promo_codes: add nullable description column (Phase 113).

Revision ID: 0072_promo_codes_description
Revises: 0071_seed_settings
Create Date: 2026-06-15

Additive migration — one nullable String(500) column on the promo_codes table.
ADD COLUMN is metadata-only on Postgres 16 — negligible lock window.
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0072_promo_codes_description"
down_revision: str | None = "0071_seed_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "promo_codes",
        sa.Column("description", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("promo_codes", "description")
```

---

### `apps/backend/app/core/permissions.py` (extend — add PROMO_CODES)

**Analog:** `apps/backend/app/core/permissions.py` (self — extend existing file)

**Resource enum addition** — follow kebab-value pattern for multi-word resources (lines 51–61):
```python
# In class Resource(StrEnum), after GYM:
PROMO_CODES = "promo-codes"  # Phase 113 — kebab (mirrors MEMBERSHIP_PLANS, SCHEDULE_SLOTS)
```

**OWNER_ONLY additions** — write actions only; LIST/VIEW allowed for both roles (lines 63–151):
```python
# Phase 113 — promo-codes write actions owner-only; LIST/VIEW allowed to reception.
(Action.CREATE, Resource.PROMO_CODES),
(Action.EDIT, Resource.PROMO_CODES),
(Action.DELETE, Resource.PROMO_CODES),  # deactivate maps to DELETE
```

**CRITICAL:** The comment block must note: `# Phase 113 — promo-codes CRUD: reception retains (LIST, PROMO_CODES). Count grows from 42 → 45.`

---

### `apps/backend/app/api/v1/router.py` (extend — register router)

**Analog:** `apps/backend/app/api/v1/router.py` lines 45–88 (existing include_router calls).

**Import** — add at top with other module imports (line 45 area):
```python
from app.modules.promo_codes.router import router as promo_codes_router
```

**Registration** — add in the v1 include_router block, alphabetically near `payments_router`:
```python
v1.include_router(promo_codes_router, prefix="/promo-codes")
```

---

### `apps/backend/tests/integration/test_rbac_parity.py` (extend)

**Analog:** `apps/backend/tests/integration/test_rbac_parity.py` lines 1–10 (count update pattern).

Update the docstring count from 42 → 45. No logic changes — the test reads both files at runtime; updating counts ensures the intent comment stays accurate. The regex `_PAIR_RE` and set-equality assertions are unchanged. The test will auto-pass once both `permissions.py` and `can.ts` are updated consistently.

---

### `apps/admin-app/src/features/promoCodes/api.ts` (hook, request-response)

**Analog:** `apps/admin-app/src/features/users/api.ts` (entire file — 188 lines)

**Key factory** (users/api.ts lines 37–42):
```typescript
export const promoCodesKeys = {
  all: ['promo-codes'] as const,
  lists: () => [...promoCodesKeys.all, 'list'] as const,
  list: (filter?: { active?: boolean; page?: number }) =>
    [...promoCodesKeys.lists(), filter] as const,
  detail: (id: string) => [...promoCodesKeys.all, 'detail', id] as const,
}
```

**Query hook** — `enabled: can(role, 'list', 'promo-codes')` mirrors (users/api.ts lines 52–64):
```typescript
export function usePromoCodes(opts: { active?: boolean; page?: number }, role: Role) {
  return useQuery({
    queryKey: promoCodesKeys.list(opts),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/promo-codes', { query: opts })
      return PromoCodesListResponseSchema.parse(raw).data
    },
    enabled: can(role, 'list', 'promo-codes'),
    staleTime: 30_000,
  })
}
```

**Mutation hooks** — onSettled invalidates lists() (users/api.ts lines 76–105):
```typescript
export function useCreatePromoCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: PromoCodeCreateInput) => {
      const raw = await staffRequest('post', '/api/v1/promo-codes', { body })
      return PromoCodeSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: () => { void qc.invalidateQueries({ queryKey: promoCodesKeys.lists() }) },
  })
}

export function useUpdatePromoCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: PromoCodeUpdateInput }) => {
      const raw = await staffRequest('patch', '/api/v1/promo-codes/{id}', { params: { id }, body })
      return PromoCodeSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: () => { void qc.invalidateQueries({ queryKey: promoCodesKeys.lists() }) },
  })
}

export function useDeactivatePromoCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      staffRequest('patch', '/api/v1/promo-codes/{id}/deactivate', { params: { id } }),
    onSettled: () => { void qc.invalidateQueries({ queryKey: promoCodesKeys.lists() }) },
  })
}

// Re-export for page/modal layers (D-100-03-APIERROR-REEXPORT)
export { ApiError }
```

---

### `apps/admin-app/src/features/promoCodes/schemas.ts` (DTO)

**Analog:** `apps/admin-app/src/features/plans/schemas.ts` (entire file — structure mirrors exactly)

**Wire shapes** (plans/schemas.ts lines 19–61):
```typescript
import { z } from 'zod'

export const PromoCodeSchema = z.object({
  id: z.string(),
  code: z.string(),
  discountType: z.enum(['percentage', 'fixed']),
  discountValue: z.number(),
  maxUses: z.number().nullable(),
  perClientLimit: z.number().nullable(),
  validFrom: z.string().nullable(),
  validUntil: z.string().nullable(),
  isActive: z.boolean(),
  applicableTo: z.string().nullable(),
  description: z.string().nullable(),
  usedCount: z.number(),
  createdAt: z.string(),
})
export type PromoCodeData = z.infer<typeof PromoCodeSchema>

// Paginated envelope — mirrors PlansListResponseSchema shape
export const PromoCodesListResponseSchema = z.object({
  data: z.object({
    items: z.array(PromoCodeSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
})

// Create input — all required fields
export const PromoCodeCreateSchema = z.object({
  code: z.string().min(1, 'Укажите код').max(32),
  discountType: z.enum(['percentage', 'fixed']),
  discountValue: z.number().int().min(1),
  maxUses: z.number().int().min(1).optional(),
  perClientLimit: z.number().int().min(1).optional(),
  validFrom: z.string().nullable().optional(),
  validUntil: z.string().nullable().optional(),
  applicableTo: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
})
export type PromoCodeCreateInput = z.infer<typeof PromoCodeCreateSchema>

// Update input — same shape as create (all fields optional on update)
export const PromoCodeUpdateSchema = PromoCodeCreateSchema.partial()
export type PromoCodeUpdateInput = z.infer<typeof PromoCodeUpdateSchema>
```

---

### `apps/admin-app/src/components/modals/PromoCodeModal.tsx` (component, CRUD form)

**Analog:** `apps/admin-app/src/components/modals/PlanFormModal.tsx` (entire file — 528 lines)

**Imports pattern** (PlanFormModal.tsx lines 21–38):
```typescript
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useCreatePromoCode, useUpdatePromoCode, ApiError } from '@/features/promoCodes/api'
import {
  PromoCodeCreateSchema,
  PromoCodeUpdateSchema,
  type PromoCodeData,
} from '@/features/promoCodes/schemas'
import { Tag, Loader2 } from '@/components/icons'
import { AdaptiveModal } from './AdaptiveModal'
import { ChipGroup, Field, FieldRow, IconChip, ModalButton, ModalInput, ModalTextarea, Section } from './fields'
```

**Props interface** (PlanFormModal.tsx lines 46–53):
```typescript
export interface PromoCodeModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: 'create' | 'edit'
  promo?: PromoCodeData
}
```

**useEffect reset-on-open** (PlanFormModal.tsx lines 150–175):
```typescript
useEffect(() => {
  if (open) {
    setSubmitAttempted(false)
    setFieldErrors({})
    createMutation.reset()
    updateMutation.reset()
    // Prefill fields from promo in edit mode
    setCode(promo?.code ?? '')
    setDiscountType(promo?.discountType ?? 'percentage')
    // ...etc
  }
}, [open]) // eslint-disable-line react-hooks/exhaustive-deps
```

**Submit pattern with Zod safeParse + onError field mapping** (PlanFormModal.tsx lines 178–212):
```typescript
function handleSubmit() {
  setSubmitAttempted(true)
  const raw = { code: code.trim().toUpperCase(), discountType, discountValue: parseDiscountValue(), ... }
  const result = (mode === 'create' ? PromoCodeCreateSchema : PromoCodeUpdateSchema).safeParse(raw)
  if (!result.success) {
    setFieldErrors(result.error.flatten().fieldErrors)
    return
  }
  setFieldErrors({})
  const mutation = mode === 'create' ? createMutation : updateMutation
  mutation.mutate(mode === 'create' ? result.data : { id: promo!.id, body: result.data }, {
    onSuccess: () => {
      onOpenChange(false)
      toast.success(mode === 'create' ? 'Промокод создан' : 'Промокод обновлён', { description: code.toUpperCase() })
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        if (err.code === 'promo_code_already_exists') {
          toast.error('Промокод с таким кодом уже существует')
        } else if (err.status === 422) {
          toast.error('Проверьте правильность заполнения полей')
        } else {
          toast.error('Не удалось сохранить промокод. Попробуйте ещё раз.')
        }
      }
    },
  })
}
```

**AdaptiveModal + IconChip header** (PlanFormModal.tsx lines 353–384):
```typescript
return (
  <AdaptiveModal
    open={open}
    onOpenChange={isPending ? () => {} : onOpenChange}
    size="default"
    icon={<IconChip tone="accent" icon={Tag} />}
    title={mode === 'create' ? 'Создать промокод' : 'Редактировать промокод'}
    description={mode === 'edit' && promo ? promo.code : undefined}
    footerActions={
      <>
        <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
          Отмена
        </ModalButton>
        <ModalButton disabled={isPending || !isRequiredValid} onClick={handleSubmit}>
          {isPending ? <><Loader2 className="size-[18px] animate-spin" />Обработка…</> : ctaLabel}
        </ModalButton>
      </>
    }
  >
    {/* Section + Field + ChipGroup + ModalInput + ModalTextarea body */}
  </AdaptiveModal>
)
```

**ChipGroup for discount type toggle** — `fields.tsx` provides `ChipGroup`. Usage:
```typescript
<ChipGroup
  options={[
    { value: 'percentage', label: 'Процент' },
    { value: 'fixed', label: 'Фикс. сумма' },
  ]}
  value={discountType}
  onChange={(v) => setDiscountType(v as 'percentage' | 'fixed')}
/>
```

---

### `apps/admin-app/src/pages/plans/PlansPage.tsx` (extend — wire promo section)

**Analog:** `apps/admin-app/src/pages/plans/PlansPage.tsx` lines 406–451 (pt-packages section — state handling with isPending/isError/isSuccess/empty/forbidden).

**Section wiring pattern** (PlansPage.tsx lines 420–450):
```typescript
// Replace mockData.promos.map with real query, mirroring the pt-packages section:
{promoCodesQuery.isPending && <PageLoading />}

{promoCodesForbidden && (
  <EmptyState icon={Lock} title="Недостаточно прав" message="..." />
)}

{promoCodesQuery.isError && !promoCodesForbidden && (
  <PageError onRetry={() => void promoCodesQuery.refetch()} />
)}

{promoCodesQuery.isSuccess && promoCodesQuery.data.items.length === 0 && (
  <EmptyState icon={Tag} title="Промокодов пока нет" message="..." action={...} />
)}

{promoCodesQuery.isSuccess && promoCodesQuery.data.items.length > 0 && (
  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
    {promoCodesQuery.data.items.map((p) => (
      <PromoCard key={p.id} promo={p} onEdit={...} onDeactivate={...} />
    ))}
  </div>
)}
```

**403 forbidden detection** — mirror existing pattern for ptPackages:
```typescript
const promoCodesForbidden =
  promoCodesQuery.isError &&
  promoCodesQuery.error instanceof ApiError &&
  promoCodesQuery.error.status === 403
```

**can() gate on create button** (PlansPage.tsx lines 387–397):
```typescript
// Replace canEditMembershipPlans check with:
const canCreatePromoCodes = can(role, 'create', 'promo-codes')
// In SectionHead action prop:
action={canCreatePromoCodes ? <button ... onClick={openCreatePromoModal}>...</button> : null}
```

---

### `apps/admin-app/src/pages/plans/components/PromoCard.tsx` (extend — wire actions)

**Analog:** `apps/admin-app/src/pages/plans/components/PromoCard.tsx` (existing — 75 lines)

**Updated props** — replace `{ promo: Promo }` (from `features/plans/types.ts`) with real data shape and action callbacks:
```typescript
import type { PromoCodeData } from '@/features/promoCodes/schemas'
import { can } from '@/shared/session/can'
import type { Role } from '@/shared/session/types'

interface PromoCardProps {
  promo: PromoCodeData
  role: Role
  onEdit?: (promo: PromoCodeData) => void
  onDeactivate?: (promo: PromoCodeData) => void
}
```

**Replace mock action buttons** (PromoCard.tsx lines 60–70) with owner-gated real actions:
```typescript
// Replace the mock actions.map with:
<div className="mt-2.5 flex flex-wrap gap-1">
  {can(role, 'edit', 'promo-codes') && (
    <button type="button" onClick={() => onEdit?.(p)} className={cn(ACTION, 'text-fg')}>
      Изменить
    </button>
  )}
  {can(role, 'delete', 'promo-codes') && p.isActive && (
    <button type="button" onClick={() => onDeactivate?.(p)} className={cn(ACTION, 'text-danger')}>
      Деактивировать
    </button>
  )}
</div>
```

**iconKind derivation** (replace `p.iconKind` from Promo type):
```typescript
const iconKind = p.discountType === 'percentage' ? 'percent' : 'discount'
const { Icon, cls } = ICON[iconKind]
```

**Deactivate via ConfirmModal** — caller (PlansPage) opens the existing ConfirmModal (ConfirmModal.tsx lines 12–92):
```typescript
// In PlansPage, passed as onDeactivate callback:
const handleDeactivate = (promo: PromoCodeData) => {
  openConfirm({
    title: 'Деактивировать промокод',
    message: `Промокод «${promo.code}» будет деактивирован. ...`,
    confirmLabel: 'Деактивировать',
    tone: 'danger',
    onConfirm: async () => {
      await deactivateMutation.mutateAsync(promo.id)
      toast.success('Промокод деактивирован', { description: promo.code })
    },
  })
}
```

---

### `apps/admin-app/src/shared/session/can.ts` (extend — add PROMO_CODES)

**Analog:** `apps/admin-app/src/shared/session/can.ts` (self — extend existing file)

**OWNER_ONLY additions** (can.ts lines 78–82, after the existing SETTINGS entry):
```typescript
// Phase 113 — promo-codes write actions owner-only; reception retains list/view.
// Mirror permissions.py PROMO_CODES block (count grows 42 → 45).
{ action: 'create', resource: 'promo-codes' },
{ action: 'edit', resource: 'promo-codes' },
{ action: 'delete', resource: 'promo-codes' },  // deactivate maps to 'delete'
```

**Resource type** — must also add `'promo-codes'` to the `Resource` union in `apps/admin-app/src/shared/session/registry.ts` (same file path pattern as the other kebab resources like `'audit-log'`, `'schedule-slots'`).

---

## Shared Patterns

### RBAC-04 Dependency Ordering
**Source:** `apps/backend/app/modules/users/router.py` docstring lines 19–25
**Apply to:** All write endpoints in `promo_codes/router.py`

In every mutation endpoint signature, `Depends(require_permission(...))` MUST appear BEFORE `Depends(verify_csrf)`. FastAPI resolves dependencies in declaration order — 401 (auth) must fire before 403 (CSRF).

```python
# CORRECT:
actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.PROMO_CODES))],
_csrf: Annotated[None, Depends(verify_csrf)],

# WRONG (do not do this):
_csrf: Annotated[None, Depends(verify_csrf)],
actor: Annotated[CurrentUser, Depends(require_permission(...))]
```

### AppError Exception Pattern (no per-endpoint try/except)
**Source:** `apps/backend/app/modules/users/router.py` docstring lines 28–39
**Apply to:** `promo_codes/router.py`, `promo_codes/service.py`

Service layer raises typed `AppError` subclasses (e.g. `PromoCodeNotFoundError`, `PromoCodeAlreadyExistsError`). These bubble uncaught through the router to the global handler. No per-endpoint try/except.

### No commit/flush in Repository
**Source:** `apps/backend/app/modules/users/repository.py` lines 7–11
**Apply to:** `promo_codes/repository.py`

Repository never calls `session.commit()` or `session.flush()`. The service layer (caller) owns the transactional moment so it can co-write audit rows in the same unit of work.

### PaginatedData.model_construct Pattern
**Source:** `apps/backend/app/modules/users/repository.py` lines 160–165
**Apply to:** `promo_codes/repository.py` list function

```python
return PaginatedData.model_construct(
    items=items,
    total=total,
    page=query.page,
    page_size=query.page_size,
)
```

### staffRequest + Schema.parse(raw).data
**Source:** `apps/admin-app/src/features/users/api.ts` lines 55–60
**Apply to:** `features/promoCodes/api.ts`

`staffRequest` auto-attaches X-CSRF-Token on POST/PATCH. No manual header needed.

```typescript
const raw = await staffRequest('get', '/api/v1/promo-codes', { query: opts })
return PromoCodesListResponseSchema.parse(raw).data
```

### Sonner toast + query invalidation on mutation settle
**Source:** `apps/admin-app/src/features/users/api.ts` lines 85–88
**Apply to:** `features/promoCodes/api.ts`, `PromoCodeModal.tsx`

```typescript
onSettled: () => { void qc.invalidateQueries({ queryKey: promoCodesKeys.lists() }) }
```

### ApiError re-export (ESLint boundary)
**Source:** `apps/admin-app/src/features/users/api.ts` line 187
**Apply to:** `features/promoCodes/api.ts`

```typescript
export { ApiError }
```

### Backend↔Frontend RBAC parity invariant
**Source:** `apps/backend/app/core/permissions.py` docstring lines 1–9
**Apply to:** Both `permissions.py` and `can.ts` must be updated atomically. The parity test (`test_rbac_parity.py`) asserts set equality at runtime — any drift fails CI.

---

## No Analog Found

All files have close analogs. No entries.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/`, `apps/backend/alembic/versions/`, `apps/backend/app/core/`, `apps/backend/app/api/`, `apps/admin-app/src/features/`, `apps/admin-app/src/components/modals/`, `apps/admin-app/src/pages/plans/`, `apps/admin-app/src/shared/session/`
**Files scanned:** ~20 analog files read
**Pattern extraction date:** 2026-06-15
