import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Badge } from '@/shared/ui/badge'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/ui/tooltip'
import { Card, CardContent, CardHeader } from '@/shared/ui/card'
import { t } from '@/shared/i18n/ru'
import { todayMSK } from '@/shared/i18n/date'
import { isDomainError } from '@/shared/api/errors'
import { useClientsList } from '@/features/clients/api/hooks'
import type { Client } from '@/entities/client'
import { useDebounceValue } from '@/shared/lib/hooks/useDebounceValue'
import { useGymMeta, useRecentVisitsByClient, useCheckIn, useMembershipStatusForClient } from '../api/hooks'

// formatTimeMSK: returns HH:mm pinned to Europe/Moscow regardless of runtime TZ.
// FE-08(d) TZ correctness: pinned to Europe/Moscow because date-fns formatTime() in
// shared/i18n/date.ts renders in the JS runtime's local zone (not MSK).
// Do not replace with formatTime().
function formatTimeMSK(iso: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Europe/Moscow',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(iso))
}

// nowHHmmMSK: current wall-clock HH:mm in Europe/Moscow for FE-08(d) string compare.
// Lexicographic compare is correct for zero-padded HH:mm strings.
function nowHHmmMSK(): string {
  return formatTimeMSK(new Date().toISOString())
}

interface CheckInCardProps {
  client: Client
  onSuccess: () => void
}

function CheckInCard({ client, onSuccess }: CheckInCardProps) {
  const [serverError, setServerError] = useState<string | null>(null)

  const { data: gymMetaData } = useGymMeta()
  const gymHoursStart = gymMetaData?.gymHoursStart ?? '07:00'
  const gymHoursEnd = gymMetaData?.gymHoursEnd ?? '23:00'

  const { data: recentVisits } = useRecentVisitsByClient(client.id, { limit: 1 })
  const { activeMembership, expiringToday } = useMembershipStatusForClient(client.id)

  const checkIn = useCheckIn()

  // FE-08(b): already checked in today
  const todayVisit = recentVisits?.[0]?.gymDate === todayMSK() ? recentVisits[0] : null

  // FE-08(d): outside gym hours (Europe/Moscow wall-clock)
  const now = nowHHmmMSK()
  const isOutsideHours = now < gymHoursStart || now >= gymHoursEnd

  // Determine if button should be disabled
  const isButtonDisabled = !!todayVisit || isOutsideHours || checkIn.isPending

  function handleCheckIn() {
    setServerError(null)
    checkIn.mutate(client.id, {
      onSuccess: () => {
        toast.success(t('visits.toast.success'))
        onSuccess()
      },
      onError: (err) => {
        if (isDomainError(err)) {
          if (err.code === 'no_active_membership') {
            setServerError(t('visits.errors.noActiveMembership'))
          } else if (err.code === 'duplicate_checkin') {
            setServerError(t('visits.errors.duplicateCheckin'))
          } else if (err.code === 'outside_gym_hours') {
            setServerError(
              t('visits.errors.outsideGymHours')
                .replace('{open}', gymHoursStart)
                .replace('{close}', gymHoursEnd),
            )
          } else {
            setServerError(err.message)
          }
        } else {
          setServerError(t('common.errors.network'))
        }
      },
    })
  }

  // Map channel enum to display label
  function channelLabel(channel: string): string {
    if (channel === 'telegram_bot') return t('visits.checkin.channel.telegram')
    return t('visits.checkin.channel.reception')
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <p className="text-base font-semibold">{client.fullName}</p>
          <p className="text-sm text-muted-foreground">{client.phone}</p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* FE-08(c): membership expiring today — informational badge, button stays ENABLED */}
        {expiringToday && (
          <Badge variant="outline">{t('memberships.badge.expiresToday')}</Badge>
        )}

        {/* No active membership warning */}
        {!activeMembership && (
          <Alert variant="destructive">
            <AlertDescription>{t('visits.errors.noActiveMembership')}</AlertDescription>
          </Alert>
        )}

        {/* FE-08(b): already checked in today */}
        {todayVisit && (
          <Badge variant="secondary">
            {t('visits.checkin.alreadyCheckedIn')
              .replace('{time}', formatTimeMSK(todayVisit.checkedInAt))
              .replace('{channel}', channelLabel(todayVisit.channel))}
          </Badge>
        )}

        {/* FE-08(d): outside gym hours */}
        {isOutsideHours && !todayVisit && (
          <p className="text-sm text-muted-foreground">
            {t('visits.checkin.outsideHours')
              .replace('{start}', gymHoursStart)
              .replace('{end}', gymHoursEnd)}
          </p>
        )}

        {/* Server error from 409 responses */}
        {serverError && (
          <Alert variant="destructive">
            <AlertDescription>{serverError}</AlertDescription>
          </Alert>
        )}

        {/* Primary CTA */}
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-block w-full">
                <Button
                  size="lg"
                  className="w-full"
                  disabled={isButtonDisabled}
                  aria-disabled={isButtonDisabled}
                  onClick={handleCheckIn}
                >
                  {checkIn.isPending ? t('visits.checkin.submitting') : t('visits.checkin.button')}
                </Button>
              </span>
            </TooltipTrigger>
            {isOutsideHours && (
              <TooltipContent>
                {t('visits.checkin.tooltip.outsideHours')
                  .replace('{start}', gymHoursStart)
                  .replace('{end}', gymHoursEnd)}
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </CardContent>
    </Card>
  )
}

export function CheckInPage() {
  const [phoneQuery, setPhoneQuery] = useState('')
  const [selectedClient, setSelectedClient] = useState<Client | null>(null)

  const debouncedPhone = useDebounceValue(phoneQuery, 250)

  // FE-08(a): phone-prefix search — top 5 matches
  const { data: clientsData } = useClientsList({
    q: debouncedPhone,
    page: 1,
    pageSize: 5,
  })
  const candidates = clientsData?.items ?? []
  const showList = debouncedPhone.length >= 2 && !selectedClient

  function handleSelectClient(client: Client) {
    setSelectedClient(client)
  }

  function handleReset() {
    setPhoneQuery('')
    setSelectedClient(null)
  }

  return (
    <div className="container mx-auto max-w-xl px-4 py-8 space-y-6">
      <h1 className="text-xl font-semibold">{t('visits.heading')}</h1>

      <div className="space-y-2">
        <Label htmlFor="phone-search">{t('visits.search.label')}</Label>
        <Input
          id="phone-search"
          type="tel"
          placeholder={t('visits.search.placeholder')}
          value={phoneQuery}
          onChange={(e) => {
            setPhoneQuery(e.target.value)
            setSelectedClient(null)
          }}
        />
      </div>

      {/* FE-08(a): Disambiguation list */}
      {showList && (
        <div>
          {candidates.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('visits.checkin.noClient')}</p>
          ) : (
            <ul role="listbox" className="space-y-1 rounded-md border bg-card">
              {candidates.map((client) => (
                <li
                  key={client.id}
                  role="option"
                  tabIndex={0}
                  aria-selected={false}
                  className="cursor-pointer rounded-md px-4 py-3 hover:bg-accent"
                  onClick={() => handleSelectClient(client)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') handleSelectClient(client)
                  }}
                >
                  <span className="font-medium">{client.fullName}</span>
                  <span className="ml-2 text-sm text-muted-foreground">{client.phone}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* CheckInCard for selected client */}
      {selectedClient && (
        <CheckInCard
          client={selectedClient}
          onSuccess={handleReset}
        />
      )}
    </div>
  )
}
