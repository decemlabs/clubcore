/**
 * Реэкспорт всех мок-источников.
 * Файлы добавляются по мере интеграции реальных HTML-шаблонов:
 *   - src/mocks/clients.ts ✓
 *   - src/mocks/trainers.ts ✓
 *   - src/mocks/schedule.ts
 *   - src/mocks/memberships.ts
 *   - src/mocks/dashboard.ts ✓
 */
export * from './dashboard';
export * from './clients';
export * from './client-detail';
export * from './trainers';
export * from './trainer-detail';
export * from './schedule';
export * from './plans';
export * from './cashbox';
export * from './messages';
export * from './reports';
export * from './attendance';
export * from './load';
export * from './settings';
export * from './system-settings';
export * from './branches';
export * from './roles';
export * from './audit';
export * from './trash';
export * from './import-export';
export * from './finance';
export * from './notifications';
