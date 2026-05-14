import { Badge } from '@/shared/ui/badge'
import { t } from '@/shared/i18n'

interface Props {
  isActive: boolean
}

export function TrainerStatusBadge({ isActive }: Props) {
  if (isActive) {
    return <Badge variant="default">{t('trainers.status.active')}</Badge>
  }
  return (
    <Badge
      variant="outline"
      className="border-warning/30 bg-warning/10 text-warning-foreground"
    >
      {t('trainers.status.inactive')}
    </Badge>
  )
}
