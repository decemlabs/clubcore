import { createContext, useContext, type ReactNode } from 'react';
import type { ExtendPayload } from './ExtendModal';

export type ModalKey =
  | 'checkin'
  | 'new-client'
  | 'extend'
  | 'book'
  | 'edit-client'
  | 'trainer-form'
  | 'subscription'
  | 'session'
  | 'cash'
  | 'present'
  | 'branch'
  | 'confirm';

/**
 * Полезная нагрузка диалога подтверждения. Строится первым в фазе 3 и
 * переиспользуется всеми (удаление с type-to-confirm, bulk-действия, выход без сохранения).
 */
export interface ConfirmPayload {
  title: string;
  message?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: 'default' | 'danger';
  /** Если задано — для подтверждения нужно ввести это слово (type-to-confirm). */
  requireText?: string;
  onConfirm: () => void | Promise<void>;
}

/** Экран семейства модалок абонемента (Subscription.html). */
export type SubscriptionScreen =
  | 'create'
  | 'edit'
  | 'renew'
  | 'freeze'
  | 'unfreeze'
  | 'cancel'
  | 'history'
  | 'refund';

/** Экран семейства модалок тренировки/сессии (Session.html). */
export type SessionScreen =
  | 'detail'
  | 'create'
  | 'edit'
  | 'reschedule'
  | 'conflict'
  | 'waitlist'
  | 'cancel';

/** Кассовая операция (Cashbox-Ops.html). */
export type CashScreen = 'in' | 'out' | 'recon' | 'zreport' | 'close' | 'openshift';

/**
 * Payload-поля по модалкам. Каждая модалка читает свой ключ из options.
 */
export interface OpenOptions {
  /** Предвыбор клиента для модалки продления. */
  extend?: ExtendPayload;
  editClient?: { clientId?: string };
  /** Без trainerId — создание; с trainerId — редактирование. */
  trainerForm?: { trainerId?: string };
  /**
   * Экран семейства абонемента.
   * membershipId + clientId — обязательны для lifecycle-действий (freeze/unfreeze/renew/cancel/refund).
   * membership — полный объект для RefundScreen (paidAmountKopecks, paidAt, planSnapshot).
   */
  subscription?: {
    screen?: SubscriptionScreen;
    clientName?: string;
    membershipId?: string;
    clientId?: string;
    membership?: {
      id: string;
      clientId: string;
      paidAmountKopecks: number;
      paidAt?: string | null;
      planSnapshot: { name: string };
      endDate: string;
      freezeDaysRemaining?: number | null;
      currentFreezePeriod?: {
        id: string;
        startedAt: string;
        startedBy: string;
        endedAt: string | null;
        endedBy: string | null;
      } | null;
    };
  };
  /** Экран семейства тренировки/сессии. */
  session?: { screen?: SessionScreen };
  /** Кассовая операция; onDone — пост-действие (закрыть/открыть смену переключает состояние страницы). */
  cash?: { screen?: CashScreen; onDone?: () => void };
  /** Без branchId — создание филиала; с branchId — редактирование. */
  branch?: { branchId?: string };
  confirm?: ConfirmPayload;
}

export interface ModalsContextValue {
  open: (key: ModalKey, options?: OpenOptions) => void;
  close: () => void;
}

export const ModalsContext = createContext<ModalsContextValue | null>(null);

/** Доступ к глобальным модалкам действий (чек-ин, продление, запись, новый клиент и т.д.). */
export function useModals(): ModalsContextValue {
  const ctx = useContext(ModalsContext);
  if (!ctx) throw new Error('useModals must be used within <ModalsProvider>');
  return ctx;
}
