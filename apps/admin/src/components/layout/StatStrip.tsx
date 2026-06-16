import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

/**
 * Контейнер-сетка для полосы метрик. Колонки и зазор задаёт потребитель через
 * className (разные страницы используют разные брейкпоинты — viewport vs @container),
 * чтобы не протекали дефолтные cols/gap.
 */
export function StatStrip({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn('grid', className)}>{children}</div>;
}
