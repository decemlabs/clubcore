/**
 * Карта маршрутов. Используйте константы вместо строк, чтобы переименование
 * пути требовало правок только здесь. Динамические маршруты — builder-функции
 * (по умолчанию возвращают паттерн с `:param` для регистрации в роутере).
 *
 * Не все ключи зарегистрированы в router.tsx сразу: страницы добавляются по фазам.
 * Статические подмаршруты (например /clients/archive) регистрируются ДО `:id`-маршрутов.
 */
export const ROUTES = {
  dashboard: '/',

  // Клиенты
  clients: '/clients',
  client: (id: string | number = ':clientId') => `/clients/${id}`,
  clientsArchive: '/clients/archive',
  clientsDuplicates: '/clients/duplicates',

  // Расписание · абонементы
  schedule: '/schedule',
  plans: '/plans',

  // Тренеры
  trainers: '/trainers',
  trainer: (id: string | number = ':trainerId') => `/trainers/${id}`,
  trainersArchive: '/trainers/archive',

  // Касса · сообщения
  cashbox: '/cashbox',
  messages: '/messages',

  // Аналитика
  reports: '/reports',
  attendance: '/attendance',
  load: '/load',
  finance: '/finance',

  // Управление
  notifications: '/notifications',

  // Система
  branches: '/branches',
  branch: (id: string | number = ':branchId') => `/branches/${id}`,
  settings: '/settings',
  systemSettings: '/settings/system',
  roles: '/settings/roles',
  audit: '/settings/audit',
  trash: '/settings/trash',
  importExport: '/settings/import-export',

  // Без оболочки (chrome-less)
  login: '/login',
  error: '/error',
} as const;
