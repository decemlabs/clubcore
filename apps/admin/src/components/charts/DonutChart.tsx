import type { ReactNode } from 'react';
import { Cell, Pie, PieChart } from 'recharts';
import { cn } from '@/lib/cn';
import { ChartContainer, type ChartConfig } from '@/components/ui/chart';

export interface DonutSegment {
  label: string;
  value: number;
  /** Цвет сегмента (hex или CSS-переменная-токен). */
  color: string;
}

const EMPTY_CONFIG: ChartConfig = {};

/**
 * Кольцевая диаграмма (donut) с подписью в центре. Обёртка над Recharts.
 * Цвета сегментов приходят из данных (токены/hex). Переиспользуется в аналитике.
 */
export function DonutChart({
  segments,
  size = 132,
  thickness = 18,
  center,
  className,
}: {
  segments: DonutSegment[];
  size?: number;
  thickness?: number;
  center?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('relative shrink-0', className)} style={{ width: size, height: size }}>
      <ChartContainer config={EMPTY_CONFIG} className="aspect-square size-full">
        <PieChart>
          <Pie
            data={segments}
            dataKey="value"
            nameKey="label"
            innerRadius={size / 2 - thickness}
            outerRadius={size / 2}
            startAngle={90}
            endAngle={-270}
            paddingAngle={1}
            stroke="none"
            isAnimationActive={false}
          >
            {segments.map((s) => (
              <Cell key={s.label} fill={s.color} />
            ))}
          </Pie>
        </PieChart>
      </ChartContainer>
      {center ? (
        <div className="absolute inset-0 grid place-items-center text-center">{center}</div>
      ) : null}
    </div>
  );
}
