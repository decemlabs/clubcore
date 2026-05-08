import { useState } from 'react'
import { toast } from 'sonner'
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
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { isDomainError } from '@/shared/api/errors'
import { t } from '@/shared/i18n'
import { useCancelMembership } from '../api/hooks'
import type { MembershipId } from '@/entities/membership'

interface Props {
  open: boolean
  onClose: () => void
  membershipId: MembershipId
}

export function CancelMembershipDialog({ open, onClose, membershipId }: Props) {
  const cancel = useCancelMembership()
  const [reason, setReason] = useState('')
  const [inlineError, setInlineError] = useState<string | null>(null)

  const handleConfirm = () => {
    setInlineError(null)
    cancel.mutate(
      { membershipId, reason: reason.trim() || undefined },
      {
        onSuccess: () => {
          toast.success(t('memberships.toast.cancelled'))
          onClose()
        },
        onError: (err) => {
          const code = isDomainError(err) ? err.code : undefined
          if (code === 'invalid_transition') {
            setInlineError(t('memberships.errors.invalidTransition'))
          } else {
            toast.error(isDomainError(err) ? err.message : 'Ошибка соединения.')
            onClose()
          }
        },
      },
    )
  }

  return (
    <AlertDialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setReason('')
          setInlineError(null)
          onClose()
        }
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t('memberships.dialog.cancelTitle')}</AlertDialogTitle>
          <AlertDialogDescription>{t('memberships.dialog.cancelBody')}</AlertDialogDescription>
        </AlertDialogHeader>

        <div className="my-3">
          <textarea
            className="border-border bg-background text-foreground placeholder:text-muted-foreground focus:ring-ring w-full rounded-md border px-3 py-2 text-sm focus:ring-1 focus:outline-none"
            rows={3}
            placeholder={t('memberships.dialog.cancelReason')}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>

        {inlineError && (
          <Alert variant="destructive" className="mb-3">
            <AlertDescription>{inlineError}</AlertDescription>
          </Alert>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel
            disabled={cancel.isPending}
            onClick={() => {
              setReason('')
              setInlineError(null)
              onClose()
            }}
          >
            {t('memberships.dialog.cancelAbort')}
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={cancel.isPending}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={handleConfirm}
          >
            {cancel.isPending ? '…' : t('memberships.dialog.cancelConfirm')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
