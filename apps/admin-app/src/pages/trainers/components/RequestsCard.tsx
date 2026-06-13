import type { LucideIcon } from 'lucide-react';
import { Card, CardHeader } from '@/components/layout/Card';
import { Calendar, ChevronRight, Star, TriangleAlert, UserPlus } from '@/components/icons';
import type { RequestItem, RequestTone, RequestsData } from '@/features/trainers/types';

const TONE: Record<RequestTone, { icon: LucideIcon; chip: string }> = {
  warn: { icon: Calendar, chip: 'bg-warning-soft text-warning-deep' },
  danger: { icon: TriangleAlert, chip: 'bg-danger-soft text-danger' },
  ok: { icon: UserPlus, chip: 'bg-primary-soft text-primary-deep dark:text-primary' },
  neutral: { icon: Star, chip: 'bg-surface-3 text-fg-muted' },
};

const PRIMARY_BTN =
  'inline-flex h-7 items-center rounded-lg bg-fg px-3 text-[12px] font-semibold text-bg transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-primary dark:text-[#06120c] dark:hover:bg-[#5ee9b8]';
const GHOST_BTN =
  'inline-flex h-7 items-center rounded-lg border-[0.5px] border-border bg-surface px-3 text-[12px] font-semibold text-fg-muted transition-colors hover:border-border-strong hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function Row({ item, first }: { item: RequestItem; first: boolean }) {
  const { icon: Icon, chip } = TONE[item.tone];
  return (
    <div
      className={
        first ? 'flex gap-3 px-5 py-3.5' : 'flex gap-3 border-t-[0.5px] border-border px-5 py-3.5'
      }
    >
      <span className={`grid size-9 shrink-0 place-items-center rounded-[10px] ${chip}`}>
        <Icon className="size-[18px]" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="text-[14px] font-bold leading-snug">{item.title}</div>
          <div className="shrink-0 whitespace-nowrap text-[11px] text-fg-subtle">{item.when}</div>
        </div>
        <p className="mt-1 text-[12.5px] leading-relaxed text-fg-muted">{item.sub}</p>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {item.actions.map((a) => (
            <button key={a.label} type="button" className={a.primary ? PRIMARY_BTN : GHOST_BTN}>
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/** Заявки и заметки: лента действий с иконкой-тоном и кнопками. */
export function RequestsCard({ data }: { data: RequestsData }) {
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Заявки и заметки"
        subtitle={`${data.pendingCount} действия требуют решения`}
        align="center"
        action={
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-md text-[12.5px] font-semibold text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Все · {data.totalCount}
            <ChevronRight className="size-3" strokeWidth={2.4} />
          </button>
        }
      />
      <div>
        {data.items.map((item, i) => (
          <Row key={item.id} item={item} first={i === 0} />
        ))}
      </div>
    </Card>
  );
}
