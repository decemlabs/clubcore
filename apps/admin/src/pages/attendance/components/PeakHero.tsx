import type { PeakHeroData } from '@/features/attendance/types';

/** Тёмная карточка-сводка «Час пик · май». */
export function PeakHero({ data }: { data: PeakHeroData }) {
  return (
    <div
      className="relative flex flex-col overflow-hidden rounded-lg p-5 text-white shadow-2"
      style={{ background: 'linear-gradient(160deg,#1c1917,#2a2826)' }}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute -right-12 -top-12 size-44 rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(45,212,164,0.22), transparent 70%)' }}
      />
      <div className="relative text-[10.5px] font-bold uppercase tracking-[0.6px] text-primary">
        Час пик · май
      </div>
      <div className="relative mt-2 flex items-baseline gap-2">
        <span className="text-[32px] font-bold leading-none tabular-nums">{data.when}</span>
        <span className="text-[12px] text-white/55">{data.whenSub}</span>
      </div>
      <div className="relative mt-2.5 text-[12.5px] leading-relaxed text-white/70">
        {data.bodyPre}
        <b className="font-semibold text-white">{data.bodyAvg}</b>
        {data.bodyMid}
        <b className="font-semibold text-primary">{data.bodyDays}</b>
        {data.bodyPost}
      </div>
      <div className="relative mt-auto grid grid-cols-2 gap-x-4 gap-y-3.5 border-t border-white/10 pt-4">
        {data.stats.map((s) => (
          <div key={s.label}>
            <div className="text-[11px] text-white/50">{s.label}</div>
            <div className="mt-0.5 text-[14px] font-bold">{s.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
