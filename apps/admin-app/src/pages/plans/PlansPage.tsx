/**
 * Plans page — wired to real membership-plans + pt-package-plans catalogs (Phase 101 MEM-01).
 *
 * Data sources:
 *   - Tariffs section: usePlans() → GET /api/v1/membership-plans (real data)
 *   - Addons section: usePtPackagePlans() → GET /api/v1/pt-package-plans (real data)
 *   - Sales chart + promos sections: plansPageData mock (unchanged, deferred to future phase)
 *
 * Permission gating (T-101-05-OWNERPLAN, T-101-06-403QUERY, T-101-07-IMMUTABLE):
 *   - Add/Edit/Delete buttons HIDDEN (not disabled) when can(role, 'edit'|'delete', resource) === false
 *   - 403 on query → EmptyState icon=Lock «Недостаточно прав» (neutral, not destructive)
 *   - 403 on mutation → Sonner toast.error (backend is the real authority)
 */
import { useRef, useState, type RefObject } from 'react'
import { toast } from 'sonner'
import { usePlans, useDeletePlan, ApiError } from '@/features/plans/api'
import { usePtPackagePlans, useDeletePtPackagePlan } from '@/features/pt-packages/api'
import { useSession } from '@/features/auth/api'
import { can } from '@/shared/session/can'
import { PageLoading, PageError } from '@/components/feedback/PageState'
import { EmptyState } from '@/components/feedback/EmptyState'
import type { PlanTab } from '@/features/plans/types'
import { plansPageData } from '@/mocks/plans'
import { SectionHead } from '@/components/layout/SectionHead'
import { Segmented } from '@/components/ui/Segmented'
import { Dumbbell, Lock, Plus, SquarePen, Tag, Trash2 } from '@/components/icons'
import { PlansPageHead } from './components/PlansPageHead'
import { PlansKpis } from './components/PlansKpis'
import { PlanFilterTabs } from './components/PlanFilterTabs'
import { SalesChart } from './components/SalesChart'
import { PromoCard } from './components/PromoCard'
import { SALES_UNIT_OPTIONS, type SalesUnit } from './components/sales-unit'
import { formatKopecks } from '@/lib/format'
import type { MembershipPlanData } from '@/features/plans/schemas'
import type { PtPackagePlanData } from '@/features/pt-packages/schemas'
import { PlanFormModal } from '@/components/modals/PlanFormModal'

const ADD_BTN =
  'inline-flex h-9 items-center gap-1.5 rounded-full border-[0.5px] border-border bg-surface px-3.5 text-[13px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

const ACTION =
  'inline-flex h-[30px] items-center gap-1.5 rounded-lg px-2.5 text-[12.5px] font-semibold transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

// ---------------------------------------------------------------------------
// Tariff card for REAL membership plan data
// ---------------------------------------------------------------------------

function MembershipPlanCard({
  plan,
  canEdit,
  canDelete,
  onEdit,
  onDelete,
}: {
  plan: MembershipPlanData
  canEdit: boolean
  canDelete: boolean
  onEdit: (plan: MembershipPlanData) => void
  onDelete: (plan: MembershipPlanData) => void
}) {
  return (
    <article className="flex flex-col overflow-hidden rounded-lg border-[0.5px] border-border bg-surface shadow-1">
      <div className="flex flex-1 flex-col px-[22px] pt-[22px]">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[18px] font-bold leading-tight">{plan.name}</div>
            <div className="mt-0.5 text-[12.5px] text-fg-subtle">
              {plan.durationDays} дней ·{' '}
              {plan.active ? (
                <span className="text-primary-deep dark:text-primary">В продаже</span>
              ) : (
                <span className="text-fg-muted">Архив</span>
              )}
            </div>
          </div>
          {!plan.active && (
            <span className="shrink-0 rounded-full bg-surface-3 px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-[0.3px] text-fg-muted">
              Архив
            </span>
          )}
        </div>

        <div className="mt-4 flex items-baseline gap-1">
          <span className="text-[34px] font-bold leading-none tabular-nums">
            {formatKopecks(plan.priceKopecks)}
          </span>
          <span className="text-[13px] text-fg-subtle">/ {plan.durationDays} дн.</span>
        </div>

        {plan.freezeDaysLimit != null && (
          <div className="mt-2 text-[12.5px] text-fg-muted">
            Заморозка до <b className="font-semibold text-fg">{plan.freezeDaysLimit}</b> дн.
          </div>
        )}
      </div>

      <div className="flex items-center gap-1 border-t-[0.5px] border-border px-[18px] py-3">
        {canEdit && (
          <button
            type="button"
            className={`${ACTION} text-fg`}
            onClick={() => onEdit(plan)}
          >
            <SquarePen className="size-3.5" />
            Изменить
          </button>
        )}
        {canDelete && (
          <button
            type="button"
            className={`${ACTION} ml-auto text-danger`}
            onClick={() => onDelete(plan)}
          >
            <Trash2 className="size-3.5" />
            Архив
          </button>
        )}
      </div>
    </article>
  )
}

// ---------------------------------------------------------------------------
// PT-Package plan row for REAL pt-package plan data
// ---------------------------------------------------------------------------

function PtPackagePlanRow({
  plan,
  canEdit,
  canDelete,
  onEdit,
  onDelete,
}: {
  plan: PtPackagePlanData
  canEdit: boolean
  canDelete: boolean
  onEdit: (plan: PtPackagePlanData) => void
  onDelete: (plan: PtPackagePlanData) => void
}) {
  const sessionCount = plan.sessionCount
  const sessionLabel =
    sessionCount === 1
      ? 'сеанс'
      : sessionCount < 5
        ? 'сеанса'
        : 'сеансов'

  return (
    <div className="grid grid-cols-[36px_minmax(0,1fr)_auto_auto] items-center gap-3.5 px-5 py-3.5 transition-colors hover:bg-surface-2 max-[740px]:grid-cols-[36px_minmax(0,1fr)_auto]">
      <span className="grid size-9 place-items-center rounded-[10px] bg-surface-3 text-fg">
        <Dumbbell className="size-[18px]" />
      </span>
      <div className="min-w-0">
        <div className="text-[14px] font-semibold">{plan.name}</div>
        <div className="mt-0.5 text-[12px] text-fg-muted">
          {sessionCount} {sessionLabel}
          {plan.validityDays != null && ` · срок ${plan.validityDays} дн.`}
          {!plan.active && ' · Архив'}
        </div>
      </div>
      <div className="whitespace-nowrap text-right">
        <div className="text-[14px] font-bold tabular-nums">{formatKopecks(plan.priceKopecks)}</div>
        <div className="text-[11px] text-fg-subtle">за пакет</div>
      </div>
      <div className="flex items-center gap-1 max-[740px]:hidden">
        {canEdit && (
          <button
            type="button"
            className={`${ACTION} text-fg`}
            onClick={() => onEdit(plan)}
          >
            <SquarePen className="size-3.5" />
          </button>
        )}
        {canDelete && (
          <button
            type="button"
            className={`${ACTION} text-danger`}
            onClick={() => onDelete(plan)}
          >
            <Trash2 className="size-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function PlansPage() {
  const session = useSession()
  const role = session.data?.role ?? 'reception'

  // Real data queries
  const plansQuery = usePlans()
  const ptPackagesQuery = usePtPackagePlans()

  // Mutations — delete plans; create/update wired via PlanFormModal (Phase 107-01)
  const deletePlan = useDeletePlan()
  const deletePtPlan = useDeletePtPackagePlan()

  // Permission checks — gate each entry point on the verb of the action it
  // performs (WR-03): create buttons → 'create', per-card edit → 'edit'.
  const canCreateMembershipPlans = can(role, 'create', 'membership-plans')
  const canEditMembershipPlans = can(role, 'edit', 'membership-plans')
  const canDeleteMembershipPlans = can(role, 'delete', 'membership-plans')
  const canCreatePtPackagePlans = can(role, 'create', 'pt-package-plans')
  const canEditPtPackagePlans = can(role, 'edit', 'pt-package-plans')
  const canDeletePtPackagePlans = can(role, 'delete', 'pt-package-plans')

  // Mock data for not-yet-wired sections (sales chart, promos, KPIs, page head)
  const mockData = plansPageData

  const [tab, setTab] = useState<PlanTab>('tariffs')
  const [salesUnit, setSalesUnit] = useState<SalesUnit>('count')
  const [planFormModal, setPlanFormModal] = useState<{
    open: boolean
    kind: 'membership' | 'pt-package'
    mode: 'create' | 'edit'
    plan?: MembershipPlanData | PtPackagePlanData
  }>({ open: false, kind: 'membership', mode: 'create' })

  const tariffsRef = useRef<HTMLElement>(null)
  const promosRef = useRef<HTMLElement>(null)
  const addonsRef = useRef<HTMLElement>(null)

  const sectionRef: Partial<Record<PlanTab, RefObject<HTMLElement>>> = {
    tariffs: tariffsRef,
    promos: promosRef,
    addons: addonsRef,
  }
  const handleTab = (next: PlanTab) => {
    setTab(next)
    sectionRef[next]?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // ── Plan CRUD handlers ──────────────────────────────────────────────────

  const handleCreatePlan = () =>
    setPlanFormModal({ open: true, kind: 'membership', mode: 'create' })

  const handleEditPlan = (plan: MembershipPlanData) =>
    setPlanFormModal({ open: true, kind: 'membership', mode: 'edit', plan })

  const handleDeletePlan = (plan: MembershipPlanData) => {
    deletePlan.mutate(plan.id, {
      onSuccess: () => toast.success('Тариф архивирован', { description: plan.name }),
      onError: (err) => {
        if (err instanceof ApiError && err.code === 'forbidden') {
          toast.error('Недостаточно прав', {
            description: 'Это действие доступно только владельцу.',
          })
        } else {
          toast.error('Не удалось архивировать тариф')
        }
      },
    })
  }

  const handleCreatePtPlan = () =>
    setPlanFormModal({ open: true, kind: 'pt-package', mode: 'create' })

  const handleEditPtPlan = (plan: PtPackagePlanData) =>
    setPlanFormModal({ open: true, kind: 'pt-package', mode: 'edit', plan })

  const handleDeletePtPlan = (plan: PtPackagePlanData) => {
    deletePtPlan.mutate(plan.id, {
      onSuccess: () => toast.success('Услуга архивирована', { description: plan.name }),
      onError: (err) => {
        if (err instanceof ApiError && err.code === 'forbidden') {
          toast.error('Недостаточно прав', {
            description: 'Это действие доступно только владельцу.',
          })
        } else {
          toast.error('Не удалось архивировать услугу')
        }
      },
    })
  }

  // ── 403 query → friendly EmptyState (T-101-06-403QUERY) ─────────────────

  const plansForbidden =
    plansQuery.isError &&
    plansQuery.error instanceof ApiError &&
    plansQuery.error.code === 'forbidden'

  const ptPackagesForbidden =
    ptPackagesQuery.isError &&
    ptPackagesQuery.error instanceof ApiError &&
    ptPackagesQuery.error.code === 'forbidden'

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7">
      <PlansPageHead summary={mockData.summary} />

      <PlansKpis kpis={mockData.kpis} />

      <PlanFilterTabs tabs={mockData.tabs} value={tab} onChange={handleTab} />

      {/* ── Тарифы (membership plans — real data) ── */}
      <section ref={tariffsRef} className="flex scroll-mt-24 flex-col gap-3.5">
        <SectionHead
          title="Тарифы"
          subtitle="Что показывается клиентам при оформлении и продлении"
          action={
            canCreateMembershipPlans ? (
              <button type="button" onClick={handleCreatePlan} className={ADD_BTN}>
                <Plus className="size-3.5" strokeWidth={2.4} />
                Добавить тариф
              </button>
            ) : null
          }
        />

        {plansQuery.isPending && <PageLoading />}

        {plansForbidden && (
          <EmptyState
            icon={Lock}
            title="Недостаточно прав"
            message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
          />
        )}

        {plansQuery.isError && !plansForbidden && (
          <PageError onRetry={() => void plansQuery.refetch()} />
        )}

        {plansQuery.isSuccess && plansQuery.data.items.length === 0 && (
          <EmptyState
            icon={Tag}
            title="Тарифов пока нет"
            message="Создайте первый тариф, чтобы продавать абонементы."
            action={
              canCreateMembershipPlans ? (
                <button type="button" onClick={handleCreatePlan} className={ADD_BTN}>
                  <Plus className="size-3.5" strokeWidth={2.4} />
                  Добавить тариф
                </button>
              ) : null
            }
          />
        )}

        {plansQuery.isSuccess && plansQuery.data.items.length > 0 && (
          <div className="@container">
            <div className="grid grid-cols-1 gap-4 @min-[640px]:grid-cols-2 @min-[1000px]:grid-cols-3">
              {plansQuery.data.items.map((plan) => (
                <MembershipPlanCard
                  key={plan.id}
                  plan={plan}
                  canEdit={canEditMembershipPlans}
                  canDelete={canDeleteMembershipPlans}
                  onEdit={handleEditPlan}
                  onDelete={handleDeletePlan}
                />
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ── Продажи по тарифам (mock — not wired in this plan) ── */}
      <section className="flex flex-col gap-3.5">
        <SectionHead
          title="Продажи по тарифам"
          subtitle="Последние 6 месяцев · количество оформленных абонементов"
          action={
            <Segmented
              variant="mini"
              options={SALES_UNIT_OPTIONS}
              value={salesUnit}
              onChange={setSalesUnit}
              ariaLabel="Единицы продаж"
            />
          }
        />
        <SalesChart data={mockData.sales} unit={salesUnit} />
      </section>

      {/* ── Скидки и акции (mock — not wired in this plan) ── */}
      <section ref={promosRef} className="flex scroll-mt-24 flex-col gap-3.5">
        <SectionHead
          title="Скидки и акции"
          subtitle="Активные предложения, видны клиентам в приложении"
          action={
            canEditMembershipPlans ? (
              <button type="button" onClick={() => toast('Создание акции')} className={ADD_BTN}>
                <Plus className="size-3.5" strokeWidth={2.4} />
                Создать акцию
              </button>
            ) : null
          }
        />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {mockData.promos.map((p) => (
            <PromoCard key={p.id} promo={p} />
          ))}
        </div>
      </section>

      {/* ── Доп. услуги (pt-package plans — real data) ── */}
      <section ref={addonsRef} className="flex scroll-mt-24 flex-col gap-3.5">
        <SectionHead
          title="Доп. услуги"
          subtitle="Пакеты персональных тренировок · продаются отдельно"
          action={
            canCreatePtPackagePlans ? (
              <button type="button" onClick={handleCreatePtPlan} className={ADD_BTN}>
                <Plus className="size-3.5" strokeWidth={2.4} />
                Добавить услугу
              </button>
            ) : null
          }
        />

        {ptPackagesQuery.isPending && <PageLoading />}

        {ptPackagesForbidden && (
          <EmptyState
            icon={Lock}
            title="Недостаточно прав"
            message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
          />
        )}

        {ptPackagesQuery.isError && !ptPackagesForbidden && (
          <PageError onRetry={() => void ptPackagesQuery.refetch()} />
        )}

        {ptPackagesQuery.isSuccess && ptPackagesQuery.data.items.length === 0 && (
          <EmptyState
            icon={Dumbbell}
            title="Доп. услуг пока нет"
            message="Добавьте первую услугу."
            action={
              canCreatePtPackagePlans ? (
                <button type="button" onClick={handleCreatePtPlan} className={ADD_BTN}>
                  <Plus className="size-3.5" strokeWidth={2.4} />
                  Добавить услугу
                </button>
              ) : null
            }
          />
        )}

        {ptPackagesQuery.isSuccess && ptPackagesQuery.data.items.length > 0 && (
          <div className="overflow-hidden rounded-lg border-[0.5px] border-border bg-surface shadow-1">
            {ptPackagesQuery.data.items.map((plan, i) => (
              <div
                key={plan.id}
                className={i > 0 ? 'border-t-[0.5px] border-border' : undefined}
              >
                <PtPackagePlanRow
                  plan={plan}
                  canEdit={canEditPtPackagePlans}
                  canDelete={canDeletePtPackagePlans}
                  onEdit={handleEditPtPlan}
                  onDelete={handleDeletePtPlan}
                />
              </div>
            ))}
          </div>
        )}
      </section>

      <PlanFormModal
        open={planFormModal.open}
        onOpenChange={(open) => setPlanFormModal((s) => ({ ...s, open }))}
        kind={planFormModal.kind}
        mode={planFormModal.mode}
        plan={planFormModal.plan}
      />
    </div>
  )
}
