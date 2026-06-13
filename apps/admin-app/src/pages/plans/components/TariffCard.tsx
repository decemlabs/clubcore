import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { useModals } from '@/components/modals/modals-context';
import { Check, SquarePen, X } from '@/components/icons';
import type { Tariff, TariffBadge } from '@/features/plans/types';

const ACTION =
  'inline-flex h-[30px] items-center gap-1.5 rounded-lg px-2.5 text-[12.5px] font-semibold transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function Badge({ badge }: { badge: TariffBadge }) {
  return (
    <span
      className={cn(
        'shrink-0 rounded-full px-[9px] py-1 text-[10.5px] font-extrabold uppercase tracking-[0.4px]',
        badge.kind === 'hit'
          ? 'bg-fg text-bg dark:bg-primary dark:text-[#06120c]'
          : 'bg-primary-soft text-primary-deep dark:text-primary',
      )}
    >
      {badge.label}
    </span>
  );
}

/** Карточка тарифа: цена, фичи, статистика, действия (full-bleed полосы). */
export function TariffCard({ tariff: t }: { tariff: Tariff }) {
  const { open } = useModals();
  const archive = () =>
    open('confirm', {
      confirm: {
        title: 'Архивировать тариф?',
        message: (
          <>
            «{t.name}» исчезнет из продажи. Действующие абонементы на этом тарифе продолжат работать.
          </>
        ),
        tone: 'danger',
        confirmLabel: 'Архивировать',
        onConfirm: () => {
          toast.success('Тариф архивирован', { description: t.name });
        },
      },
    });
  return (
    <article
      className={cn(
        'flex flex-col overflow-hidden rounded-lg border-[0.5px] bg-surface shadow-1',
        t.popular ? 'border-fg ring-1 ring-fg dark:border-primary dark:ring-primary' : 'border-border',
      )}
    >
      <div className="flex flex-1 flex-col px-[22px] pt-[22px]">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[18px] font-bold leading-tight">{t.name}</div>
            <div className="mt-0.5 text-[12.5px] text-fg-subtle">{t.tag}</div>
          </div>
          {t.badge ? <Badge badge={t.badge} /> : null}
        </div>

        <div className="mt-4 flex items-baseline gap-1">
          <span className="text-[34px] font-bold leading-none tabular-nums">{t.priceBig}</span>
          <span className="text-[13px] text-fg-subtle">{t.per}</span>
        </div>

        <div className="mt-2 text-[12.5px] text-fg-muted">
          <b className="font-semibold text-fg">{t.days} дней</b> доступа · в сумме{' '}
          <b className="font-semibold text-fg">{t.sumLabel}</b>
        </div>

        <ul className="mt-4 flex flex-col gap-2 pb-5">
          {t.features.map((f) => (
            <li
              key={f.text}
              className={cn('flex items-center gap-2 text-[13px]', !f.included && 'text-fg-subtle')}
            >
              {f.included ? (
                <Check className="size-3.5 shrink-0 text-primary-deep dark:text-primary" strokeWidth={2.6} />
              ) : (
                <X className="size-3.5 shrink-0 text-fg-subtle" strokeWidth={2.2} />
              )}
              {f.text}
            </li>
          ))}
        </ul>
      </div>

      <div className="grid grid-cols-3 border-t-[0.5px] border-border bg-surface-2 px-[22px] py-3.5">
        {t.stats.map((s) => (
          <div key={s.label} className="min-w-0">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.3px] text-fg-subtle">{s.label}</div>
            <div className="mt-0.5 text-[15px] font-bold tabular-nums">{s.value}</div>
            <div className={cn('text-[10.5px]', s.footUp ? 'text-primary-deep dark:text-primary' : 'text-fg-subtle')}>
              {s.foot}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-1 border-t-[0.5px] border-border px-[18px] py-3">
        <button
          type="button"
          className={cn(ACTION, 'text-fg')}
          onClick={() => toast(`Редактирование тарифа «${t.name}»`)}
        >
          <SquarePen className="size-3.5" />
          Изменить
        </button>
        <button
          type="button"
          className={cn(ACTION, 'text-fg-muted hover:text-fg')}
          onClick={() => toast.success('Тариф продублирован', { description: t.name })}
        >
          Дублировать
        </button>
        <button type="button" className={cn(ACTION, 'ml-auto text-danger')} onClick={archive}>
          Архив
        </button>
      </div>
    </article>
  );
}
