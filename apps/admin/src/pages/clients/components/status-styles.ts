/**
 * Цветовые карты статусов клиента (вынесены из компонентов ради react-refresh).
 */
import type { ClientStatus, ExpiryUrgency, PlanTone } from '@/features/clients/types';

/** Цвет заполнения прогресс-бара абонемента (десктоп-трактовка референса). */
export const PLAN_FILL: Record<PlanTone, string> = {
  normal: 'bg-fg',
  warn: 'bg-warning',
  danger: 'bg-danger',
  muted: 'bg-fg-subtle',
};

/** Цвет верхней строки «Истекает» в таблице (тёмный янтарь для «скоро»). */
export const URGENCY_TABLE: Record<ExpiryUrgency, string> = {
  urgent: 'text-danger',
  soon: 'text-warning-deep',
  normal: 'text-fg',
};

/** То же для карточки — нейтральный по умолчанию, яркий янтарь для «скоро». */
export const URGENCY_CARD: Record<ExpiryUrgency, string> = {
  urgent: 'text-danger',
  soon: 'text-warning',
  normal: 'text-fg-muted',
};

/** Цвет левой полосы статуса в карточке клиента. */
export const STATUS_STRIPE: Record<ClientStatus, string> = {
  active: 'bg-primary',
  expiring: 'bg-danger',
  frozen: 'bg-[#64748b]',
  lead: 'bg-lead',
  expired: 'bg-fg-subtle',
};
