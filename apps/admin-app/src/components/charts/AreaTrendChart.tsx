import type { ReactNode } from 'react';
import { Area, AreaChart, CartesianGrid, Line, XAxis, YAxis } from 'recharts';
import { cn } from '@/lib/cn';
import { ChartContainer, ChartTooltip, type ChartConfig } from '@/components/ui/chart';

export interface TrendPoint {
  label: string;
  value: number;
  /** Сравнительный ряд (пунктирная линия), напр. прошлый период. */
  compare?: number;
}

interface DotProps {
  cx?: number;
  cy?: number;
  index?: number;
  lastIndex?: number;
}

/** Точка-маркер на последнем дне ряда. */
function LastDot({ cx, cy, index, lastIndex }: DotProps) {
  if (cx == null || cy == null || index !== lastIndex) return <g />;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={4}
      fill="var(--surface)"
      stroke="var(--primary-deep)"
      strokeWidth={2}
    />
  );
}

const CONFIG: ChartConfig = { value: { label: 'Значение', color: 'var(--primary-deep)' } };

/**
 * Линейно-площадная диаграмма тренда с опциональным пунктирным рядом сравнения.
 * Обёртка над Recharts (shadcn ChartContainer). Цвета — токены проекта.
 * Используется на «Отчётах» (выручка по дням) и «Посещаемости» (кривая по часам).
 */
export function AreaTrendChart({
  data,
  height = 240,
  yMax,
  ticks,
  renderTooltip,
  className,
}: {
  data: TrendPoint[];
  height?: number;
  yMax?: number;
  /** Подмножество подписей оси X для отображения. */
  ticks?: string[];
  /** Кастомный тултип по точке. */
  renderTooltip?: (point: TrendPoint) => ReactNode;
  className?: string;
}) {
  const lastIndex = data.length - 1;
  const hasCompare = data.some((d) => d.compare != null);

  return (
    <ChartContainer
      config={CONFIG}
      className={cn('aspect-auto w-full', className)}
      style={{ height }}
    >
      <AreaChart data={data} margin={{ top: 10, right: 12, left: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="areaTrendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2dd4a4" stopOpacity={0.32} />
            <stop offset="100%" stopColor="#2dd4a4" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid
          vertical={false}
          stroke="var(--border)"
          strokeDasharray="3 4"
          strokeOpacity={0.7}
        />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          ticks={ticks}
          tick={{ fontSize: 10 }}
        />
        <YAxis hide domain={yMax != null ? [0, yMax] : ['auto', 'auto']} />
        {hasCompare ? (
          <Line
            type="monotone"
            dataKey="compare"
            stroke="var(--fg-subtle)"
            strokeWidth={1.5}
            strokeDasharray="3 4"
            dot={false}
            isAnimationActive={false}
          />
        ) : null}
        <Area
          type="monotone"
          dataKey="value"
          stroke="var(--primary-deep)"
          strokeWidth={2.2}
          fill="url(#areaTrendFill)"
          dot={<LastDot lastIndex={lastIndex} />}
          activeDot={{
            r: 4,
            fill: 'var(--surface)',
            stroke: 'var(--primary-deep)',
            strokeWidth: 2,
          }}
          isAnimationActive={false}
        />
        {renderTooltip ? (
          <ChartTooltip
            cursor={{ stroke: 'var(--primary-deep)', strokeDasharray: '2 3', strokeOpacity: 0.5 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const point = payload[0]?.payload as TrendPoint | undefined;
              return point ? <>{renderTooltip(point)}</> : null;
            }}
          />
        ) : null}
      </AreaChart>
    </ChartContainer>
  );
}
