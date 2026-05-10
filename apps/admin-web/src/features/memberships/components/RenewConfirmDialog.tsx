import { addDays, parseISO } from 'date-fns'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/ui/alert-dialog'
import { useRenewMembership } from '@/features/memberships/api/hooks'
import { formatMoney } from '@/shared/lib/money'
import { formatDate, todayMSK } from '@/shared/i18n/date'
import { t } from '@/shared/i18n'
import type { Membership } from '@/entities/membership'

interface Props {
  membership: Membership
  open: boolean
  onClose: () => void
}

export function RenewConfirmDialog({ membership, open, onClose }: Props) {
  const renew = useRenewMembership()

  const computedStart =
    membership.status === 'expired'
      ? todayMSK()
      : addDays(parseISO(membership.endDate), 1).toISOString().slice(0, 10)
  const computedEnd = addDays(parseISO(computedStart), membership.durationDaysSnapshot - 1)
    .toISOString()
    .slice(0, 10)

  const body = t('memberships.renew.confirm.body')
    .replace('{plan}', membership.planNameSnapshot)
    .replace('{price}', formatMoney(membership.priceKopecksSnapshot))
    .replace('{startDate}', formatDate(computedStart))
    .replace('{endDate}', formatDate(computedEnd))

  const handleConfirm = () => {
    renew.mutate(
      { membershipId: membership.id, clientId: membership.clientId },
      { onSettled: () => onClose() },
    )
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t('memberships.renew.confirm.title')}</AlertDialogTitle>
          <AlertDialogDescription className="whitespace-pre-line">{body}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={renew.isPending}>
            {t('memberships.renew.confirm.cancel')}
          </AlertDialogCancel>
          <AlertDialogAction disabled={renew.isPending} onClick={handleConfirm}>
            {renew.isPending ? '…' : t('memberships.renew.confirm.cta')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
