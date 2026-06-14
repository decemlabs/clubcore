/**
 * AuditDetailModal — detail view for a real API AuditEvent (Phase 104-03 RPT-03).
 *
 * Threat T-104-07: payload JSONB rendered ONLY via JSON.stringify into escaped
 * text inside a <pre> element. Never uses innerHTML (XSS guard T-104-07).
 *
 * Accepts the real API AuditEvent from features/audit/schemas.ts.
 */
import { AdaptiveModal } from '@/components/modals/AdaptiveModal';
import { ModalButton } from '@/components/modals/fields';
import type { AuditEvent } from '@/features/audit/schemas';
import { ActionIcon } from './parts';
import { formatDateRu, formatTime } from '@/lib/format';

function MetaTile({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="rounded-xl border-[0.5px] border-border bg-surface-2 px-3 py-2.5">
      <div className="text-[11px] text-fg-subtle">{k}</div>
      <div
        className={
          mono ? 'mt-0.5 font-mono text-[12px] text-fg' : 'mt-0.5 text-[13px] font-semibold'
        }
      >
        {v}
      </div>
    </div>
  );
}

export function AuditDetailModal({
  event,
  open,
  onOpenChange,
}: {
  event: AuditEvent | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!event) return null;

  const dateLabel = formatDateRu(event.createdAt, 'd MMMM yyyy');
  const timeLabel = formatTime(event.createdAt);

  // Serialize payload to safe escaped text (T-104-07: never innerHTML)
  const payloadText =
    event.payload !== null
      ? JSON.stringify(event.payload, null, 2)
      : '(нет данных)';

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<ActionIcon action={event.action} size="lg" />}
      title={`${event.action} / ${event.resourceType}`}
      description={`Событие #${event.id}`}
      footerActions={
        <ModalButton onClick={() => onOpenChange(false)}>Закрыть</ModalButton>
      }
    >
      <div className="grid grid-cols-1 gap-2.5 min-[440px]:grid-cols-2">
        <MetaTile k="Сотрудник" v={event.actorEmailSnapshot ?? 'Система'} />
        <MetaTile k="Дата и время" v={`${dateLabel}, ${timeLabel}`} />
        {event.resourceType ? (
          <MetaTile k="Тип ресурса" v={event.resourceType} />
        ) : null}
        {event.resourceId ? (
          <MetaTile k="ID ресурса" v={event.resourceId} mono />
        ) : null}
      </div>

      {/* Payload — rendered as escaped text only (T-104-07 XSS guard) */}
      <div className="mb-2 mt-4 text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
        Payload
      </div>
      <div className="overflow-hidden rounded-xl border-[0.5px] border-border">
        <pre className="overflow-x-auto whitespace-pre-wrap break-all px-4 py-3 font-mono text-[11.5px] leading-[1.6] text-fg">
          {payloadText}
        </pre>
      </div>
    </AdaptiveModal>
  );
}
