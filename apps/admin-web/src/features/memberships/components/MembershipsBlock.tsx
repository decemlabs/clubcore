import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { Skeleton } from '@/shared/ui/skeleton'
import { RoleGate } from '@/shared/session/RoleGate'
import { t } from '@/shared/i18n'
import { formatDate, todayMSK } from '@/shared/i18n/date'
import { useMembershipsByClient } from '../api/hooks'
import { SellMembershipDialog } from './SellMembershipDialog'
import { CancelMembershipDialog } from './CancelMembershipDialog'
import type { Membership, MembershipId } from '@/entities/membership'

interface Props {
  clientId: string
}

function StatusBadge({ status }: { status: Membership['status'] }) {
  if (status === 'active') return <Badge variant="default">{t('memberships.status.active')}</Badge>
  if (status === 'expired') return <Badge variant="secondary">{t('memberships.status.expired')}</Badge>
  return <Badge variant="outline">{t('memberships.status.cancelled')}</Badge>
}

export function MembershipsBlock({ clientId }: Props) {
  const query = useMembershipsByClient(clientId)
  const [sellOpen, setSellOpen] = useState(false)
  const [cancelId, setCancelId] = useState<MembershipId | null>(null)

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="text-base font-semibold">
          {t('clientProfile.membershipsBlock')}
        </CardTitle>
        <Button size="sm" onClick={() => setSellOpen(true)}>
          {t('memberships.actions.sell')}
        </Button>
      </CardHeader>
      <CardContent>
        {query.isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex gap-4">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-16" />
              </div>
            ))}
          </div>
        )}

        {query.isError && (
          <Alert variant="destructive">
            <AlertDescription>{t('memberships.error.heading')}</AlertDescription>
          </Alert>
        )}

        {query.isSuccess && query.data.items.length === 0 && (
          <div className="space-y-3 py-6 text-center">
            <p className="text-muted-foreground text-sm">{t('memberships.empty.heading')}</p>
            <Button size="sm" variant="outline" onClick={() => setSellOpen(true)}>
              {t('memberships.actions.sell')}
            </Button>
          </div>
        )}

        {query.isSuccess && query.data.items.length > 0 && (
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="pb-2 text-left font-medium">Тариф</th>
                  <th className="pb-2 text-left font-medium">Период</th>
                  <th className="pb-2 text-left font-medium">Статус</th>
                  <th className="pb-2 text-right font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((m) => (
                  <tr key={m.id} className="border-b last:border-0">
                    <td className="py-2 pr-4">{m.planNameSnapshot}</td>
                    <td className="text-muted-foreground py-2 pr-4">
                      {formatDate(m.startDate)}–{formatDate(m.endDate)}
                      {m.status === 'active' && m.endDate === todayMSK() && (
                        <Badge variant="secondary" className="ml-2 text-xs">
                          {t('memberships.badge.expiresToday')}
                        </Badge>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      <StatusBadge status={m.status} />
                    </td>
                    <td className="py-2 text-right">
                      <RoleGate action="cancel" resource="memberships">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          onClick={() => setCancelId(m.id)}
                          disabled={m.status !== 'active'}
                        >
                          {t('memberships.actions.cancel')}
                        </Button>
                      </RoleGate>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      <SellMembershipDialog
        open={sellOpen}
        onClose={() => setSellOpen(false)}
        clientId={clientId}
      />

      {cancelId && (
        <CancelMembershipDialog
          open={!!cancelId}
          onClose={() => setCancelId(null)}
          membershipId={cancelId}
        />
      )}
    </Card>
  )
}
