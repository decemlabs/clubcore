import { Card, CardHeader, CardLink } from '@/components/layout/Card';
import { ROUTES } from '@/app/routes';
import type { FrequencyData } from '@/features/attendance/types';

/** Светлые заливки сегментов — тёмный текст для контраста. */
const DARK_TEXT = new Set(['#2dd4a4', '#a8a29e', '#e9a23b']);

export function FrequencyCard({ data }: { data: FrequencyData }) {
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Сегменты по частоте"
        subtitle={`Сколько раз в неделю ходит клиент · ${data.total} чел`}
        action={<CardLink to={ROUTES.clients}>Клиенты</CardLink>}
      />
      <div className="px-5 pb-4">
        <div className="flex h-7 overflow-hidden rounded-lg">
          {data.segments.map((s) => (
            <div
              key={s.name}
              style={{
                flex: s.count,
                background: s.color,
                color: DARK_TEXT.has(s.color) ? '#1c1917' : '#fff',
              }}
              className="grid min-w-0 place-items-center text-[10.5px] font-bold tabular-nums"
            >
              {s.count}
            </div>
          ))}
        </div>

        <div className="mt-3">
          {data.segments.map((s, i) => (
            <div
              key={s.name}
              className={`grid grid-cols-[10px_minmax(0,1fr)_auto_36px] items-center gap-2.5 py-2 text-[12px] ${i > 0 ? 'border-t-[0.5px] border-border' : ''}`}
            >
              <span className="size-2.5 rounded-[3px]" style={{ background: s.color }} />
              <div className="min-w-0">
                <div className="truncate font-semibold">{s.name}</div>
                <div className="truncate text-[11px] text-fg-subtle">{s.sub}</div>
              </div>
              <span className="text-right font-bold tabular-nums">{s.count}</span>
              <span className="text-right text-fg-subtle tabular-nums">{s.pct}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
