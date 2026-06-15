import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Gift, GraduationCap, Percent, Tag } from '@/components/icons';
import { can } from '@/shared/session/can';
import type { Role } from '@/shared/session/types';
import type { PromoCodeData } from '@/features/promoCodes/schemas';
import { formatKopecks } from '@/lib/format';

type PromoIconKind = 'discount' | 'gift' | 'student' | 'percent';

const ICON: Record<PromoIconKind, { Icon: LucideIcon; cls: string }> = {
  discount: { Icon: Tag, cls: 'bg-primary-soft text-primary-deep dark:text-primary' },
  gift: { Icon: Gift, cls: 'bg-lead-soft text-lead' },
  student: { Icon: GraduationCap, cls: 'bg-warning-soft text-warning-deep' },
  percent: { Icon: Percent, cls: 'bg-primary-soft text-primary-deep dark:text-primary' },
};

const ACTION =
  'inline-flex h-[30px] items-center rounded-lg px-2.5 text-[12.5px] font-semibold transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function StatusPill({ isActive }: { isActive: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full py-[3px] pl-[6px] pr-2 text-[10.5px] font-bold uppercase tracking-[0.3px]',
        isActive
          ? 'bg-primary-soft text-primary-deep dark:text-primary'
          : 'bg-surface-3 text-fg-muted',
      )}
    >
      <span
        className={cn(
          'size-1.5 rounded-full',
          isActive ? 'animate-pulse bg-primary-deep dark:bg-primary' : 'bg-fg-subtle',
        )}
      />
      {isActive ? 'Активен' : 'Неактивен'}
    </span>
  );
}

/** Форматирует окно действия промокода. */
function formatValidity(validFrom: string | null, validUntil: string | null): string {
  if (!validFrom && !validUntil) return 'бессрочно';
  const from = validFrom ? validFrom.slice(0, 10) : '—';
  const until = validUntil ? validUntil.slice(0, 10) : 'бессрочно';
  return `${from} – ${until}`;
}

interface PromoCardProps {
  promo: PromoCodeData;
  role: Role;
  onEdit?: (promo: PromoCodeData) => void;
  onDeactivate?: (promo: PromoCodeData) => void;
}

/** Карточка промокода: реальные данные из API, owner-gated действия. */
export function PromoCard({ promo: p, role, onEdit, onDeactivate }: PromoCardProps) {
  const iconKind: PromoIconKind = p.discountType === 'percentage' ? 'percent' : 'discount';
  const { Icon, cls } = ICON[iconKind];

  const discountDisplay =
    p.discountType === 'percentage'
      ? `${p.discountValue / 100}%`
      : formatKopecks(p.discountValue);

  const usageDisplay = `${p.usedCount} / ${p.maxUses != null ? String(p.maxUses) : '∞'}`;

  const validityDisplay = formatValidity(p.validFrom, p.validUntil);

  const limitDisplay = p.perClientLimit != null ? String(p.perClientLimit) : '—';

  return (
    <article className="flex gap-4 rounded-lg border-[0.5px] border-border bg-surface p-[18px] shadow-1">
      <span className={cn('grid size-11 shrink-0 place-items-center rounded-xl', cls)}>
        <Icon className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <div className="text-[14.5px] font-bold">
            {p.code}
            <code className="ml-1.5 rounded-[5px] bg-surface-3 px-1.5 py-0.5 font-mono text-[13px] font-semibold">
              {p.code}
            </code>
          </div>
          <StatusPill isActive={p.isActive} />
        </div>
        {p.description ? (
          <p className="mt-1 text-[12px] leading-relaxed text-fg-muted">{p.description}</p>
        ) : null}
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-fg-muted">
          <span>
            Скидка: <b className="font-semibold text-fg">{discountDisplay}</b>
          </span>
          <span>
            Использований: <b className="font-semibold text-fg">{usageDisplay}</b>
          </span>
          <span>
            Действует: <b className="font-semibold text-fg">{validityDisplay}</b>
          </span>
          <span>
            Лимит на клиента: <b className="font-semibold text-fg">{limitDisplay}</b>
          </span>
        </div>
        <div className="mt-2.5 flex flex-wrap gap-1">
          {can(role, 'edit', 'promo-codes') && (
            <button
              type="button"
              onClick={() => onEdit?.(p)}
              className={cn(ACTION, 'text-fg')}
            >
              Изменить
            </button>
          )}
          {can(role, 'delete', 'promo-codes') && p.isActive && (
            <button
              type="button"
              onClick={() => onDeactivate?.(p)}
              className={cn(ACTION, 'text-danger')}
            >
              Деактивировать
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
