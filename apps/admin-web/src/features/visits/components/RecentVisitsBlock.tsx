import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Skeleton } from '@/shared/ui/skeleton'
import { Badge } from '@/shared/ui/badge'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { t } from '@/shared/i18n/ru'
import { formatDate } from '@/shared/i18n/date'
import { useRecentVisitsByClient } from '../api/hooks'

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

interface Props {
  clientId: string
}

export function RecentVisitsBlock({ clientId }: Props) {
  const { data: visits, isPending, isError } = useRecentVisitsByClient(clientId, { limit: 20 })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold">{t('visits.recentBlock.heading')}</CardTitle>
      </CardHeader>
      <CardContent>
        {isPending && (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-20" />
              </div>
            ))}
          </div>
        )}

        {isError && (
          <Alert variant="destructive">
            <AlertDescription>{t('visits.recentBlock.error')}</AlertDescription>
          </Alert>
        )}

        {!isPending && !isError && visits && visits.length === 0 && (
          <p className="text-muted-foreground text-center text-sm py-4">
            {t('visits.recentBlock.empty')}
          </p>
        )}

        {!isPending && !isError && visits && visits.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-muted-foreground">
                <th className="py-2 text-left font-medium">{t('visits.columns.date')}</th>
                <th className="py-2 text-left font-medium">{t('visits.columns.time')}</th>
                <th className="py-2 text-left font-medium">{t('visits.columns.channel')}</th>
              </tr>
            </thead>
            <tbody>
              {visits.map((v) => (
                <tr key={v.id} className="border-b last:border-0">
                  <td className="py-2">{formatDate(v.checkedInAt)}</td>
                  <td className="py-2">
                    {/* formatTimeMSK pins to Europe/Moscow — see comment above */}
                    {formatTimeMSK(v.checkedInAt)}
                  </td>
                  <td className="py-2">
                    <Badge variant="outline">
                      {v.channel === 'telegram_bot'
                        ? t('visits.channel.telegram')
                        : t('visits.channel.reception')}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  )
}
