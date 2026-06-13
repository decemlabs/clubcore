/**
 * PayoutsTab — wired to real /api/v1/payroll/* (Phase 102-04 TRN-02).
 *
 * Props: { trainerId: string } (read from TrainerData.id by TrainerPage)
 *
 * Gate order:
 *   1. Reception role → Lock EmptyState immediately (BEFORE any hook fires — T-102-PAY-RBAC)
 *   2. Owner → comp-config, preview→run, accruals list
 *
 * Money: integer kopecks on the wire; display = kopecks/100 (rubles) and bps/100 (%).
 * No Idempotency-Key for payroll endpoints (not required per backend contract).
 */
import { useState } from 'react';
import { toast } from 'sonner';
import { Lock, TriangleAlert, Wallet } from '@/components/icons';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Callout } from '@/components/ui/callout';
import { Skeleton } from '@/components/ui/skeleton';
import { ConfirmModal } from '@/components/modals/ConfirmModal';
import { Field, FieldRow, ModalInput, ModalButton, StatRow } from '@/components/modals/fields';
import { Panel, PanelBody, PanelHead } from './shared';
import { useSession } from '@/features/auth/api';
import { can } from '@/shared/session/can';
import { formatRub, formatDateRu } from '@/lib/format';
import { PayrollConfigInputSchema } from '@/features/payroll/schemas';
import {
  usePayrollConfig,
  useSetPayrollConfig,
  useAccrualPreview,
  useRunAccrual,
  useAccruals,
  useMarkAccrualPaid,
  ApiError,
} from '@/features/payroll/api';
import type { AccrualData } from '@/features/payroll/schemas';

// Helper: format kopecks as rubles string (₽)
function formatMoney(kopecks: number): string {
  return formatRub(kopecks / 100);
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface PayoutsTabProps {
  /** Trainer ID from TrainerData.id */
  trainerId: string;
}

// ---------------------------------------------------------------------------
// PayoutsTab
// ---------------------------------------------------------------------------

export function PayoutsTab({ trainerId }: PayoutsTabProps) {
  const session = useSession();

  // WR-03: While session is loading, show nothing — avoids flashing the Lock EmptyState
  // to an owner for the duration of the session fetch (50–200 ms). TrainerPage is already
  // behind PageLoading for the trainer data, so this window is narrow in practice.
  if (session.isPending) return null;

  const role = session.data?.role ?? 'reception';

  // ── T-102-PAY-RBAC: Reception gate BEFORE any hook fires ──────────────────
  if (!can(role, 'view', 'payroll')) {
    return (
      <EmptyState
        icon={Lock}
        title="Недостаточно прав"
        message="Раздел выплат доступен только владельцу."
      />
    );
  }

  // All payroll hooks are below this point — reception never reaches them
  return <OwnerPayoutsTab trainerId={trainerId} role={role} />;
}

// ---------------------------------------------------------------------------
// OwnerPayoutsTab — rendered only for owner role
// ---------------------------------------------------------------------------

function OwnerPayoutsTab({
  trainerId,
  role,
}: {
  trainerId: string;
  role: 'owner' | 'reception';
}) {
  // ── Comp-config query ──────────────────────────────────────────────────────
  const configQuery = usePayrollConfig(trainerId);
  const setConfig = useSetPayrollConfig();

  // Config editor local state
  const today = new Date().toISOString().slice(0, 10);
  const [feeRubles, setFeeRubles] = useState<string>('');
  const [commPct, setCommPct] = useState<string>('');
  const [effectiveFrom, setEffectiveFrom] = useState<string>(today);
  const [configErrors, setConfigErrors] = useState<Record<string, string>>({});

  // ── Preview→run state ─────────────────────────────────────────────────────
  const [periodStart, setPeriodStart] = useState<string>('');
  const [periodEnd, setPeriodEnd] = useState<string>('');
  const [previewEnabled, setPreviewEnabled] = useState(false);
  const [previewDismissed, setPreviewDismissed] = useState(false);

  const previewQuery = useAccrualPreview({
    trainerId,
    periodStart,
    periodEnd,
    enabled: previewEnabled && !!periodStart && !!periodEnd,
  });

  const runAccrual = useRunAccrual();

  // ── Accruals list ─────────────────────────────────────────────────────────
  const accrualsQuery = useAccruals(trainerId);

  // ── Mark-paid confirm state ───────────────────────────────────────────────
  const [confirmAccrual, setConfirmAccrual] = useState<AccrualData | null>(null);
  const markPaid = useMarkAccrualPaid();

  // ── Populate editor from loaded config ───────────────────────────────────
  const activeConfig = configQuery.data;
  const configMissing =
    configQuery.isError &&
    configQuery.error instanceof ApiError &&
    configQuery.error.code === 'comp_config_missing';

  // Pre-fill editor from current config when it loads (once)
  const [editorPreFilled, setEditorPreFilled] = useState(false);
  if (activeConfig && !editorPreFilled) {
    setFeeRubles(String(activeConfig.sessionFeeKopecks / 100));
    setCommPct(String(activeConfig.commissionPctBps / 100));
    setEffectiveFrom(activeConfig.effectiveFrom ?? today);
    setEditorPreFilled(true);
  }

  // ── Handlers ─────────────────────────────────────────────────────────────

  const handleSaveConfig = async () => {
    const input = {
      sessionFeeKopecks: Math.round(Number(feeRubles) * 100),
      commissionPctBps: Math.round(Number(commPct) * 100),
      effectiveFrom,
    };

    const validation = PayrollConfigInputSchema.safeParse(input);
    if (!validation.success) {
      const errs: Record<string, string> = {};
      for (const issue of validation.error.issues) {
        errs[issue.path[0] as string] = issue.message;
      }
      setConfigErrors(errs);
      return;
    }
    setConfigErrors({});

    try {
      await setConfig.mutateAsync({ trainerId, body: validation.data });
      setEditorPreFilled(false); // allow re-fill from new config
    } catch {
      // onError handled in hook (toast)
    }
  };

  const handlePreview = () => {
    setPreviewEnabled(true);
    setPreviewDismissed(false);
    void previewQuery.refetch();
  };

  const handleRunAccrual = async () => {
    try {
      await runAccrual.mutateAsync({ trainerId, periodStart, periodEnd });
      setPreviewEnabled(false);
      setPreviewDismissed(true);
    } catch {
      // 409 handled in hook (toast); clear preview on already_run
      if (
        runAccrual.error instanceof ApiError &&
        runAccrual.error.code === 'payroll_period_already_run'
      ) {
        setPreviewEnabled(false);
        setPreviewDismissed(true);
      }
    }
  };

  const handleMarkPaid = async () => {
    if (!confirmAccrual) return;
    try {
      await markPaid.mutateAsync({ accrualId: confirmAccrual.id, trainerId });
      toast.success('Выплата зафиксирована', { description: formatMoney(confirmAccrual.totalKopecks) });
    } catch {
      // 409 already_paid handled in hook (toast)
    } finally {
      setConfirmAccrual(null);
    }
  };

  // ── Preview 422 config missing ────────────────────────────────────────────
  const previewConfigMissing =
    previewQuery.isError &&
    previewQuery.error instanceof ApiError &&
    (previewQuery.error.code === 'comp_config_missing' ||
      previewQuery.error.code === 'unprocessable_entity');

  const preview = previewEnabled && !previewDismissed ? previewQuery.data : undefined;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-4">
      {/* ── Panel 1: Comp-config ─────────────────────────────────────────── */}
      <Panel>
        <PanelHead title="Настройки компенсации" />
        <PanelBody>
          {/* Loading */}
          {configQuery.isPending && (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-3/4" />
            </div>
          )}

          {/* 404 comp_config_missing */}
          {configMissing && (
            <Callout tone="warn" icon={TriangleAlert}>
              Настройки компенсации не заданы. Установите конфигурацию для просмотра расчётов.
            </Callout>
          )}

          {/* Current config read-only display */}
          {activeConfig && (
            <div className="mb-4">
              <StatRow
                label="Текущая ставка"
                value={formatMoney(activeConfig.sessionFeeKopecks)}
              />
              <StatRow
                label="Текущая комиссия"
                value={`${activeConfig.commissionPctBps / 100}%`}
              />
              <StatRow
                label="Действует с"
                value={formatDateRu(activeConfig.effectiveFrom)}
              />
            </div>
          )}

          {/* Config editor form — always shown for owner */}
          {(activeConfig || configMissing || !configQuery.isPending) && (
            <div className="mt-2">
              <FieldRow>
                <Field
                  label="Ставка за сессию"
                  hint={configErrors['sessionFeeKopecks']}
                >
                  <ModalInput
                    type="number"
                    inputMode="numeric"
                    suffix="₽"
                    placeholder="0"
                    value={feeRubles}
                    onChange={(e) => setFeeRubles(e.target.value)}
                    min="0"
                  />
                </Field>
                <Field
                  label="Комиссия"
                  hint={configErrors['commissionPctBps']}
                >
                  <ModalInput
                    type="number"
                    inputMode="numeric"
                    suffix="%"
                    placeholder="0"
                    value={commPct}
                    onChange={(e) => setCommPct(e.target.value)}
                    min="0"
                    max="100"
                    step="0.01"
                  />
                </Field>
              </FieldRow>
              <Field
                label="Действует с"
                hint={configErrors['effectiveFrom']}
              >
                <ModalInput
                  type="date"
                  value={effectiveFrom}
                  onChange={(e) => setEffectiveFrom(e.target.value)}
                />
              </Field>
              <div className="flex justify-end pt-1">
                <ModalButton
                  variant="ghost"
                  disabled={setConfig.isPending}
                  onClick={() => void handleSaveConfig()}
                >
                  Сохранить конфигурацию
                </ModalButton>
              </div>
            </div>
          )}
        </PanelBody>
      </Panel>

      {/* ── Panel 2: Preview → Run ──────────────────────────────────────────── */}
      <Panel>
        <PanelHead title="Расчёт зарплаты" />
        <PanelBody>
          {/* Period picker */}
          <FieldRow>
            <Field label="С">
              <ModalInput
                type="month"
                value={periodStart.slice(0, 7)}
                onChange={(e) => {
                  const ym = e.target.value; // YYYY-MM
                  if (ym) {
                    setPeriodStart(`${ym}-01`);
                    setPreviewEnabled(false);
                  }
                }}
              />
            </Field>
            <Field label="По">
              <ModalInput
                type="month"
                value={periodEnd.slice(0, 7)}
                onChange={(e) => {
                  const ym = e.target.value;
                  if (ym) {
                    // Last day of month
                    const [year, month] = ym.split('-').map(Number);
                    const lastDay = new Date(year!, month!, 0).getDate();
                    setPeriodEnd(`${ym}-${String(lastDay).padStart(2, '0')}`);
                    setPreviewEnabled(false);
                  }
                }}
              />
            </Field>
          </FieldRow>

          {/* Preview 422 config missing */}
          {previewConfigMissing && (
            <Callout tone="warn" icon={TriangleAlert}>
              Сначала задайте настройки компенсации.
            </Callout>
          )}

          {/* Preview loading */}
          {previewEnabled && previewQuery.isPending && (
            <div className="flex flex-col gap-2 py-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          )}

          {/* Preview result */}
          {preview && (
            <div className="mt-3">
              <StatRow label="Сессий" value={String(preview.sessionCount)} />
              <StatRow label="Ставка за сессии" value={formatMoney(preview.fixedKopecks)} />
              <StatRow label="Комиссия" value={formatMoney(preview.commissionKopecks)} />
              <div className="mt-2 flex items-center border-t border-border pt-3">
                <div className="text-sm font-bold">К начислению</div>
                <div className="ml-auto text-[20px] font-bold tabular-nums tracking-[-0.4px]">
                  {formatMoney(preview.totalKopecks)}
                </div>
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="mt-3 flex items-center gap-2.5">
            <ModalButton
              variant="ghost"
              disabled={!periodStart || !periodEnd || previewQuery.isFetching}
              onClick={handlePreview}
            >
              Просмотр
            </ModalButton>
            {preview && (
              <ModalButton
                variant="primary"
                disabled={runAccrual.isPending}
                onClick={() => void handleRunAccrual()}
              >
                Начислить
              </ModalButton>
            )}
          </div>
        </PanelBody>
      </Panel>

      {/* ── Panel 3: Accruals list ─────────────────────────────────────────── */}
      <Panel>
        <PanelHead title="История выплат" />
        <PanelBody>
          {/* Loading */}
          {accrualsQuery.isPending && (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-[52px] w-full rounded-xl" />
              <Skeleton className="h-[52px] w-full rounded-xl" />
              <Skeleton className="h-[52px] w-full rounded-xl" />
            </div>
          )}

          {/* Empty */}
          {accrualsQuery.isSuccess && accrualsQuery.data.items.length === 0 && (
            <EmptyState
              title="Начислений нет"
              message="Выплаты появятся здесь после первого начисления."
            />
          )}

          {/* Accruals list */}
          {accrualsQuery.isSuccess &&
            accrualsQuery.data.items.map((accrual) => (
              <AccrualRow
                key={accrual.id}
                accrual={accrual}
                canMarkPaid={can(role, 'edit', 'payroll')}
                onMarkPaid={() => setConfirmAccrual(accrual)}
              />
            ))}
        </PanelBody>
      </Panel>

      {/* ── Mark-paid ConfirmModal ─────────────────────────────────────────── */}
      <ConfirmModal
        open={confirmAccrual !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmAccrual(null);
        }}
        payload={
          confirmAccrual
            ? {
                title: 'Подтвердить выплату?',
                message: `Пометить начисление за ${formatDateRu(confirmAccrual.periodStart)} – ${formatDateRu(confirmAccrual.periodEnd)} как выплаченное. ${formatMoney(confirmAccrual.totalKopecks)}.`,
                tone: 'default',
                confirmLabel: 'Выплатить',
                cancelLabel: 'Отмена',
                onConfirm: handleMarkPaid,
              }
            : undefined
        }
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// AccrualRow
// ---------------------------------------------------------------------------

const STATUS_BADGE: Record<
  AccrualData['status'],
  { cls: string; label: string }
> = {
  pending: {
    cls: 'bg-warning-soft text-warning-deep',
    label: 'Ожидает выплаты',
  },
  paid: {
    cls: 'bg-primary-soft text-primary-deep dark:text-primary',
    label: 'Выплачено',
  },
  clawback: {
    cls: 'bg-danger-soft text-danger',
    label: 'Возврат',
  },
};

function AccrualRow({
  accrual,
  canMarkPaid,
  onMarkPaid,
}: {
  accrual: AccrualData;
  canMarkPaid: boolean;
  onMarkPaid: () => void;
}) {
  const badge = STATUS_BADGE[accrual.status];
  const periodLabel = `${formatDateRu(accrual.periodStart)} – ${formatDateRu(accrual.periodEnd)}`;

  return (
    <div className="flex items-center gap-3 border-b-[0.5px] border-border py-3 last:border-b-0">
      <span className="grid size-[34px] shrink-0 place-items-center rounded-[9px] bg-primary-soft text-primary-deep dark:text-primary">
        <Wallet className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-semibold">{periodLabel}</div>
        <div className="mt-px">
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${badge.cls}`}
          >
            {badge.label}
          </span>
        </div>
      </div>
      <div className="font-bold tabular-nums">{formatMoney(accrual.totalKopecks)}</div>
      {accrual.status === 'pending' && canMarkPaid && (
        <ModalButton variant="ghost" onClick={onMarkPaid}>
          Выплатить
        </ModalButton>
      )}
    </div>
  );
}
