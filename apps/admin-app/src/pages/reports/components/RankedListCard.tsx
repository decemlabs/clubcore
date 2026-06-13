import { cn } from '@/lib/cn';
import { Card, CardHeader, CardLink } from '@/components/layout/Card';
import { Initials } from '@/components/ui/initials';
import type { BarTone, RankedListData, RankRow } from '@/features/reports/types';

const BAR_FILL: Record<BarTone, string> = {
  dark: 'bg-fg',
  accent: 'bg-primary',
  grey: 'bg-fg-subtle',
};

function Row({ row, first }: { row: RankRow; first: boolean }) {
  return (
    <div
      className={cn(
        'grid grid-cols-[22px_minmax(0,1fr)_90px_64px] items-center gap-3 px-5 py-3 max-sm:grid-cols-[22px_minmax(0,1fr)_80px]',
        !first && 'border-t-[0.5px] border-border',
      )}
    >
      {row.avatar ? (
        <Initials
          initials={row.avatar.initials}
          color={row.avatar.color}
          className="size-[22px] text-[9.5px]"
        />
      ) : (
        <span className="text-center font-mono text-[11px] text-fg-subtle">{row.rank}</span>
      )}

      <div className="min-w-0">
        <div className="truncate text-[13.5px] font-semibold">{row.name}</div>
        <div className="truncate text-[11px] text-fg-subtle">{row.sub}</div>
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-surface-3">
          <div
            className={cn('h-full rounded-full', BAR_FILL[row.barTone])}
            style={{ width: `${row.barPct}%` }}
          />
        </div>
      </div>

      <div className="whitespace-nowrap text-right text-[14px] font-bold tabular-nums">
        {row.amount}
      </div>
      <div className="whitespace-nowrap text-right text-[11.5px] text-fg-muted tabular-nums max-sm:hidden">
        {row.share}
      </div>
    </div>
  );
}

export function RankedListCard({ data }: { data: RankedListData }) {
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title={data.title}
        subtitle={data.sub}
        action={<CardLink to={data.linkTo}>{data.linkLabel}</CardLink>}
      />

      <div>
        {data.rows.map((row, i) => (
          <Row key={row.id} row={row} first={i === 0} />
        ))}
      </div>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t-[0.5px] border-border px-5 py-3 text-[12px] text-fg-muted">
        <span>
          {data.footLeft.pre}
          <b className="font-semibold tabular-nums text-fg">{data.footLeft.strong}</b>
          {data.footLeft.post}
        </span>
        <span>
          {data.footRight.pre}
          <b className="font-semibold text-fg">{data.footRight.strong}</b>
        </span>
      </div>
    </Card>
  );
}
