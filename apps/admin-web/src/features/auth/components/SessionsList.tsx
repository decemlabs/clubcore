import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Skeleton } from '@/shared/ui/skeleton'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { ApiError, isDomainError } from '@/shared/api/errors'
import { t } from '@/shared/i18n'
import { formatDate } from '@/shared/i18n/date'
import { useActiveSessions, useRevokeSession } from '../api/sessionsHooks'
import { LogoutAllDialog } from './LogoutAllDialog'
import type { SessionChannel, SessionFamily } from '@/shared/api/contracts/auth'

function ChannelBadge({ channel }: { channel: SessionChannel }) {
  if (channel === 'email') return <Badge variant="outline">{t('sessions.channel.email')}</Badge>
  if (channel === 'telegram_bot')
    return <Badge variant="outline">{t('sessions.channel.telegram')}</Badge>
  return <Badge variant="outline">{t('sessions.channel.unknown')}</Badge>
}

function SessionRow({ session }: { session: SessionFamily }) {
  const revoke = useRevokeSession()

  const handleRevoke = () => {
    revoke.mutate(session.familyId, {
      onSuccess: () => {
        toast.success(t('sessions.toast.revoked'))
      },
      onError: (err) => {
        const fallback = t('auth.errors.network')
        toast.error(
          isDomainError(err)
            ? err.message
            : err instanceof ApiError
              ? err.message
              : fallback,
        )
      },
    })
  }

  return (
    <li className="flex items-center gap-4 border-b py-3 last:border-b-0">
      <ChannelBadge channel={session.channel} />
      <div className="flex flex-col">
        <span className="text-sm">{formatDate(session.createdAt)}</span>
        {session.userAgent && (
          <span className="text-muted-foreground line-clamp-1 text-xs">{session.userAgent}</span>
        )}
      </div>
      {session.isCurrent && (
        <Badge variant="secondary" className="ml-2">
          {t('sessions.current')}
        </Badge>
      )}
      <div className="flex-1" />
      <Button
        variant="ghost"
        size="sm"
        onClick={handleRevoke}
        disabled={revoke.isPending}
        aria-label={`${t('sessions.revoke')} ${session.familyId}`}
      >
        {revoke.isPending ? '…' : t('sessions.revoke')}
      </Button>
    </li>
  )
}

/**
 * FE-09 — list of active session families with per-row revoke + a destructive
 * "logout from all devices" button. Wired exclusively to the http auth service
 * (D-22-2: mock throws `mock_not_implemented`).
 */
export function SessionsList() {
  const query = useActiveSessions()
  const [logoutAllOpen, setLogoutAllOpen] = useState(false)

  return (
    <div className="space-y-4">
      {query.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 py-2">
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      )}

      {query.isError && (
        <Alert variant="destructive">
          <AlertDescription>
            {isDomainError(query.error) && query.error.code === 'mock_not_implemented'
              ? t('sessions.errors.mockNotImplemented')
              : t('sessions.error')}
          </AlertDescription>
        </Alert>
      )}

      {query.isSuccess && query.data.length === 0 && (
        <p className="text-muted-foreground text-sm">{t('sessions.empty')}</p>
      )}

      {query.isSuccess && query.data.length > 0 && (
        <ul className="divide-border">
          {query.data.map((s) => (
            <SessionRow key={s.familyId} session={s} />
          ))}
        </ul>
      )}

      <Button
        variant="destructive"
        size="sm"
        className="mt-4"
        onClick={() => setLogoutAllOpen(true)}
      >
        {t('sessions.logoutAll')}
      </Button>

      <LogoutAllDialog open={logoutAllOpen} onClose={() => setLogoutAllOpen(false)} />
    </div>
  )
}
