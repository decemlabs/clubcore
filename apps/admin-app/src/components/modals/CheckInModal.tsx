/**
 * CheckInModal — реальный чек-ин клиента (Phase 103-02 ATT-01).
 *
 * Открывается кнопкой «Чек-ин» на AttendancePage. Принимает только open/onOpenChange.
 * Анатомия: BookingModal client-picker МИНУС пакет PT.
 *
 * Безопасность (T-103-02-409CHAIN):
 *  - 3 различных 409-кода → 3 различных Callout tone="danger"; модалка остаётся открытой.
 *  - Оптимистичная строка откатывается при любой ошибке (onError в useCheckIn).
 *  - Никаких повторов, никаких обходов — пользователь ВИДИТ причину.
 *
 * ESLint import-boundary:
 *  - ApiError импортируется из @/features/attendance/api (re-export слой), не из @/api/client.
 */
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2, Search, TriangleAlert, UserCheck, X as XIcon } from '@/components/icons';
import { AdaptiveModal } from './AdaptiveModal';
import {
  Callout,
  IconChip,
  ModalButton,
  ModalInput,
  ResultItem,
  ResultList,
  Section,
} from './fields';
import { useClients } from '@/features/clients/api';
import { useCheckIn, useGymMeta, ApiError } from '@/features/attendance/api';
import { useSession } from '@/features/auth/api';
import { getInitials } from '@/lib/format';

// ---------------------------------------------------------------------------
// 409 code → российская копия (T-103-02-409CHAIN)
// ---------------------------------------------------------------------------

interface ErrorCopy {
  heading: string;
  body: string;
}

const CHECK_IN_ERROR_COPY: Record<string, ErrorCopy> = {
  outside_gym_hours: {
    heading: 'Вне часов работы',
    body: 'Зал сейчас закрыт. Чек-ин невозможен до открытия.',
  },
  no_active_membership: {
    heading: 'Нет активного абонемента',
    body: 'У клиента нет действующего абонемента. Оформите абонемент перед регистрацией.',
  },
  duplicate_checkin: {
    heading: 'Уже отмечен сегодня',
    body: 'Этот клиент уже был отмечен сегодня. Повторный чек-ин невозможен.',
  },
};

const GENERIC_ERROR: ErrorCopy = {
  heading: '',
  body: 'Не удалось выполнить чек-ин. Проверьте соединение и попробуйте ещё раз.',
};

// ---------------------------------------------------------------------------
// Вспомогательные функции
// ---------------------------------------------------------------------------

/** Brand emerald via CSS token (WR-05: no raw hex palette in JSX props). */
const AVATAR_COLOR = 'var(--color-primary)';

function clientFullName(c: { firstName: string; lastName: string }): string {
  return `${c.firstName} ${c.lastName}`.trim();
}

/** Проверяет, находится ли текущее московское время вне часов работы зала. */
function isOutsideGymHours(startHHMM: string, endHHMM: string): boolean {
  const nowMSK = new Date(
    new Date().toLocaleString('en-US', { timeZone: 'Europe/Moscow' }),
  );
  const [sh, sm] = startHHMM.split(':').map(Number);
  const [eh, em] = endHHMM.split(':').map(Number);
  const nowMinutes = nowMSK.getHours() * 60 + nowMSK.getMinutes();
  const startMinutes = (sh ?? 0) * 60 + (sm ?? 0);
  const endMinutes = (eh ?? 0) * 60 + (em ?? 0);
  return nowMinutes < startMinutes || nowMinutes >= endMinutes;
}

// ---------------------------------------------------------------------------
// Компонент
// ---------------------------------------------------------------------------

export function CheckInModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [selectedClientName, setSelectedClientName] = useState<string | null>(null);
  const [apiError, setApiError] = useState<ErrorCopy | null>(null);

  // Debounce search input (300ms)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Сброс при открытии модалки
  useEffect(() => {
    if (open) {
      setSearch('');
      setDebouncedSearch('');
      setSelectedClientId(null);
      setSelectedClientName(null);
      setApiError(null);
    }
  }, [open]);

  // Все хуки вызываются до любых conditional return
  const session = useSession();
  const currentUserId = session.data?.id ?? '';
  const clientsQuery = useClients({ q: debouncedSearch, pageSize: 8 });
  const gymMeta = useGymMeta();
  const checkIn = useCheckIn();
  const isPending = checkIn.isPending;

  const handleCheckIn = useCallback(async () => {
    if (!selectedClientId || !selectedClientName) return;
    setApiError(null);
    try {
      await checkIn.mutateAsync({
        clientId: selectedClientId,
        clientName: selectedClientName,
        currentUserId,
      });
      toast.success('Визит зафиксирован', { description: selectedClientName });
      onOpenChange(false);
    } catch (err) {
      if (err instanceof ApiError) {
        const copy = CHECK_IN_ERROR_COPY[err.code] ?? GENERIC_ERROR;
        setApiError(copy);
      } else {
        setApiError(GENERIC_ERROR);
      }
      // Модалка остаётся открытой — пользователь видит причину ошибки
    }
  }, [selectedClientId, selectedClientName, checkIn, currentUserId, onOpenChange]);

  const handleOpenChange = isPending ? () => {} : onOpenChange;

  const clients = clientsQuery.data?.items ?? [];
  const isSearching = debouncedSearch.length > 0 && clientsQuery.isFetching;

  // Gym-meta предупреждение (мягкое): вне часов работы
  const showOutsideHoursWarning =
    gymMeta.data != null &&
    isOutsideGymHours(gymMeta.data.gymHoursStart, gymMeta.data.gymHoursEnd);

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={handleOpenChange}
      icon={<IconChip tone="accent" icon={UserCheck} />}
      title="Чек-ин"
      description="Найдите клиента и отметьте его визит"
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton
            variant="primary"
            disabled={!selectedClientId || isPending}
            onClick={() => void handleCheckIn()}
          >
            {isPending ? <Loader2 className="size-[18px] animate-spin" /> : null}
            Отметить визит
          </ModalButton>
        </>
      }
    >
      {/* Секция «Клиент» */}
      <Section>Клиент</Section>

      {/* Мягкое предупреждение: вне часов работы (soft warn, POST всё ещё разрешён) */}
      {showOutsideHoursWarning && !selectedClientId && (
        <div className="mb-3.5">
          <Callout tone="warn" icon={TriangleAlert}>
            Сейчас вне часов работы зала. Чек-ин может быть отклонён.
          </Callout>
        </div>
      )}

      {/* Поиск клиента */}
      <div className="relative mb-3.5">
        <ModalInput
          icon={Search}
          placeholder="Найти по имени или телефону…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            // Снимаем выбор клиента при изменении поиска
            if (selectedClientId) {
              setSelectedClientId(null);
              setSelectedClientName(null);
              setApiError(null);
            }
          }}
        />
        {isSearching && (
          <Loader2 className="pointer-events-none absolute right-3.5 top-1/2 size-4 -translate-y-1/2 animate-spin text-fg-subtle" />
        )}
      </div>

      {/* Выбранный клиент или список результатов */}
      {selectedClientId ? (
        <ResultList>
          <ResultItem
            initials={getInitials(selectedClientName ?? '')}
            color={AVATAR_COLOR}
            name={selectedClientName ?? ''}
            meta=""
            active
            aside={
              <button
                type="button"
                aria-label="Отменить выбор клиента"
                className="text-fg-muted hover:text-fg"
                onClick={() => {
                  setSelectedClientId(null);
                  setSelectedClientName(null);
                  setApiError(null);
                }}
              >
                <XIcon className="size-3.5" strokeWidth={2.4} />
              </button>
            }
          />
        </ResultList>
      ) : debouncedSearch.length > 0 ? (
        clients.length === 0 && !clientsQuery.isFetching ? (
          <div className="flex items-center justify-center rounded-xl border-[0.5px] border-border bg-surface py-5 text-[13px] text-fg-muted">
            Клиент не найден
          </div>
        ) : (
          <ResultList>
            {clients.map((client) => (
              <ResultItem
                key={client.id}
                initials={getInitials(clientFullName(client))}
                color={AVATAR_COLOR}
                name={clientFullName(client)}
                meta={client.phone ?? ''}
                onClick={() => {
                  setSelectedClientId(client.id);
                  setSelectedClientName(clientFullName(client));
                  setSearch('');
                  setDebouncedSearch('');
                  setApiError(null);
                }}
              />
            ))}
          </ResultList>
        )
      ) : null}

      {/* 409 / ошибка — inline Callout; модалка остаётся открытой (T-103-02-409CHAIN) */}
      {apiError && (
        <div className="mt-3.5">
          <Callout tone="danger" icon={TriangleAlert}>
            {apiError.heading ? (
              <>
                <span className="font-semibold">{apiError.heading}</span>
                <span className="mt-0.5 block text-[11.5px]">{apiError.body}</span>
              </>
            ) : (
              <span>{apiError.body}</span>
            )}
          </Callout>
        </div>
      )}
    </AdaptiveModal>
  );
}
