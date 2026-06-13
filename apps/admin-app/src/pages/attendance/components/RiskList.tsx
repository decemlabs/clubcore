import { useState } from 'react';
import { cn } from '@/lib/cn';
import { Card, CardHeader } from '@/components/layout/Card';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { Initials } from '@/components/ui/initials';
import { MessageSquare, MoreHorizontal, TrendingDown } from '@/components/icons';
import type { RiskClient, RiskScore } from '@/features/attendance/types';

const SCORE: Record<RiskScore, { cls: string; label: string }> = {
  high: { cls: 'bg-danger-soft text-danger', label: 'Высокий' },
  med: { cls: 'bg-warning-soft text-warning-deep', label: 'Средний' },
  low: { cls: 'bg-primary-soft text-primary-deep dark:text-primary', label: 'Низкий' },
};

function RiskRow({ c, first }: { c: RiskClient; first: boolean }) {
  return (
    <div
      className={cn(
        'grid grid-cols-[36px_minmax(0,1fr)_auto_76px_auto] items-center gap-3 px-5 py-3 transition-colors hover:bg-surface-2 max-md:grid-cols-[36px_minmax(0,1fr)_auto]',
        !first && 'border-t-[0.5px] border-border',
      )}
    >
      <Initials initials={c.initials} color={c.color} className="size-9 text-[12px]" />
      <div className="min-w-0">
        <div className="text-[13.5px] font-semibold">{c.name}</div>
        <div className="line-clamp-2 text-[11.5px] text-fg-muted">{c.meta}</div>
      </div>
      <span className="inline-flex items-center gap-1 whitespace-nowrap text-[12px] font-semibold tabular-nums text-danger max-md:hidden">
        <TrendingDown className="size-3.5" />
        {c.trend}
      </span>
      <span
        className={cn(
          'rounded-full px-2 py-1 text-center text-[10.5px] font-bold uppercase tracking-[0.2px] max-md:hidden',
          SCORE[c.score].cls,
        )}
      >
        {SCORE[c.score].label}
      </span>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          aria-label="Действия"
          className="grid size-8 place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring max-sm:hidden"
        >
          <MoreHorizontal className="size-4" />
        </button>
        <button
          type="button"
          className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-fg px-3 text-[12px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]"
        >
          <MessageSquare className="size-3.5" />
          <span className="max-sm:hidden">Написать</span>
        </button>
      </div>
    </div>
  );
}

export function RiskList({ data }: { data: { count: number; total: number; rows: RiskClient[] } }) {
  const [level, setLevel] = useState<'high' | 'med' | 'all'>('high');
  const options: SegmentedOption<'high' | 'med' | 'all'>[] = [
    { value: 'high', label: 'Высокий' },
    { value: 'med', label: 'Средний' },
    { value: 'all', label: `Все · ${data.total}` },
  ];

  return (
    <Card as="section" className="flex flex-col">
      <CardHeader
        title={`Под риском оттока · ${data.count} клиентов`}
        subtitle="Постоянные клиенты, чья частота визитов резко упала. Сортировка по уровню риска"
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Segmented
              variant="mini"
              options={options}
              value={level}
              onChange={setLevel}
              ariaLabel="Уровень риска"
            />
            <button
              type="button"
              className="inline-flex h-8 items-center gap-1.5 rounded-full border-[0.5px] border-border bg-surface px-3 text-[12.5px] font-semibold text-fg transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <MessageSquare className="size-3.5" />
              <span className="max-sm:hidden">Написать всем</span>
            </button>
          </div>
        }
      />
      <div>
        {data.rows.map((c, i) => (
          <RiskRow key={c.id} c={c} first={i === 0} />
        ))}
      </div>
    </Card>
  );
}
