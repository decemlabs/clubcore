import { createFileRoute, redirect } from '@tanstack/react-router'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { can } from '@/shared/session/can'
import { t } from '@/shared/i18n'
import { SessionsList } from '@/features/auth'

/**
 * FE-09 / Warning 2 fix: own-account profile surface accessible to BOTH roles.
 *
 * The existing /_protected/settings route is owner-only (settings.tsx:6-13
 * redirects reception via can(role, 'view', 'settings')). Reception must be
 * able to manage their own active sessions, so a NEW /_protected/profile
 * route is required. The 'profile' resource is added to can.ts but is NOT
 * in OWNER_ONLY — both roles pass `can(_, 'view', 'profile')`.
 *
 * The beforeLoad below is defense-in-depth (mirrors settings.tsx structure).
 * It will only deny if some future role configuration revokes profile-view.
 */
function ProfilePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{t('profile.heading')}</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">{t('sessions.heading')}</CardTitle>
        </CardHeader>
        <CardContent>
          <SessionsList />
        </CardContent>
      </Card>
    </div>
  )
}

export const Route = createFileRoute('/_protected/profile')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'profile')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  component: ProfilePage,
})
