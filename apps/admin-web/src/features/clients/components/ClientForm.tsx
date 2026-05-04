import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { ApiError, isDomainError } from '@/shared/api/errors'
import { clientCreateSchema, type ClientCreateFormInput } from '../model/schema'
import { useCreateClient, useUpdateClient } from '../api/hooks'
import type { Client } from '@/entities/client'

interface Props {
  mode: 'create' | 'edit'
  initial?: Client
  onSuccess: () => void
  onCancel: () => void
}

function splitFullName(full: string): { lastName: string; firstName: string; middleName?: string } {
  const parts = full.split(' ')
  return {
    lastName: parts[0] ?? '',
    firstName: parts[1] ?? '',
    middleName: parts[2],
  }
}

export function ClientForm({ mode, initial, onSuccess, onCancel }: Props) {
  const split = initial ? splitFullName(initial.fullName) : { lastName: '', firstName: '' }
  const form = useForm<ClientCreateFormInput>({
    resolver: zodResolver(clientCreateSchema),
    defaultValues: {
      lastName: split.lastName,
      firstName: split.firstName,
      middleName: split.middleName ?? '',
      phone: initial?.phone ?? '',
      email: initial?.email ?? '',
      birthDate: initial?.birthDate ?? '',
      notes: initial?.notes ?? '',
    },
  })
  const create = useCreateClient()
  const update = useUpdateClient()
  const isPending = create.isPending || update.isPending

  const handleError = (err: unknown) => {
    const fields = err instanceof ApiError || isDomainError(err) ? err.fields : undefined
    if (fields) {
      for (const [k, v] of Object.entries(fields)) {
        const msg = Array.isArray(v) ? String(v[0] ?? '') : String(v)
        form.setError(k as keyof ClientCreateFormInput, { type: 'server', message: msg })
      }
      return
    }
    form.setError('root', {
      type: 'server',
      message: 'Ошибка соединения. Проверьте сеть и попробуйте снова.',
    })
  }

  const onSubmit = form.handleSubmit((values) => {
    if (mode === 'create') {
      create.mutate(values, {
        onSuccess: () => onSuccess(),
        onError: handleError,
      })
    } else if (initial) {
      update.mutate(
        { id: initial.id, input: values },
        {
          onSuccess: () => onSuccess(),
          onError: handleError,
        },
      )
    }
  })

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label htmlFor="lastName">Фамилия*</Label>
          <Input id="lastName" {...form.register('lastName')} />
          {form.formState.errors.lastName && (
            <p className="text-destructive text-sm">{form.formState.errors.lastName.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="firstName">Имя*</Label>
          <Input id="firstName" {...form.register('firstName')} />
          {form.formState.errors.firstName && (
            <p className="text-destructive text-sm">{form.formState.errors.firstName.message}</p>
          )}
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="middleName">Отчество</Label>
        <Input id="middleName" {...form.register('middleName')} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="phone">Телефон*</Label>
        <Input id="phone" type="tel" placeholder="+79991234567" {...form.register('phone')} />
        {form.formState.errors.phone && (
          <p className="text-destructive text-sm">{form.formState.errors.phone.message}</p>
        )}
      </div>
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" {...form.register('email')} />
        {form.formState.errors.email && (
          <p className="text-destructive text-sm">{form.formState.errors.email.message}</p>
        )}
      </div>
      <div className="space-y-2">
        <Label htmlFor="birthDate">Дата рождения</Label>
        <Input id="birthDate" type="date" {...form.register('birthDate')} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="notes">Заметки</Label>
        <Input id="notes" {...form.register('notes')} />
      </div>
      {form.formState.errors.root && (
        <div
          role="alert"
          className="border-destructive/50 bg-destructive/10 text-destructive rounded-md border p-3 text-sm"
        >
          {form.formState.errors.root.message}
        </div>
      )}
      <div className="flex justify-between pt-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Не сохранять
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending
            ? 'Сохранение…'
            : mode === 'create'
              ? 'Добавить клиента'
              : 'Сохранить изменения'}
        </Button>
      </div>
    </form>
  )
}
