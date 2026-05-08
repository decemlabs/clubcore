import { useNavigate } from '@tanstack/react-router'
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
import { isDomainError } from '@/shared/api/errors'
import { t } from '@/shared/i18n'
import { useLogoutAll } from '../api/sessionsHooks'

interface Props {
  open: boolean
  onClose: () => void
}

/**
 * FE-09 destructive confirm for "Выйти со всех устройств".
 *
 * Wraps `useLogoutAll` (which calls `qc.clear()` on success). On confirm:
 * sonner toast → navigate to /login (the protected route layout will also
 * redirect away once the session evaporates server-side).
 */
export function LogoutAllDialog({ open, onClose }: Props) {
  const logoutAll = useLogoutAll()
  const navigate = useNavigate()

  const handleConfirm = () => {
    logoutAll.mutate(undefined, {
      onSuccess: () => {
        toast.success(t('sessions.toast.loggedOutAll'))
        onClose()
        void navigate({ to: '/login', replace: true })
      },
      onError: (err) => {
        toast.error(isDomainError(err) ? err.message : 'Ошибка соединения.')
        onClose()
      },
    })
  }

  return (
    <AlertDialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose()
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t('sessions.logoutAllConfirm.title')}</AlertDialogTitle>
          <AlertDialogDescription>{t('sessions.logoutAllConfirm.body')}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={logoutAll.isPending} onClick={onClose}>
            {t('sessions.logoutAllConfirm.cancel')}
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={logoutAll.isPending}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={handleConfirm}
          >
            {logoutAll.isPending ? '…' : t('sessions.logoutAllConfirm.action')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
