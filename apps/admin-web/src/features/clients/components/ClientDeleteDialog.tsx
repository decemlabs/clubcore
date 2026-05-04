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
import { ApiError, isDomainError } from '@/shared/api/errors'
import { useDeleteClient } from '../api/hooks'
import type { Client } from '@/entities/client'

interface Props {
  client: Client
  open: boolean
  onClose: () => void
}

export function ClientDeleteDialog({ client, open, onClose }: Props) {
  const remove = useDeleteClient()
  const handleConfirm = () => {
    remove.mutate(client.id, {
      onSuccess: () => onClose(),
      onError: (err) => {
        const code = err instanceof ApiError || isDomainError(err) ? err.code : undefined
        const message =
          code === 'forbidden'
            ? 'Доступ запрещён.'
            : 'Не удалось удалить клиента. Попробуйте позже.'
        toast.error(message)
        onClose()
      },
    })
  }
  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить клиента?</AlertDialogTitle>
          <AlertDialogDescription>
            Клиент <strong>{client.fullName}</strong> будет скрыт из списков.
            Данные сохранятся в базе (мягкое удаление).
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onClose} disabled={remove.isPending}>
            Не удалять
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={remove.isPending}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {remove.isPending ? 'Удаление…' : 'Удалить'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
