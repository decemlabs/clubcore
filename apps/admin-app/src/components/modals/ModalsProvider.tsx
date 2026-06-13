import { useMemo, useState, type ReactNode } from 'react';
import { Toaster } from '@/components/ui/sonner';
import {
  ModalsContext,
  type ModalKey,
  type ModalsContextValue,
  type OpenOptions,
} from './modals-context';
import { CheckInModal } from './CheckInModal';
import { NewClientModal } from './NewClientModal';
import { ExtendModal } from './ExtendModal';
import { BookModal } from './BookModal';
import { ConfirmModal } from './ConfirmModal';
import { TrainerFormModal } from './TrainerFormModal';
import { SubscriptionModal } from './SubscriptionModal';
import { SessionModal } from './SessionModal';
import { EditClientModal } from './EditClientModal';
import { CashModal } from './CashModal';
import { PresentModal } from './PresentModal';
import { BranchModal } from './BranchModal';

interface ModalState {
  key: ModalKey;
  options?: OpenOptions;
}

/**
 * Глобальный провайдер модалок действий. Монтируется один раз над приложением;
 * любая страница и шапка открывают модалки через useModals().open(key, options).
 * Активная модалка + её payload хранятся одним состоянием, поэтому добавление новой
 * модалки в фазе 3 — это лишь её регистрация в JSX ниже.
 */
export function ModalsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ModalState | null>(null);

  const value = useMemo<ModalsContextValue>(
    () => ({
      open: (key, options) => setState({ key, options }),
      close: () => setState(null),
    }),
    [],
  );

  const active = state?.key ?? null;
  const onClose = (open: boolean) => {
    if (!open) setState(null);
  };

  return (
    <ModalsContext.Provider value={value}>
      {children}
      <CheckInModal open={active === 'checkin'} onOpenChange={onClose} />
      <NewClientModal open={active === 'new-client'} onOpenChange={onClose} />
      <ExtendModal
        open={active === 'extend'}
        onOpenChange={onClose}
        payload={state?.options?.extend}
      />
      <BookModal open={active === 'book'} onOpenChange={onClose} />
      <ConfirmModal
        open={active === 'confirm'}
        onOpenChange={onClose}
        payload={state?.options?.confirm}
      />
      <TrainerFormModal
        open={active === 'trainer-form'}
        onOpenChange={onClose}
        trainer={undefined}
      />
      <SubscriptionModal
        open={active === 'subscription'}
        onOpenChange={onClose}
        payload={state?.options?.subscription}
      />
      <SessionModal
        open={active === 'session'}
        onOpenChange={onClose}
        payload={state?.options?.session}
      />
      <EditClientModal
        open={active === 'edit-client'}
        onOpenChange={onClose}
        clientId={state?.options?.editClient?.clientId}
      />
      <CashModal open={active === 'cash'} onOpenChange={onClose} payload={state?.options?.cash} />
      <PresentModal open={active === 'present'} onOpenChange={onClose} />
      <BranchModal
        open={active === 'branch'}
        onOpenChange={onClose}
        payload={state?.options?.branch}
      />
      <Toaster position="top-right" />
    </ModalsContext.Provider>
  );
}
