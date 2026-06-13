import type { ReactNode } from 'react';
import { toast } from 'sonner';
import { AdaptiveModal } from '@/components/modals/AdaptiveModal';
import { ModalButton } from '@/components/modals/fields';
import type { AuditEvent } from '@/features/audit/types';
import { ActionIcon } from './parts';

function MetaTile({ k, v, mono }: { k: string; v: ReactNode; mono?: boolean }) {
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
  date,
  open,
  onOpenChange,
}: {
  event: AuditEvent | null;
  date: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!event) return null;
  const title = `${event.lead}${event.obj}${event.tail}`;

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={onOpenChange}
      icon={<ActionIcon action={event.action} size="lg" />}
      title={title}
      description={`Событие #${event.id}`}
      footerActions={
        <>
          <ModalButton variant="ghost" onClick={() => toast('Откат изменения')}>
            Откатить
          </ModalButton>
          <ModalButton onClick={() => onOpenChange(false)}>Закрыть</ModalButton>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-2.5 min-[440px]:grid-cols-2">
        <MetaTile k="Сотрудник" v={event.actor.name} />
        <MetaTile k="Дата и время" v={`${date}, ${event.time}`} />
        <MetaTile k="Объект" v={event.object} />
        <MetaTile k="IP-адрес" v={event.ip} mono />
      </div>

      <div className="mb-2 mt-4 text-[11px] font-bold uppercase tracking-[0.5px] text-fg-subtle">
        Что изменилось
      </div>
      <div className="overflow-hidden rounded-xl border-[0.5px] border-border">
        {event.diff.map((d) => (
          <div
            key={d.label}
            className="grid grid-cols-1 border-b-[0.5px] border-border text-[12.5px] last:border-b-0 min-[440px]:grid-cols-[120px_1fr]"
          >
            <div className="bg-surface-2 px-3 py-2.5 font-semibold text-fg-muted">{d.label}</div>
            <div className="flex flex-col gap-0.5 px-3 py-2.5">
              {d.old === '—' ? (
                <span className="text-fg-subtle">—</span>
              ) : (
                <span className="text-danger line-through">{d.old}</span>
              )}
              <span className="font-semibold text-primary-deep dark:text-primary">{d.new}</span>
            </div>
          </div>
        ))}
      </div>
    </AdaptiveModal>
  );
}
