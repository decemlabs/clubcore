import { Loader2 } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/ui/tooltip'
import { RoleGate } from '@/shared/session/RoleGate'
import { useFreezeMembership, useUnfreezeMembership } from '@/features/memberships/api/hooks'
import { t } from '@/shared/i18n'
import { formatDate } from '@/shared/i18n/date'
import type { Membership } from '@/entities/membership'

interface Props {
  membership: Membership
}

export function FreezeSection({ membership }: Props) {
  const freeze = useFreezeMembership()
  const unfreeze = useUnfreezeMembership()

  // Hide entirely for non-active/non-frozen
  if (membership.status !== 'active' && membership.status !== 'frozen') return null

  const used = membership.freezeDaysUsed
  const limit = membership.freezeDaysLimitSnapshot
  const remaining = membership.freezeDaysRemaining

  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">{t('memberships.detail.section.freeze')}</h2>
      <p className="text-muted-foreground text-sm">
        Использовано: {used} из {limit} дн.
      </p>

      {membership.status === 'active' && (
        <RoleGate action="create" resource="memberships">
          {remaining > 0 ? (
            <Button
              variant="outline"
              size="sm"
              disabled={freeze.isPending}
              onClick={() =>
                freeze.mutate({ membershipId: membership.id, clientId: membership.clientId })
              }
            >
              {freeze.isPending ? (
                <Loader2 className="animate-spin" size={14} />
              ) : (
                t('memberships.freeze.button')
              )}
            </Button>
          ) : (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0}>
                    <Button variant="outline" size="sm" disabled>
                      {t('memberships.freeze.button')}
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent>{t('memberships.freeze.no_days_remaining')}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </RoleGate>
      )}

      {membership.status === 'frozen' && membership.currentFreezePeriod && (
        <div className="flex items-center gap-3">
          <RoleGate action="create" resource="memberships">
            <Button
              variant="outline"
              size="sm"
              disabled={unfreeze.isPending}
              onClick={() =>
                unfreeze.mutate({ membershipId: membership.id, clientId: membership.clientId })
              }
            >
              {unfreeze.isPending ? (
                <Loader2 className="animate-spin" size={14} />
              ) : (
                t('memberships.unfreeze.button')
              )}
            </Button>
          </RoleGate>
          <Badge
            variant="outline"
            className="bg-warning/10 text-warning-foreground border-warning/30"
          >
            {t('memberships.frozen.badge').replace(
              '{date}',
              formatDate(membership.currentFreezePeriod.startedAt),
            )}
          </Badge>
        </div>
      )}
    </section>
  )
}
