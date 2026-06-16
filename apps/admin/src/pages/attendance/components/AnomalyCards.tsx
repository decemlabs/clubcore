import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Card } from '@/components/layout/Card';
import { Activity, MessageSquare, TriangleAlert } from '@/components/icons';
import type { Anomaly, AnomalyTone } from '@/features/attendance/types';

const TONE: Record<AnomalyTone, { icon: LucideIcon; cls: string }> = {
  warn: { icon: TriangleAlert, cls: 'bg-warning-soft text-warning-deep' },
  ok: { icon: Activity, cls: 'bg-primary-soft text-primary-deep dark:text-primary' },
  info: { icon: MessageSquare, cls: 'bg-surface-3 text-fg-muted' },
};

export function AnomalyCards({ items }: { items: Anomaly[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {items.map((a) => {
        const { icon: Icon, cls } = TONE[a.tone];
        return (
          <Card key={a.title} as="section" className="flex gap-3 p-4">
            <span className={cn('grid size-9 shrink-0 place-items-center rounded-[10px]', cls)}>
              <Icon className="size-[18px]" />
            </span>
            <div className="min-w-0">
              <div className="text-[13px] font-bold leading-snug">{a.title}</div>
              <p className="mt-1 text-[11.5px] leading-relaxed text-fg-muted">{a.body}</p>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
