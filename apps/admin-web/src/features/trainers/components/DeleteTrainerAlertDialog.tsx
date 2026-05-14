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
import { useDeleteTrainer } from '../api/hooks'
import type { Trainer } from '@/entities/trainer'

interface Props {
  open: boolean
  onClose: () => void
  trainer: Trainer
}

export function DeleteTrainerAlertDialog({ open, onClose, trainer }: Props) {
  const deleteTrainer = useDeleteTrainer()
  const [inlineError, setInlineError] = useState<string | null>(null)

  const handleConfirm = () => {
    setInlineError(null)
    deleteTrainer.mutate(trainer.id, {
      onSuccess: () => {
        toast.success(t('trainers.toast.deleted'))
        onClose()
      },
      onError: (err) => {
        if (isDomainError(err) && err.code === 'trainer_in_use') {
          setInlineError(t('trainers.errors.trainerInUse'))
          // Dialog stays open — user reads the error and dismisses manually
        } else {
          toast.error(t('common.errors.network'))
          onClose()
        }
      },
    })
  }

  return (
    <AlertDialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setInlineError(null)
          onClose()
        }
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t('trainers.dialog.deleteTitle')}</AlertDialogTitle>
          <AlertDialogDescription>
            {t('trainers.dialog.deleteBody').replace('{fullName}', trainer.fullName)}
          </AlertDialogDescription>
        </AlertDialogHeader>

        {inlineError && (
          <Alert variant="destructive" className="mb-3">
            <AlertDescription>{inlineError}</AlertDescription>
          </Alert>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel onClick={onClose}>
            {t('trainers.dialog.deleteCancel')}
          </AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={handleConfirm}
            disabled={deleteTrainer.isPending}
          >
            {deleteTrainer.isPending ? '…' : t('trainers.dialog.deleteConfirm')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
