import { StatusPill as BaseStatusPill, type StatusTone } from '@/components/ui/StatusPill';
import type { ClientStatus } from '@/features/clients/types';

/** Доменный map: статус клиента → tone + подпись общей пилюли. */
const CLIENT_STATUS: Record<ClientStatus, { tone: StatusTone; label: string }> = {
  active: { tone: 'success', label: 'Активный' },
  expiring: { tone: 'warning', label: 'Истекает' },
  frozen: { tone: 'info', label: 'Заморожен' },
  lead: { tone: 'lead', label: 'Лид' },
  expired: { tone: 'danger', label: 'Истёк' },
};

/** Пилюля статуса клиента. `label` переопределяет текст по умолчанию. */
export function StatusPill({
  status,
  label,
  className,
}: {
  status: ClientStatus;
  label?: string;
  className?: string;
}) {
  const { tone, label: defaultLabel } = CLIENT_STATUS[status];
  return (
    <BaseStatusPill tone={tone} className={className}>
      {label ?? defaultLabel}
    </BaseStatusPill>
  );
}
