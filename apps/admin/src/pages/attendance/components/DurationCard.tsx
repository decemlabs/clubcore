import { useState } from 'react';
import { cn } from '@/lib/cn';
import { Card, CardHeader } from '@/components/layout/Card';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { DonutChart } from '@/components/charts/DonutChart';
import type { DurationData } from '@/features/attendance/types';

type Scope = 'all' | 'gym' | 'group';
const SCOPES: SegmentedOption<Scope>[] = [
  { value: 'all', label: 'Все' },
  { value: 'gym', label: 'Зал' },
  { value: 'group', label: 'Группа' },
];

export function DurationCard({ data }: { data: DurationData }) {
  const [scope, setScope] = useState<Scope>('gym');
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Длительность визита"
        subtitle="Минут в зале · QR-вход → QR-выход"
        action={
          <Segmented
            variant="mini"
            options={SCOPES}
            value={scope}
            onChange={setScope}
            ariaLabel="Тип визита"
          />
        }
      />
      <div className="flex items-center gap-4 px-5 pt-1">
        <DonutChart
          size={92}
          thickness={13}
          segments={[
            { label: 'visit', value: data.donutPct, color: 'var(--primary)' },
            { label: 'rest', value: 100 - data.donutPct, color: 'var(--surface-3)' },
          ]}
          center={
            <div>
              <div className="text-[18px] font-bold leading-none tabular-nums">
                {data.centerValue}
              </div>
              <div className="mt-0.5 text-[9px] text-fg-subtle">мин среднее</div>
            </div>
          }
        />
        <div className="min-w-0">
          <div className="text-[24px] font-bold tabular-nums">
            {data.median}
            <small className="ml-1 text-[11px] font-medium text-fg-subtle">медиана</small>
          </div>
          <div className="mt-1 flex flex-col gap-0.5 text-[11.5px] leading-snug text-fg-muted">
            {data.notes.map((n) => (
              <div key={n.pre}>
                {n.pre}
                <b className="font-semibold text-fg">{n.strong}</b>
                {n.post}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="px-5 pb-4 pt-4">
        <div className="flex h-[120px] items-end gap-1.5">
          {data.buckets.map((b) => (
            <div
              key={b.label}
              className={cn('w-full flex-1 rounded-t-[4px]', b.peak ? 'bg-fg' : 'bg-fg-subtle/60')}
              style={{ height: `${b.pct}%` }}
            />
          ))}
        </div>
        <div className="mt-1.5 flex gap-1.5">
          {data.buckets.map((b) => (
            <div key={b.label} className="min-w-0 flex-1 text-center">
              <div className="truncate text-[9.5px] font-semibold tabular-nums">{b.label}</div>
              <div className="text-[9px] text-fg-subtle tabular-nums">{b.share}</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
