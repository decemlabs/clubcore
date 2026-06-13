import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom'
import { AppLayout } from '@/layouts/AppLayout/AppLayout'
import { ROUTES } from './routes'
import { ErrorPage } from '@/components/feedback/ErrorPage'
import { RouteErrorBoundary } from '@/components/feedback/RouteErrorBoundary'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { ComingSoon } from '@/components/feedback/ComingSoon'

/**
 * Три ветки:
 *  (A) chrome-less маршруты — вне AppLayout (логин/ошибки добавляются по фазам);
 *  (B) приложение под общей оболочкой AppLayout, с errorElement на всю ветку;
 *  (C) совместимость со статическим прототипом (/index.html → дашборд).
 *
 * Статические подмаршруты (/clients/archive и т.п.) при добавлении регистрируются
 * ДО соответствующих `:id`-маршрутов. Внутренний catch-all '*' рендерит 404 с хромом.
 *
 * Отложенные маршруты (FND-04 hide-for-future): рендерят <ComingSoon/> вместо страницы.
 * Файлы страниц остаются в дереве (не удаляются) и будут подключены в будущих фазах.
 */
export const routeConfig: RouteObject[] = [
  // (A) Без оболочки.
  {
    path: ROUTES.login,
    lazy: async () => ({
      Component: (await import('@/pages/login/LoginPage')).LoginPage,
    }),
  },
  { path: ROUTES.error, element: <ErrorPage code={500} /> },

  // (B) Приложение — защищено RequireAuth (AUTH-02).
  // RequireAuth вызывает useSession() над /auth/me; неаутентифицированный доступ
  // перенаправляется на /login. Ветка /login и /error остаются ВНЕ стража.
  {
    element: <RequireAuth><AppLayout /></RequireAuth>,
    errorElement: <RouteErrorBoundary />,
    children: [
      // --- Активные маршруты (lazy-load) ---
      {
        path: ROUTES.dashboard,
        lazy: async () => ({
          Component: (await import('@/pages/dashboard/DashboardPage')).DashboardPage,
        }),
      },
      {
        path: ROUTES.clients,
        lazy: async () => ({
          Component: (await import('@/pages/clients/ClientsPage')).ClientsPage,
        }),
      },
      {
        path: ROUTES.client(),
        lazy: async () => ({
          Component: (await import('@/pages/client/ClientPage')).ClientPage,
        }),
      },
      {
        path: ROUTES.schedule,
        lazy: async () => ({
          Component: (await import('@/pages/schedule/SchedulePage')).SchedulePage,
        }),
      },
      {
        path: ROUTES.plans,
        lazy: async () => ({
          Component: (await import('@/pages/plans/PlansPage')).PlansPage,
        }),
      },
      {
        path: ROUTES.trainers,
        lazy: async () => ({
          Component: (await import('@/pages/trainers/TrainersPage')).TrainersPage,
        }),
      },
      {
        path: ROUTES.trainer(),
        lazy: async () => ({
          Component: (await import('@/pages/trainer/TrainerPage')).TrainerPage,
        }),
      },
      {
        path: ROUTES.cashbox,
        lazy: async () => ({
          Component: (await import('@/pages/cashbox/CashboxPage')).CashboxPage,
        }),
      },
      {
        path: ROUTES.reports,
        lazy: async () => ({
          Component: (await import('@/pages/reports/ReportsPage')).ReportsPage,
        }),
      },
      {
        path: ROUTES.attendance,
        lazy: async () => ({
          Component: (await import('@/pages/attendance/AttendancePage')).AttendancePage,
        }),
      },
      {
        path: ROUTES.load,
        lazy: async () => ({
          Component: (await import('@/pages/load/LoadPage')).LoadPage,
        }),
      },
      {
        path: ROUTES.finance,
        lazy: async () => ({
          Component: (await import('@/pages/finance/FinancePage')).FinancePage,
        }),
      },
      {
        path: ROUTES.settings,
        lazy: async () => ({
          Component: (await import('@/pages/settings/SettingsPage')).SettingsPage,
        }),
      },
      {
        path: ROUTES.audit,
        lazy: async () => ({
          Component: (await import('@/pages/audit/AuditPage')).AuditPage,
        }),
        handle: { breadcrumb: ['Настройки', 'Журнал действий'] },
      },

      // --- Отложенные маршруты (FND-04 hide-for-future) — рендерят <ComingSoon/> ---
      // Файлы страниц сохранены в дереве; подключаются в будущих фазах.
      { path: ROUTES.branches,       element: <ComingSoon /> },
      {
        path: ROUTES.branch(),
        element: <ComingSoon />,
        handle: { breadcrumb: ['Филиалы'] },
      },
      { path: ROUTES.messages,       element: <ComingSoon /> },
      { path: ROUTES.notifications,  element: <ComingSoon /> },
      {
        path: ROUTES.systemSettings,
        element: <ComingSoon />,
        handle: { breadcrumb: ['Настройки', 'Система'] },
      },
      {
        path: ROUTES.roles,
        element: <ComingSoon />,
        handle: { breadcrumb: ['Настройки', 'Роли и права'] },
      },
      {
        path: ROUTES.trash,
        element: <ComingSoon />,
        handle: { breadcrumb: ['Настройки', 'Корзина'] },
      },
      {
        path: ROUTES.importExport,
        element: <ComingSoon />,
        handle: { breadcrumb: ['Настройки', 'Импорт / экспорт'] },
      },

      { path: '*', element: <ErrorPage code={404} /> },
    ],
  },

  // (C) Совместимость со статическим прототипом.
  { path: '/index.html', element: <Navigate to={ROUTES.dashboard} replace /> },
]

export const router = createBrowserRouter(routeConfig)
