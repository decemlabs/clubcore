/**
 * SubscriptionModal — membership lifecycle dialogs (Phase 101-03 MEM-02/MEM-03).
 *
 * Wire-only update (no visual redesign):
 *  - CreateScreen → useSellMembership + real plans from usePlans()
 *  - RenewScreen  → useRenewMembership (removed multi-period picker)
 *  - FreezeScreen → useFreezeMembership optimistic (removed chip duration picker)
 *  - UnfreezeScreen → useUnfreezeMembership optimistic
 *  - CancelScreen → useCancelMembership; HIDDEN for reception via can()
 *  - HistoryScreen → read-only (unchanged, future Phase)
 *  - RefundScreen → NEW: useRefundMembership, required reason, no amount field
 *
 * Submitting state (all dialogs): primary + ghost buttons disabled, primary shows spinner.
 * Error state (all dialogs): inline Callout tone="danger" below fields; dialog stays open.
 * Success (all dialogs): close + toast (per UI-SPEC Copywriting Contract).
 */
import { useEffect, useState } from 'react';
import { cn } from '@/lib/cn';
import { formatRub, formatDateRu } from '@/lib/format';
import { useSession } from '@/features/auth/api';
import { can } from '@/shared/session/can';
import { usePlans } from '@/features/plans/api';
import {
  useSellMembership,
  useFreezeMembership,
  useUnfreezeMembership,
  useRenewMembership,
  useCancelMembership,
  useRefundMembership,
  ApiError,
} from '@/features/memberships/api';
import {
  CircleX,
  CreditCard,
  History,
  Loader2,
  ReceiptText,
  RefreshCw,
  Snowflake,
  Sun,
  TriangleAlert,
} from '@/components/icons';
import type { SubscriptionScreen } from './modals-context';
import { AdaptiveModal } from './AdaptiveModal';
import { Callout, Field, IconChip, ModalButton, ModalTextarea, StatRow } from './fields';

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

type MembershipPayload = {
  id: string;
  clientId: string;
  paidAmountKopecks: number;
  paidAt?: string | null;
  planSnapshot: { name: string };
  endDate: string;
  freezeDaysRemaining?: number | null;
  currentFreezePeriod?: {
    id: string;
    startedAt: string;
    startedBy: string;
    endedAt: string | null;
    endedBy: string | null;
  } | null;
};

type ScreenProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  clientName?: string;
  membershipId?: string;
  clientId?: string;
  membership?: MembershipPayload;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ErrorCallout({ error }: { error: Error | null }) {
  if (!error) return null;
  const msg =
    error instanceof ApiError
      ? error.message
      : 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.';
  return (
    <div className="mt-3.5">
      <Callout tone="danger" icon={TriangleAlert}>
        {msg}
      </Callout>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CreateScreen (Sell membership)
// ---------------------------------------------------------------------------

function CreateScreen({ open, onOpenChange, clientId, clientName }: ScreenProps) {
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');
  const [notes, setNotes] = useState('');
  const plansQuery = usePlans({ active: true });
  const sellMutation = useSellMembership();

  useEffect(() => {
    if (open) {
      setSelectedPlanId('');
      setNotes('');
      sellMutation.reset();
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const plans = plansQuery.data?.items ?? [];
  const selectedPlan = plans.find((p) => p.id === selectedPlanId);
  const isPending = sellMutation.isPending;

  function handleSubmit() {
    if (!clientId || !selectedPlanId) return;
    sellMutation.mutate(
      { clientId, planId: selectedPlanId, notes: notes.trim() || undefined },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      size="wide"
      icon={<IconChip icon={CreditCard} />}
      title="Оформить абонемент"
      description={
        clientName
          ? `${clientName} · выберите тариф и примите оплату`
          : 'Выберите тариф и примите оплату'
      }
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton disabled={isPending || !selectedPlanId || !clientId} onClick={handleSubmit}>
            {isPending ? (
              <>
                <Loader2 className="size-[18px] animate-spin" />
                Обработка…
              </>
            ) : (
              'Создать и принять оплату'
            )}
          </ModalButton>
        </>
      }
    >
      <Field label="Тариф">
        {plansQuery.isPending ? (
          <div className="h-[42px] animate-pulse rounded-xl bg-surface-3" />
        ) : (
          <select
            value={selectedPlanId}
            onChange={(e) => setSelectedPlanId(e.target.value)}
            disabled={isPending}
            className="w-full h-[42px] cursor-pointer appearance-none rounded-xl border-[0.5px] border-border bg-surface-2 px-3.5 pr-9 text-sm text-fg outline-none transition-colors focus:border-primary focus:bg-surface focus:shadow-[0_0_0_3px_var(--primary-soft)]"
          >
            <option value="">Выберите тариф…</option>
            {plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {formatRub(p.priceKopecks)}
              </option>
            ))}
          </select>
        )}
      </Field>
      {selectedPlan ? (
        <StatRow label="К оплате" value={formatRub(selectedPlan.priceKopecks)} accent />
      ) : null}
      <Field label="Заметка" optional>
        <ModalTextarea
          placeholder="Необязательно"
          value={notes}
          disabled={isPending}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
        />
      </Field>
      <ErrorCallout error={sellMutation.error} />
    </AdaptiveModal>
  );
}

// ---------------------------------------------------------------------------
// RenewScreen
// ---------------------------------------------------------------------------

function RenewScreen({
  open,
  onOpenChange,
  clientName,
  membershipId,
  clientId,
  membership,
}: ScreenProps) {
  const renewMutation = useRenewMembership();

  useEffect(() => {
    if (open) renewMutation.reset();
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const isPending = renewMutation.isPending;

  function handleSubmit() {
    if (!membershipId || !clientId) return;
    renewMutation.mutate(
      { membershipId, clientId },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      icon={<IconChip icon={RefreshCw} />}
      title="Продлить абонемент"
      description={
        membership
          ? `${clientName ?? ''} · «${membership.planSnapshot.name}»`
          : (clientName ?? undefined)
      }
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton disabled={isPending || !membershipId} onClick={handleSubmit}>
            {isPending ? (
              <>
                <Loader2 className="size-[18px] animate-spin" />
                Обработка…
              </>
            ) : (
              'Продлить'
            )}
          </ModalButton>
        </>
      }
    >
      {membership ? (
        <StatRow
          label="Текущая дата окончания"
          value={formatDateRu(membership.endDate, 'd MMMM yyyy')}
          accent
        />
      ) : null}
      <div className="mt-3.5">
        <Callout icon={TriangleAlert} tone="warn">
          Срок действия абонемента будет продлён на один период тарифа.
        </Callout>
      </div>
      <ErrorCallout error={renewMutation.error} />
    </AdaptiveModal>
  );
}

// ---------------------------------------------------------------------------
// FreezeScreen
// ---------------------------------------------------------------------------

function FreezeScreen({
  open,
  onOpenChange,
  clientName,
  membershipId,
  clientId,
  membership,
}: ScreenProps) {
  const freezeMutation = useFreezeMembership();

  useEffect(() => {
    if (open) freezeMutation.reset();
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const isPending = freezeMutation.isPending;

  function handleSubmit() {
    if (!membershipId || !clientId) return;
    freezeMutation.mutate(
      { membershipId, clientId },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      icon={<IconChip tone="indigo" icon={Snowflake} />}
      title="Заморозить абонемент"
      description={
        membership
          ? `${clientName ?? ''} · «${membership.planSnapshot.name}»`
          : 'Срок продлится на дни заморозки'
      }
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton disabled={isPending || !membershipId} onClick={handleSubmit}>
            {isPending ? (
              <>
                <Loader2 className="size-[18px] animate-spin" />
                Обработка…
              </>
            ) : (
              'Заморозить'
            )}
          </ModalButton>
        </>
      }
    >
      {membership?.freezeDaysRemaining != null ? (
        <StatRow
          label="Доступно дней заморозки"
          value={String(membership.freezeDaysRemaining)}
          accent
        />
      ) : null}
      <div className="mt-3.5">
        <Callout tone="accent" icon={TriangleAlert}>
          Срок абонемента продлится на дни заморозки. Разморозить можно досрочно в любой момент.
        </Callout>
      </div>
      <ErrorCallout error={freezeMutation.error} />
    </AdaptiveModal>
  );
}

// ---------------------------------------------------------------------------
// UnfreezeScreen
// ---------------------------------------------------------------------------

function UnfreezeScreen({
  open,
  onOpenChange,
  clientName,
  membershipId,
  clientId,
  membership,
}: ScreenProps) {
  const unfreezeMutation = useUnfreezeMembership();

  useEffect(() => {
    if (open) unfreezeMutation.reset();
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const isPending = unfreezeMutation.isPending;
  const fp = membership?.currentFreezePeriod;

  function handleSubmit() {
    if (!membershipId || !clientId) return;
    unfreezeMutation.mutate(
      { membershipId, clientId },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      icon={<IconChip icon={Sun} />}
      title="Разморозить абонемент"
      description={
        membership
          ? `${clientName ?? ''} · «${membership.planSnapshot.name}»`
          : (clientName ?? undefined)
      }
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton disabled={isPending || !membershipId} onClick={handleSubmit}>
            {isPending ? (
              <>
                <Loader2 className="size-[18px] animate-spin" />
                Обработка…
              </>
            ) : (
              'Разморозить сейчас'
            )}
          </ModalButton>
        </>
      }
    >
      {fp ? (
        <div className="mt-1 flex items-center gap-3.5 rounded-xl bg-indigo-500/15 px-3.5 py-3.5">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-indigo-500/20 text-indigo-600 dark:text-indigo-300">
            <Snowflake className="size-[18px]" />
          </span>
          <div>
            <div className="text-[13.5px] font-semibold text-indigo-600 dark:text-indigo-300">
              Заморожен с {formatDateRu(fp.startedAt, 'd MMMM yyyy')}
            </div>
            {fp.endedAt ? (
              <div className="mt-0.5 text-xs text-indigo-600/80 dark:text-indigo-300/80">
                До {formatDateRu(fp.endedAt, 'd MMMM yyyy')}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
      <div className="mt-3.5">
        <Callout icon={TriangleAlert}>Абонемент станет активным сегодня.</Callout>
      </div>
      <ErrorCallout error={unfreezeMutation.error} />
    </AdaptiveModal>
  );
}

// ---------------------------------------------------------------------------
// CancelScreen (OWNER_ONLY — hidden for reception)
// ---------------------------------------------------------------------------

function CancelScreen({
  open,
  onOpenChange,
  clientName,
  membershipId,
  clientId,
  membership,
}: ScreenProps) {
  const [reason, setReason] = useState('');
  const cancelMutation = useCancelMembership();

  useEffect(() => {
    if (open) {
      setReason('');
      cancelMutation.reset();
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const isPending = cancelMutation.isPending;

  function handleSubmit() {
    if (!membershipId || !clientId) return;
    cancelMutation.mutate(
      { membershipId, body: reason.trim() ? { reason: reason.trim() } : {} },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      icon={<IconChip tone="danger" icon={CircleX} />}
      title="Отменить абонемент?"
      description={
        membership
          ? `${clientName ?? ''} · «${membership.planSnapshot.name}»`
          : (clientName ?? undefined)
      }
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Не отменять
          </ModalButton>
          <ModalButton
            variant="danger"
            disabled={isPending || !membershipId}
            onClick={handleSubmit}
          >
            {isPending ? (
              <>
                <Loader2 className="size-[18px] animate-spin" />
                Обработка…
              </>
            ) : (
              'Отменить абонемент'
            )}
          </ModalButton>
        </>
      }
    >
      <Field label="Причина отмены" optional>
        <ModalTextarea
          placeholder="Необязательно, до 500 символов"
          maxLength={500}
          value={reason}
          disabled={isPending}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
        />
      </Field>
      <Callout tone="danger" icon={TriangleAlert}>
        Абонемент станет неактивным сразу. Будущие записи в расписании <b>отменятся</b>. Действие
        необратимо.
      </Callout>
      <ErrorCallout error={cancelMutation.error} />
    </AdaptiveModal>
  );
}

// ---------------------------------------------------------------------------
// RefundScreen (NET-NEW — Phase 101-03)
// ---------------------------------------------------------------------------

function RefundScreen({ open, onOpenChange, clientName, membershipId, membership }: ScreenProps) {
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const refundMutation = useRefundMembership();

  useEffect(() => {
    if (open) {
      setReason('');
      setTouched(false);
      refundMutation.reset();
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const isPending = refundMutation.isPending;
  const reasonTrimmed = reason.trim();

  function handleSubmit() {
    setTouched(true);
    if (!reasonTrimmed || !membershipId) return;
    refundMutation.mutate(
      { membershipId, body: { reason: reasonTrimmed } },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      icon={<IconChip tone="danger" icon={ReceiptText} />}
      title="Оформить возврат"
      description={
        membership
          ? `${clientName ?? ''} · «${membership.planSnapshot.name}»`
          : (clientName ?? undefined)
      }
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton
            variant="danger"
            disabled={isPending || !reasonTrimmed}
            onClick={handleSubmit}
          >
            {isPending ? (
              <>
                <Loader2 className="size-[18px] animate-spin" />
                Обработка…
              </>
            ) : (
              `Вернуть ${membership ? formatRub(membership.paidAmountKopecks) : ''}`
            )}
          </ModalButton>
        </>
      }
    >
      <Callout tone="warn" icon={TriangleAlert}>
        Возврат полный и необратимый. Средства вернутся тем же способом, которым была принята
        оплата.
      </Callout>
      {membership ? (
        <>
          <StatRow label="Оплачено" value={formatRub(membership.paidAmountKopecks)} accent />
          {membership.paidAt ? (
            <StatRow label="Дата покупки" value={formatDateRu(membership.paidAt, 'd MMMM yyyy')} />
          ) : null}
        </>
      ) : null}
      <div className="mt-3.5">
        <Field label="Причина возврата" required>
          <textarea
            className={cn(
              'min-h-[80px] w-full resize-none rounded-[10px] border-[0.5px] border-border bg-surface-2 px-3 py-2.5 text-[13.5px] outline-none placeholder:text-fg-subtle',
              'focus:border-primary focus:ring-2 focus:ring-primary/20',
            )}
            maxLength={200}
            placeholder="Укажите причину возврата"
            value={reason}
            disabled={isPending}
            onChange={(e) => setReason(e.target.value)}
            onBlur={() => setTouched(true)}
          />
          <div className="mt-1 flex justify-between">
            {touched && reasonTrimmed.length === 0 ? (
              <span className="text-[12px] text-danger">Причина обязательна для возврата</span>
            ) : (
              <span />
            )}
            <span className="ml-auto text-[11.5px] tabular-nums text-fg-subtle">
              {reason.length}/200
            </span>
          </div>
        </Field>
      </div>
      <ErrorCallout error={refundMutation.error} />
    </AdaptiveModal>
  );
}

// ---------------------------------------------------------------------------
// HistoryScreen (placeholder — real endpoint deferred to a future phase)
// ---------------------------------------------------------------------------

function HistoryScreen({ open, onOpenChange, clientName }: ScreenProps) {
  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<IconChip icon={History} />}
      title="История абонемента"
      description={clientName ?? undefined}
      footerActions={<ModalButton onClick={() => onOpenChange(false)}>Закрыть</ModalButton>}
    >
      <div className="py-8 text-center text-[13px] text-fg-muted">
        История появится позже — эта функция будет доступна в следующей версии.
      </div>
    </AdaptiveModal>
  );
}

// ---------------------------------------------------------------------------
// Dispatcher
// ---------------------------------------------------------------------------

export function SubscriptionModal({
  open,
  onOpenChange,
  payload,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payload?: {
    screen?: SubscriptionScreen;
    clientName?: string;
    membershipId?: string;
    clientId?: string;
    membership?: MembershipPayload;
  };
}) {
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  const screen = payload?.screen ?? 'edit';
  const props: ScreenProps = {
    open,
    onOpenChange,
    clientName: payload?.clientName,
    membershipId: payload?.membershipId,
    clientId: payload?.clientId,
    membership: payload?.membership,
  };

  switch (screen) {
    case 'create':
      return <CreateScreen {...props} />;
    case 'renew':
      return <RenewScreen {...props} />;
    case 'freeze':
      return <FreezeScreen {...props} />;
    case 'unfreeze':
      return <UnfreezeScreen {...props} />;
    case 'cancel':
      // OWNER_ONLY: hide for reception (can() gating per T-101-09-CANCELPRIV)
      if (!can(role, 'cancel', 'memberships')) {
        return (
          <AdaptiveModal open={false} onOpenChange={onOpenChange} title="" footerActions={null}>
            <></>
          </AdaptiveModal>
        );
      }
      return <CancelScreen {...props} />;
    case 'refund':
      return <RefundScreen {...props} />;
    case 'history':
      return <HistoryScreen {...props} />;
    case 'edit':
    default:
      // edit screen: show placeholder (no backend edit endpoint in scope for Phase 101)
      return (
        <AdaptiveModal
          open={open}
          onOpenChange={onOpenChange}
          icon={<IconChip icon={CreditCard} />}
          title="Абонемент"
          description={payload?.clientName ?? undefined}
          footerActions={<ModalButton onClick={() => onOpenChange(false)}>Закрыть</ModalButton>}
        >
          <div className="py-4 text-center text-[13px] text-fg-muted">
            Редактирование абонемента доступно в следующей версии.
          </div>
        </AdaptiveModal>
      );
  }
}
