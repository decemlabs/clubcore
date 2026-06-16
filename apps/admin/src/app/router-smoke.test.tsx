import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { Providers } from './providers';
import { routeConfig } from './router';

// Все зарегистрированные пути, которые должны рендериться без падений.
// /login имеет собственный <main> (chrome-less). Все остальные — через AppLayout
// (SidebarInset рендерится как <main>), поэтому findByRole('main') подходит для всех.
const PATHS = [
  '/',
  '/clients',
  '/schedule',
  '/plans',
  '/trainers',
  '/branches',
  '/cashbox',
  '/messages',
  '/notifications',
  '/reports',
  '/attendance',
  '/load',
  '/finance',
  '/settings',
  '/settings/system',
  '/settings/roles',
  '/settings/audit',
  '/settings/trash',
  '/settings/import-export',
  '/login',
];

describe('маршруты рендерятся без падений', () => {
  for (const path of PATHS) {
    it(
      path,
      async () => {
        const router = createMemoryRouter(routeConfig, { initialEntries: [path] });
        const { unmount } = render(
          <Providers>
            <RouterProvider router={router} />
          </Providers>,
        );
        expect(await screen.findByRole('main', {}, { timeout: 10_000 })).toBeInTheDocument();
        unmount();
      },
      10_000,
    );
  }
});
