import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { TooltipProvider } from '@/components/ui/tooltip';
import { RevenueChart } from './RevenueChart';
import type { RevenueData } from '@/features/dashboard/types';

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient();
  return (
    <QueryClientProvider client={qc}>
      <TooltipProvider>
        <MemoryRouter>{children}</MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
}

/** Минимальная фикстура с пустыми точками для дефолтного периода. */
const emptyData: RevenueData = {
  defaultPeriod: '30',
  series: {
    '30': {
      period: '30',
      title: 'Выручка',
      rangeLabel: '1–30 апр',
      total: 0,
      delta: { label: '+0%', direction: 'flat' },
      deltaSub: 'к марту',
      points: [],
      breakdown: [],
      ticksEvery: 5,
    },
    '90': {
      period: '90',
      title: 'Выручка',
      rangeLabel: 'Янв–Апр',
      total: 0,
      delta: { label: '+0%', direction: 'flat' },
      deltaSub: 'к Q1',
      points: [],
      breakdown: [],
      ticksEvery: 2,
    },
    year: {
      period: 'year',
      title: 'Выручка',
      rangeLabel: '2025',
      total: 0,
      delta: { label: '+0%', direction: 'flat' },
      deltaSub: 'к 2024',
      points: [],
      breakdown: [],
      ticksEvery: 2,
    },
  },
};

/** Фикстура с тремя точками для дефолтного периода. */
const withDataFixture: RevenueData = {
  defaultPeriod: '30',
  series: {
    ...emptyData.series,
    '30': {
      ...emptyData.series['30'],
      title: 'Выручка · апрель',
      rangeLabel: '1–30 апр',
      total: 3248000,
      delta: { label: '+18.4%', direction: 'up' },
      deltaSub: 'к марту',
      points: [
        { label: '1 апр', short: '1', value: 96000 },
        { label: '15 апр', short: '15', value: 112000 },
        { label: '30 апр', short: '30', value: 108000 },
      ],
      breakdown: [
        { label: 'Абонементы', value: 2248000, color: '#2dd4a4' },
        { label: 'ПТ', value: 812400, color: '#818cf8' },
        { label: 'Магазин', value: 188200, color: '#fb923c' },
      ],
      ticksEvery: 1,
    },
  },
};

describe('RevenueChart', () => {
  it('показывает пустое состояние когда points пуст', () => {
    render(
      <Wrapper>
        <RevenueChart data={emptyData} />
      </Wrapper>,
    );
    expect(screen.getByText('Нет данных за период')).toBeInTheDocument();
    expect(screen.getByText('Выберите другой период.')).toBeInTheDocument();
  });

  it('рендерит заголовок серии при наличии данных', () => {
    render(
      <Wrapper>
        <RevenueChart data={withDataFixture} />
      </Wrapper>,
    );
    expect(screen.getByText('Выручка · апрель')).toBeInTheDocument();
  });
});
