import { createFileRoute, Link, redirect, useParams } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { can } from '@/shared/session/can'
import { membershipsKeys } from '@/features/memberships/api/keys'
import { services } from '@/shared/api/services'
import { StatusBadge } from '@/features/memberships/components/StatusBadge'
import { FreezeSection } from '@/features/memberships/components/FreezeSection'
import { RenewSection } from '@/features/memberships/components/RenewSection'
import { Card, CardContent, CardHeader } from '@/shared/ui/card'
import { Skeleton } from '@/shared/ui/skeleton'
import { formatMoney } from '@/shared/lib/money'
import { formatDate } from '@/shared/i18n/date'
import { t } from '@/shared/i18n'
import type { MembershipId } from '@/entities/membership'

export const Route = createFileRoute('/_protected/memberships_/$membershipId')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'memberships')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loader: ({ context, params }) => {
    const id = params.membershipId as MembershipId
    return context.queryClient.ensureQueryData({
      queryKey: membershipsKeys.detail(id),
      queryFn: () => services.memberships.get(id),
    })
  },
  component: MembershipDetailPage,
})

export function MembershipDetailPage() {
  const { membershipId } = useParams({ from: '/_protected/memberships_/$membershipId' })
  const id = membershipId as MembershipId
  const { data: membership, isLoading } = useQuery({
    queryKey: membershipsKeys.detail(id),
    queryFn: () => services.memberships.get(id),
  })

  if (isLoading || !membership) {
    return (
      <main className="container mx-auto space-y-8 px-4 py-6">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </main>
    )
  }

  return (
    <main className="container mx-auto space-y-8 px-4 py-6">
      <Link to="/memberships" className="text-muted-foreground text-sm">
        ← {t('memberships.heading')}
      </Link>

      <Card>
        <CardHeader>
          <h1 className="text-xl font-semibold">{t('memberships.detail.title')}</h1>
        </CardHeader>
        <CardContent className="space-y-2">
          <Link
            to="/clients/$clientId"
            params={{ clientId: membership.clientId }}
            className="text-sm underline-offset-4 hover:underline"
          >
            {membership.clientId}
          </Link>
          <p className="text-sm">
            {membership.planNameSnapshot} · {membership.durationDaysSnapshot} дн.
          </p>
          <p className="text-sm">{formatMoney(membership.priceKopecksSnapshot)}</p>
          <div className="flex items-center gap-2">
            <StatusBadge status={membership.status} />
          </div>
          <p className="text-muted-foreground text-sm">
            {formatDate(membership.startDate)} – {formatDate(membership.endDate)}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <FreezeSection membership={membership} />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <RenewSection membership={membership} />
        </CardContent>
      </Card>

      {membership.previousMembershipId && (
        <Card>
          <CardContent className="pt-6 text-sm">
            <Link
              to="/memberships/$membershipId"
              params={{ membershipId: membership.previousMembershipId as MembershipId }}
              className="underline-offset-4 hover:underline"
            >
              {t('memberships.detail.previousMembership')}
            </Link>
          </CardContent>
        </Card>
      )}
    </main>
  )
}
