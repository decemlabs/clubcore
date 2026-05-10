import { Badge } from '@/shared/ui/badge'
import { t } from '@/shared/i18n'
import type { MembershipStatus } from '@/entities/membership'

interface Props {
  status: MembershipStatus
}

export function StatusBadge({ status }: Props) {
  if (status === 'active')
    return <Badge variant="default">{t('memberships.status.active')}</Badge>
  if (status === 'expired')
    return <Badge variant="secondary">{t('memberships.status.expired')}</Badge>
  if (status === 'cancelled')
    return <Badge variant="outline">{t('memberships.status.cancelled')}</Badge>
  // 'frozen' — semantic warning token override (NOT raw palette)
  return (
    <Badge variant="outline" className="bg-warning text-warning-foreground border-warning/50">
      {t('memberships.status.frozen')}
    </Badge>
  )
}
