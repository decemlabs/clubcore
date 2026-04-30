import { Button } from '@/shared/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip'
import { t } from '@/shared/i18n'
import { Bell } from 'lucide-react'

export function NotificationsBell() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={t('shell.notifications.label')}>
          <Bell className="size-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{t('shell.notifications.empty')}</TooltipContent>
    </Tooltip>
  )
}
