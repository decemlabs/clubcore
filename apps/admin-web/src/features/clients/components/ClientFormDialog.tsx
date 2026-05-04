import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog'
import { ClientForm } from './ClientForm'
import type { Client } from '@/entities/client'

type Props =
  | { mode: 'create'; open: boolean; onClose: () => void; client?: never }
  | { mode: 'edit'; open: boolean; onClose: () => void; client: Client }

export function ClientFormDialog(props: Props) {
  const { mode, open, onClose } = props
  const heading = mode === 'create' ? 'Добавить клиента' : 'Редактировать клиента'
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{heading}</DialogTitle>
          <DialogDescription className="sr-only">
            Форма данных клиента
          </DialogDescription>
        </DialogHeader>
        <ClientForm
          mode={mode}
          initial={mode === 'edit' ? props.client : undefined}
          onSuccess={onClose}
          onCancel={onClose}
        />
      </DialogContent>
    </Dialog>
  )
}
