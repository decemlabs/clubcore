import { cn } from '@/lib/cn';
import { useModals } from '@/components/modals/modals-context';
import type { LiveData, ZoneTone } from '@/features/load/types';

const ZONE_BAR: Record<ZoneTone, string> = {
  accent: 'bg-primary',
  warn: 'bg-[#fbbf24]',
  low: 'bg-white/30',
};

/** Тёмная карточка «Сейчас» — текущая загрузка клуба + разбивка по зонам. Клик → список присутствующих. */
export function LiveNowCard({ data }: { data: LiveData }) {
  const { open } = useModals();
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => open('present')}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          open('present');
        }
      }}
      className="relative flex cursor-pointer flex-col overflow-hidden rounded-lg text-white shadow-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
      style={{ background: 'linear-gradient(160deg,#1c1917,#2a2826)' }}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute -right-12 -top-12 size-44 rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(45,212,164,0.22), transparent 70%)' }}
      />
      <div className="relative p-[22px] pb-4">
        <div className="flex items-center gap-2 text-[11.5px] font-semibold uppercase tracking-[0.5px] text-white/55">
          <span className="size-[7px] animate-pulse rounded-full bg-primary" />
          Сейчас · {data.time}
        </div>
        <div className="mt-2 flex items-baseline gap-1.5">
          <span className="text-[60px] font-bold leading-none tracking-[-2px] tabular-nums">
            {data.current}
          </span>
          <span className="text-[18px] text-white/55">/ {data.capacity}</span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-primary" style={{ width: `${data.meterPct}%` }} />
        </div>
        <div className="mt-2 flex items-center justify-between text-[12px] text-white/55">
          <span>
            Заполнено <b className="font-semibold text-white">{data.filledPct}</b>
          </span>
          <span>
            За день: <b className="font-semibold text-white">{data.dayVisits}</b> визитов
          </span>
        </div>
      </div>

      <div className="relative border-t border-white/10">
        {data.zones.map((z, i) => (
          <div
            key={z.name}
            className={cn(
              'grid grid-cols-[minmax(0,1fr)_56px] items-center gap-3 px-[22px] py-3',
              i > 0 && 'border-t border-white/[0.08]',
            )}
          >
            <div className="min-w-0">
              <div className="text-[12.5px] font-semibold">{z.name}</div>
              <div className="text-[11px] text-white/50">
                {z.metaStrong ? (
                  <b className="font-semibold text-white/85">{z.metaStrong}</b>
                ) : null}
                {z.metaRest}
              </div>
              <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/10">
                <div
                  className={cn('h-full rounded-full', ZONE_BAR[z.tone])}
                  style={{ width: `${z.barPct}%` }}
                />
              </div>
            </div>
            <div
              className={cn(
                'text-right text-[14px] font-bold tabular-nums',
                z.pctWarn ? 'text-[#fbbf24]' : 'text-white',
              )}
            >
              {z.pct}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
