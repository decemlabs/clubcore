import { ChevronRight } from '@/components/icons';
import { useModals } from '@/components/modals/modals-context';
import type { OccupancyNow as OccupancyNowData } from '@/features/dashboard/types';

const BRIGHT_BAR = 'linear-gradient(90deg, #2dd4a4, #5ee9b8)';
const MUTED_BAR = 'rgba(45, 212, 164, 0.30)';

/** «В клубе сейчас» — тёмная hero-карточка с живой заполняемостью. Клик → список присутствующих. */
export function OccupancyNow({ data }: { data: OccupancyNowData }) {
  const { open } = useModals();
  return (
    <section
      role="button"
      tabIndex={0}
      onClick={() => open('present')}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          open('present');
        }
      }}
      className="group relative flex cursor-pointer flex-col justify-between gap-4 overflow-hidden rounded-lg bg-[linear-gradient(160deg,#1c1917_0%,#2a2826_100%)] p-[22px] pb-5 text-[#f5f5f4] shadow-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 dark:bg-[linear-gradient(160deg,#050505_0%,#181715_100%)]"
    >
      {/* Свечение в углу */}
      <div className="pointer-events-none absolute -right-[60px] -top-[60px] size-[220px] rounded-full bg-[radial-gradient(circle,rgba(45,212,164,0.5),transparent_70%)]" />

      <div className="relative">
        <div className="flex items-center justify-between gap-2.5">
          <span className="text-[12.5px] font-medium uppercase tracking-[0.5px] text-[#a8a29e]">
            В клубе сейчас
          </span>
          <span className="inline-flex items-center gap-0.5 text-[11.5px] font-semibold tracking-[-0.1px] text-primary opacity-85 transition-[opacity,gap] group-hover:gap-1 group-hover:opacity-100">
            Список
            <ChevronRight className="size-[11px]" strokeWidth={2.6} />
          </span>
        </div>

        <div className="mt-2.5 flex items-baseline gap-1.5 tabular-nums">
          <span className="text-[56px] font-bold leading-none tracking-[-2px]">{data.current}</span>
          <span className="text-lg font-medium text-[#a8a29e]">/ {data.capacity}</span>
        </div>

        <div className="mt-4 flex flex-col items-start gap-2">
          <span className="flex">
            {data.faces.map((face) => (
              <span
                key={face.initials}
                style={{ background: face.color }}
                className="-ml-2 grid size-[30px] place-items-center rounded-full border-2 border-[#211e1c] text-[10.5px] font-bold tracking-[-0.3px] text-white transition-transform first:ml-0 group-hover:-translate-y-px"
              >
                {face.initials}
              </span>
            ))}
            <span className="-ml-2 grid size-[30px] place-items-center rounded-full border-2 border-[#211e1c] bg-[#46423f] text-[10.5px] font-bold tracking-[-0.3px] text-[#e7e5e4] transition-transform group-hover:-translate-y-px">
              +{data.moreCount}
            </span>
          </span>
          <span className="text-[11.5px] text-[#a8a29e]">в зале прямо сейчас</span>
        </div>
      </div>

      {/* Разбивка по ячейкам */}
      <div className="relative grid grid-cols-3 gap-2.5">
        {data.cells.map((cell) => (
          <div
            key={cell.label}
            className="flex min-w-0 flex-col rounded-[13px] border-[0.5px] border-white/10 bg-white/[0.045] px-3 pb-3 pt-[11px] transition-colors group-hover:border-white/[0.14]"
          >
            <div className="truncate text-[11.5px] text-[#a8a29e]">{cell.label}</div>
            <div className="mt-1 text-[22px] font-bold tracking-[-0.6px] tabular-nums">
              {cell.value}
              {cell.delta ? (
                <small className="ml-1 text-[11.5px] font-semibold text-[#5ee9b8]">
                  {cell.delta}
                </small>
              ) : null}
            </div>
            <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/10">
              <span
                className="block h-full rounded-full"
                style={{
                  width: `${cell.barPct}%`,
                  background: cell.muted ? MUTED_BAR : BRIGHT_BAR,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Метр заполнения */}
      <div className="relative">
        <div className="h-2 overflow-hidden rounded-full bg-[#2a2826]">
          <div
            className="h-full rounded-full"
            style={{ width: `${data.fillPct}%`, background: BRIGHT_BAR }}
          />
        </div>
        <div className="mt-3.5 flex justify-between text-xs text-[#a8a29e]">
          <span>
            Заполнено <b className="font-semibold text-[#f5f5f4]">{data.fillPct}%</b>
          </span>
          <span>
            За день: <b className="font-semibold text-[#f5f5f4]">{data.dayVisits}</b> визитов
          </span>
        </div>
      </div>
    </section>
  );
}
