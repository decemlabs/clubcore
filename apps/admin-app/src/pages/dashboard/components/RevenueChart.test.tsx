import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { TooltipProvider } from '@/components/ui/tooltip';
import { RevenueChart } from './RevenueChart';
import type { RevenueReportData } from '@/features/reports/schemas';

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

const fromDate = '2026-05-14';
const toDate = '2026-06-12';

/** Fixture with empty buckets — should show empty state. */
const emptyData: RevenueReportData = {
  buckets: [],
  fromDate,
  toDate,
  groupBy: 'day',
};

/** Fixture with one bucket. */
const withDataFixture: RevenueReportData = {
  buckets: [
    {
      period: '2026-05-14',
      netKopecks: 9600000,
      byMethod: { cash: 4800000, online: 4800000 },
      bySubjectKind: { membership: 9600000, ptPackage: 0 },
    },
  ],
  fromDate,
  toDate,
  groupBy: 'day',
};

describe('RevenueChart (wired — Phase 104-02)', () => {
  it('показывает пустое состояние когда buckets пусты', () => {
    render(
      <Wrapper>
        <RevenueChart data={emptyData} fromDate={fromDate} toDate={toDate} isPending={false} />
      </Wrapper>,
    );
    expect(screen.getByText('Нет данных за период')).toBeInTheDocument();
  });

  it('рендерит заголовок карточки при наличии данных', () => {
    render(
      <Wrapper>
        <RevenueChart data={withDataFixture} fromDate={fromDate} toDate={toDate} isPending={false} />
      </Wrapper>,
    );
    // The card title is always rendered regardless of chart data
    expect(screen.getAllByText('Выручка за 30 дней').length).toBeGreaterThan(0);
  });

  it('показывает скелет при isPending=true', () => {
    render(
      <Wrapper>
        <RevenueChart data={undefined} fromDate={fromDate} toDate={toDate} isPending={true} />
      </Wrapper>,
    );
    // Subtitle collapses to em-dash while loading
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
