/**
 * BookingModal — create a PT booking from an available calendar slot (Phase 102-03 SCH-02).
 *
 * Opened when user clicks an available slot in WeekCalendar.
 * Props: slotId, trainerId, trainerFullName, slotStartTime, slotEndTime, open, onOpenChange.
 *
 * Flow:
 *  1. Staff searches for a client (debounced 300ms).
 *  2. Staff selects an active PT-package for the chosen client.
 *  3. Staff clicks «Записать» → POST /api/v1/bookings with a fresh Idempotency-Key.
 *
 * Race-safe (T-102-BK-RACE):
 *  - 409 slot_already_booked / slot_not_available → inline Callout + calendar invalidate, modal stays open.
 *  - 409 PT-package errors → inline Callout with mapped Russian copy, modal stays open.
 *  - NEVER crashes the page.
 *
 * ESLint import-boundary: ApiError imported via @/features/bookings/api (re-export); scheduleKeys
 * imported from @/features/schedule/keys (feature module boundary is acceptable for cross-module keys).
 */
import { useEffect, useState, useCallback } from 'react'
import { toast } from 'sonner'
import { CalendarCheck, Loader2, Search, TriangleAlert, X as XIcon } from '@/components/icons'
import { Skeleton } from '@/components/ui/skeleton'
import { AdaptiveModal } from './AdaptiveModal'
import {
  Callout,
  IconChip,
  ModalButton,
  ModalInput,
  PlanCards,
  ResultItem,
  ResultList,
  Section,
} from './fields'
import { useClients } from '@/features/clients/api'
import { usePtPackagesByClient } from '@/features/pt-packages/api'
import { useCreateBooking, ApiError } from '@/features/bookings/api'
import { scheduleKeys } from '@/features/schedule/keys'
import { useQueryClient } from '@tanstack/react-query'
import { formatTime, formatDateRu } from '@/lib/format'
import type { PlanOption } from './fields'

// PT-package 409 error codes → friendly Russian copy
const PT_PACKAGE_ERROR_COPY: Record<string, string> = {
  pt_package_not_active: 'Пакет PT неактивен',
  pt_package_exhausted: 'Все занятия в пакете уже использованы',
  pt_package_expired_before_slot: 'Срок действия пакета истечёт до даты слота',
  trainer_mismatch: 'Тренер в пакете не совпадает с тренером слота',
}

interface BookingModalProps {
  slotId: string
  trainerId: string
  trainerFullName: string
  /** ISO string for slot start time */
  slotStartTime: string
  /** ISO string for slot end time */
  slotEndTime: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Format slot time for display: «20 июня 10:00–11:00» */
function formatSlotDisplay(startTime: string, endTime: string): string {
  return `${formatDateRu(startTime, 'd MMMM')} ${formatTime(startTime)}–${formatTime(endTime)}`
}

export function BookingModal({
  slotId,
  trainerFullName,
  slotStartTime,
  slotEndTime,
  open,
  onOpenChange,
}: BookingModalProps) {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
  const [selectedClientName, setSelectedClientName] = useState<string | null>(null)
  const [selectedPtPackageId, setSelectedPtPackageId] = useState<string | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)

  // Debounce search input (300ms)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  // Reset on modal open (pattern from BookModal.tsx)
  useEffect(() => {
    if (open) {
      setSearch('')
      setDebouncedSearch('')
      setSelectedClientId(null)
      setSelectedClientName(null)
      setSelectedPtPackageId(null)
      setApiError(null)
    }
  }, [open])

  // All hooks before any conditional return
  const clientsQuery = useClients({ q: debouncedSearch })
  const ptPackagesQuery = usePtPackagesByClient(selectedClientId ?? '')
  const createBooking = useCreateBooking()
  const isPending = createBooking.isPending

  const handleBook = useCallback(async () => {
    if (!selectedClientId || !selectedPtPackageId) return
    setApiError(null)
    try {
      await createBooking.mutateAsync({
        slotId,
        clientId: selectedClientId,
        ptPackageId: selectedPtPackageId,
      })
      toast.success('Запись создана', {
        description: `${selectedClientName ?? ''} · ${trainerFullName} · ${formatTime(slotStartTime)}–${formatTime(slotEndTime)}`,
      })
      onOpenChange(false)
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 'slot_already_booked') {
          setApiError('Слот уже занят')
          // Calendar invalidate so the user sees the updated state on close
          void qc.invalidateQueries({ queryKey: scheduleKeys.all })
        } else if (err.code === 'slot_not_available') {
          setApiError('Слот недоступен')
          void qc.invalidateQueries({ queryKey: scheduleKeys.all })
        } else {
          setApiError(PT_PACKAGE_ERROR_COPY[err.code] ?? err.message)
        }
      }
      // Modal stays open — user manually closes (never crash)
    }
  }, [
    selectedClientId,
    selectedPtPackageId,
    createBooking,
    slotId,
    selectedClientName,
    trainerFullName,
    slotStartTime,
    slotEndTime,
    onOpenChange,
    qc,
  ])

  const handleOpenChange = isPending ? () => {} : onOpenChange

  const clients = clientsQuery.data?.items ?? []
  const isSearching = debouncedSearch.length > 0 && clientsQuery.isFetching

  /** Derive full name from firstName + lastName */
  function clientFullName(c: { firstName: string; lastName: string }): string {
    return `${c.firstName} ${c.lastName}`.trim()
  }

  // PT-packages for the selected client (filtered to active only)
  const ptPackages = (ptPackagesQuery.data?.items ?? []).filter(
    (pkg) => pkg.status === 'active',
  )

  // Build PlanCards options from active PT-packages
  const planOptions: PlanOption[] = ptPackages.map((pkg) => ({
    value: pkg.id,
    name: pkg.planSnapshot.name,
    price: `Осталось: ${pkg.sessionsRemaining} из ${pkg.sessionsTotal}`,
    sub: 'PT-пакет',
  }))

  const footerInfo =
    selectedClientId ? (
      <span>
        <b className="font-semibold text-fg">{selectedClientName}</b> ·{' '}
        {trainerFullName} · {formatTime(slotStartTime)}–{formatTime(slotEndTime)}
      </span>
    ) : null

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={handleOpenChange}
      icon={<IconChip tone="accent" icon={CalendarCheck} />}
      title="Записать клиента"
      description={`${trainerFullName} · ${formatSlotDisplay(slotStartTime, slotEndTime)}`}
      footerInfo={footerInfo}
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton
            variant="primary"
            disabled={!selectedClientId || !selectedPtPackageId || isPending}
            onClick={() => void handleBook()}
          >
            {isPending ? <Loader2 className="size-4 animate-spin" /> : null}
            Записать
          </ModalButton>
        </>
      }
    >
      {/* Client section */}
      <Section>Клиент</Section>
      <div className="relative mb-3.5">
        <ModalInput
          icon={Search}
          placeholder="Найти по имени или телефону…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            // Deselect client when search changes
            if (selectedClientId) {
              setSelectedClientId(null)
              setSelectedClientName(null)
              setSelectedPtPackageId(null)
            }
          }}
        />
        {isSearching && (
          <Loader2 className="pointer-events-none absolute right-3.5 top-1/2 size-4 -translate-y-1/2 animate-spin text-fg-subtle" />
        )}
      </div>

      {/* Show selected client as highlighted row */}
      {selectedClientId ? (
        <ResultList>
          <ResultItem
            initials={getInitials(selectedClientName ?? '')}
            color="#2dd4a4"
            name={selectedClientName ?? ''}
            meta=""
            active
            aside={
              <button
                type="button"
                aria-label="Снять выбор клиента"
                className="text-fg-muted hover:text-fg"
                onClick={() => {
                  setSelectedClientId(null)
                  setSelectedClientName(null)
                  setSelectedPtPackageId(null)
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
                color="#2dd4a4"
                name={clientFullName(client)}
                meta={client.phone ?? ''}
                onClick={() => {
                  setSelectedClientId(client.id)
                  setSelectedClientName(clientFullName(client))
                  setSearch('')
                  setDebouncedSearch('')
                }}
              />
            ))}
          </ResultList>
        )
      ) : null}

      {/* PT-package section — shown only after client selected */}
      {selectedClientId && (
        <>
          <Section>Пакет PT</Section>
          {ptPackagesQuery.isPending ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-11 w-full rounded-xl" />
              <Skeleton className="h-11 w-full rounded-xl" />
              <Skeleton className="h-11 w-full rounded-xl" />
            </div>
          ) : planOptions.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border-[0.5px] border-border bg-surface py-5 text-center">
              <div className="text-[13.5px] font-semibold">Нет активных PT-пакетов</div>
              <div className="mt-1 text-[11.5px] text-fg-subtle">
                У клиента нет доступных персональных занятий.
              </div>
            </div>
          ) : (
            <PlanCards
              options={planOptions}
              value={selectedPtPackageId ?? ''}
              onChange={(v) => setSelectedPtPackageId(v)}
            />
          )}
        </>
      )}

      {/* Race-conflict inline Callout (T-102-BK-RACE) */}
      {apiError && (
        <div className="mt-3.5">
          <Callout tone="danger" icon={TriangleAlert}>
            <span className="font-semibold">{apiError}</span>
            {(apiError === 'Слот уже занят' || apiError === 'Слот недоступен') && (
              <span className="block text-[11.5px] mt-0.5">
                Кто-то успел записаться раньше. Закройте это окно — расписание обновится.
              </span>
            )}
          </Callout>
        </div>
      )}
    </AdaptiveModal>
  )
}

function getInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  return words
    .slice(0, 2)
    .map((w) => w.charAt(0)?.toUpperCase() ?? '')
    .join('')
}
